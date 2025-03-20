import os
import json
from typing import Optional, List, Dict, Any, Union
from flask import Flask, render_template, request, jsonify
import threading
import webbrowser
from flask_socketio import SocketIO
from langflow_chat.langflow import Langflow

class ChatUI:
    def __init__(
        self,
        langflow_instance: Optional[Langflow] = None,
        port: int = 5000,
        host: str = "127.0.0.1",
        debug: bool = False,
        title: str = "Langflow Chat",
        auto_open: bool = True,
        use_websocket: bool = True
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
        """
        self.app = Flask(__name__)
        self.socketio = SocketIO(self.app, cors_allowed_origins="*") if use_websocket else None
        self.langflow = langflow_instance or Langflow()
        self.port = port
        self.host = host
        self.debug = debug
        self.title = title
        self.auto_open = auto_open
        self.server_thread = None
        self.use_websocket = use_websocket
        
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
                dict_data, _ = self.langflow.run_flow(
                    message=message,
                    endpoint=endpoint,
                    output_type=data.get('output_type', 'chat'),
                    input_type=data.get('input_type', 'chat'),
                    tweaks=data.get('tweaks'),
                    api_key=data.get('api_key')
                )
                
                # WebSocket経由で更新を通知
                if self.use_websocket:
                    self.socketio.emit('chat_updated', {
                        "history": self.langflow.get_chat_history()
                    })
                
                return jsonify({
                    "success": True,
                    "response": dict_data,
                    "history": self.langflow.get_chat_history()
                })
            except Exception as e:
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
    
    def _setup_socketio_events(self):
        """
        WebSocketのイベントハンドラを設定
        """
        @self.socketio.on('connect')
        def handle_connect():
            # クライアント接続時に最新のチャット履歴を送信
            self.socketio.emit('chat_updated', {
                "history": self.langflow.get_chat_history()
            })
        
        @self.socketio.on('request_history')
        def handle_request_history():
            # クライアントからの履歴リクエスト
            self.socketio.emit('chat_updated', {
                "history": self.langflow.get_chat_history()
            })
    
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