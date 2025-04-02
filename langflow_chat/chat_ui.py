import os
import json
import requests
from typing import Optional, List, Dict, Any, Union
from flask import Flask, render_template, request, jsonify
import threading
import webbrowser
from flask_socketio import SocketIO
from langflow_chat.langflow import LangflowChat

class ChatUI:
    def __init__(
        self,
        langflow_instance: Optional[LangflowChat] = None,
        port: int = 5000,
        host: str = "127.0.0.1",
        debug: bool = False,
        title: str = "Langflow Chat",
        auto_open: bool = True,
        use_websocket: bool = True,
        mineflayer_api_url: str = "http://localhost:3000"
    ):
        """
        ChatGPTのようなチャットUIを提供するクラス。
        
        :param langflow_instance: Langflowインスタンス
        :param port: Webサーバーのポート番号
        :param host: ホスト名
        :param debug: デバッグモード
        :param title: チャットUIのタイトル
        :param auto_open: 自動的にブラウザで開くかどうか
        :param use_websocket: WebSocketを使用してリアルタイム更新するかどうか
        :param mineflayer_api_url: MineflayerのAPIサーバーURL
        """
        self.app = Flask(__name__)
        
        # WebSocketの設定
        if use_websocket:
            # より詳細なログを有効にする
            if debug:
                self.app.logger.setLevel('DEBUG')
                
            # Socket.IOサーバーの設定
            socketio_config = {
                'cors_allowed_origins': "*",      # CORSを許可
                'ping_timeout': 60,               # pingタイムアウト（秒）
                'ping_interval': 25,              # ping間隔（秒）
                'max_http_buffer_size': 10e6,     # バッファサイズ（10MB）
                'async_mode': 'threading',        # 非同期モード
                'logger': debug,                  # ロギングの有効化
                'engineio_logger': debug          # Engine.IOのロギング
            }
            
            self.socketio = SocketIO(self.app, **socketio_config)
        else:
            self.socketio = None
            
        self.langflow = langflow_instance or LangflowChat()
        self.port = port
        self.host = host
        self.debug = debug
        self.title = title
        self.auto_open = auto_open
        self.server_thread = None
        self.use_websocket = use_websocket
        self.mineflayer_api_url = mineflayer_api_url
        
        # コールバックの登録（LangflowChatの更新を受け取る）
        if self.use_websocket:
            self.langflow.register_update_callback(self._notify_chat_updated)
        
        # ルートの設定
        self._setup_routes()
        
        # WebSocketのイベントハンドラの設定
        if self.use_websocket:
            self._setup_socketio_events()
    
    def _setup_routes(self):
        """
        Flaskルートの設定
        """
        @self.app.route('/')
        def index():
            return render_template('chat.html', title=self.title, use_websocket=self.use_websocket)
        
        @self.app.route('/debug')
        def debug():
            return render_template('debug.html', mineflayer_api_url=self.mineflayer_api_url)
        
        @self.app.route('/api/proxy/mineflayer', methods=['POST'])
        def proxy_mineflayer():
            data = request.json
            endpoint = data.get('endpoint')
            payload = data.get('payload', {})
            
            if not endpoint:
                return jsonify({"error": "エンドポイントは必須です"}), 400
            
            try:
                response = requests.post(
                    f"{self.mineflayer_api_url}{endpoint}", 
                    json=payload,
                    timeout=300  # 長時間のレスポンスに対応
                )
                
                return jsonify(response.json()), response.status_code
            except requests.exceptions.RequestException as e:
                return jsonify({"error": f"APIサーバーへの接続に失敗しました: {str(e)}"}), 500
        
        @self.app.route('/api/chat_history', methods=['GET'])
        def get_chat_history():
            return jsonify(self.langflow.get_chat_history())
        
        @self.app.route('/api/send_message', methods=['POST'])
        def send_message():
            data = request.json
            message = data.get('message', '')
            endpoint = data.get('endpoint', '')
            
            if not message or not endpoint:
                return jsonify({"error": "メッセージとエンドポイントは必須です"}), 400
            
            try:
                # まずユーザーメッセージをチャット履歴に追加（内部でWebSocketイベントを発行）
                self._add_user_message_to_history(message)
                
                # 問い合わせ中のメッセージを追加（内部でWebSocketイベントを発行）
                self._add_pending_message_to_history()
                
                # Langflowにメッセージを送信（update_history=Falseに設定して、内部での履歴更新を無効化）
                dict_data = self.langflow.run_flow(
                    message=message,
                    endpoint=endpoint,
                    output_type=data.get('output_type', 'chat'),
                    input_type=data.get('input_type', 'chat'),
                    tweaks=data.get('tweaks'),
                    api_key=data.get('api_key'),
                    update_history=False  # 内部での履歴更新を無効化
                )
                
                # 問い合わせ中のメッセージを削除（内部でWebSocketイベントを発行）
                self._remove_pending_messages_from_history()
                
                return jsonify({
                    "success": True,
                    "response": dict_data,
                    "history": self.langflow.get_chat_history()
                })
            except Exception as e:
                # エラー発生時も問い合わせ中のメッセージを削除（内部でWebSocketイベントを発行）
                self._remove_pending_messages_from_history()
                return jsonify({"error": str(e)}), 500
        
        @self.app.route('/api/clear_history', methods=['POST'])
        def clear_history():
            self.langflow.clear_chat_history()
            
            # WebSocket経由で更新を通知
            if self.use_websocket:
                self.socketio.emit('chat_updated', {
                    "history": self.langflow.get_chat_history()
                })
                
            return jsonify({"success": True})
        
        @self.app.route('/shutdown', methods=['GET'])
        def shutdown():
            shutdown_func = request.environ.get('werkzeug.server.shutdown')
            if shutdown_func is None:
                raise RuntimeError('サーバーをシャットダウンできません。Werkzeugサーバーではありません。')
            
            shutdown_func()
            return 'サーバーをシャットダウンしています...'
    
    def _add_user_message_to_history(self, message: str) -> None:
        """
        ユーザーメッセージをチャット履歴に追加します。
        """
        self.langflow._add_user_message_to_history(message)
        
        # WebSocketが有効な場合は更新を通知
        if self.use_websocket:
            self.socketio.emit('chat_updated', {
                "history": self.langflow.get_chat_history()
            })
    
    def _add_pending_message_to_history(self) -> None:
        """
        問い合わせ中のプレースホルダーメッセージを追加します。
        """
        self.langflow._add_pending_message_to_history()
        
        # WebSocketが有効な場合は更新を通知
        if self.use_websocket:
            self.socketio.emit('chat_updated', {
                "history": self.langflow.get_chat_history()
            })
    
    def _remove_pending_messages_from_history(self) -> None:
        """
        問い合わせ中のメッセージを削除します。
        """
        self.langflow._remove_pending_messages_from_history()
        
        # WebSocketが有効な場合は更新を通知
        if self.use_websocket:
            self.socketio.emit('chat_updated', {
                "history": self.langflow.get_chat_history()
            })
            
    def _add_bot_response_to_history(self, name: str, text: str, icon: Optional[str] = None) -> None:
        """
        ボットの応答をチャット履歴に追加します。
        """
        self.langflow._add_bot_response_to_history(name, text, icon)
        
        # WebSocketが有効な場合は更新を通知
        if self.use_websocket:
            self.socketio.emit('chat_updated', {
                "history": self.langflow.get_chat_history()
            })
            
    def _setup_socketio_events(self):
        """
        WebSocketのイベントハンドラを設定
        """
        @self.socketio.on('connect')
        def handle_connect():
            # クライアント接続時の処理
            print(f"クライアント接続: {request.sid}")
            # 最新のチャット履歴を送信
            self.socketio.emit('chat_updated', {
                "history": self.langflow.get_chat_history()
            }, room=request.sid)  # 接続したクライアントのみに送信
            print(f"初期履歴送信: {len(self.langflow.get_chat_history())}件のメッセージ")
        
        @self.socketio.on('disconnect')
        def handle_disconnect():
            # クライアント切断時の処理
            print(f"クライアント切断: {request.sid}")
        
        @self.socketio.on('error')
        def handle_error(error):
            # エラー発生時の処理
            print(f"WebSocketエラー: {error}")
        
        @self.socketio.on('request_history')
        def handle_request_history():
            # クライアントからの履歴リクエスト
            print(f"履歴リクエスト: {request.sid}")
            history = self.langflow.get_chat_history()
            print(f"履歴送信: {len(history)}件のメッセージ")
            self.socketio.emit('chat_updated', {
                "history": history
            }, room=request.sid)  # リクエストしたクライアントのみに送信
    
    def start(self):
        """
        チャットUIのWebサーバーを起動します
        """
        if self.auto_open:
            # 別スレッドでブラウザを開く
            threading.Timer(1.0, lambda: webbrowser.open(f"http://{self.host}:{self.port}")).start()
        
        # サーバーの起動
        if self.use_websocket:
            self.socketio.run(self.app, host=self.host, port=self.port, debug=self.debug)
        else:
            self.app.run(host=self.host, port=self.port, debug=self.debug)
    
    def start_background(self):
        """
        バックグラウンドでチャットUIのWebサーバーを起動します
        """
        def run_server():
            if self.use_websocket:
                self.socketio.run(self.app, host=self.host, port=self.port, debug=False, use_reloader=False)
            else:
                self.app.run(host=self.host, port=self.port, debug=False, use_reloader=False)
        
        if self.server_thread is None or not self.server_thread.is_alive():
            self.server_thread = threading.Thread(target=run_server)
            self.server_thread.daemon = True
            self.server_thread.start()
            
            if self.auto_open:
                # ブラウザを開く
                webbrowser.open(f"http://{self.host}:{self.port}")
                
    def stop(self):
        """
        バックグラウンドで実行中のWebサーバーを停止します
        """
        if self.server_thread and self.server_thread.is_alive():
            # Flaskサーバーを停止するための方法
            # 1. リクエストを自分自身に送信して終了を通知
            import requests
            try:
                requests.get(f"http://{self.host}:{self.port}/shutdown")
            except requests.exceptions.ConnectionError:
                pass  # サーバーが既に停止している場合は無視
            
            # 2. スレッドの終了を待機（最大5秒）
            self.server_thread.join(timeout=5.0)
            
            # 3. スレッドが終了しているか確認
            if self.server_thread.is_alive():
                print("警告: サーバーのシャットダウンに失敗しました。プロセス終了時に自動的に停止します。")
            else:
                print("サーバーが正常に停止しました。") 

    def _notify_chat_updated(self):
        """
        チャット更新時にWebSocket経由で通知するコールバック
        """
        if self.use_websocket and self.socketio:
            print("メッセージ更新通知を送信")
            self.socketio.emit('chat_updated', {
                "history": self.langflow.get_chat_history()
            }) 