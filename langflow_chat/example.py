"""
Langflow ChatUIの使用例
------------------------

このサンプルプログラムは、Langflow ChatUIを使用して簡単なチャットアプリケーションを構築し、
いくつかの制御方法を示しています。

実行方法:
    python example.py
"""

import time
import signal
import sys
from langflow_chat import Langflow, ChatUI

def signal_handler(sig, frame):
    """Ctrl+Cが押された時に実行される関数"""
    print("\nプログラムを終了します...")
    if chat_ui and hasattr(chat_ui, 'stop'):
        chat_ui.stop()
    sys.exit(0)

def direct_run_flow_example():
    """
    Langflowの run_flow メソッドを直接使用する例
    """
    print("=== Langflow.run_flow() の直接使用 ===")
    
    # Langflowインスタンスの作成
    langflow = Langflow(langflow_base_api_url="http://127.0.0.1:7860")
    
    # ユーザー入力の取得
    endpoint = input("エンドポイントを入力してください: ")
    message = input("メッセージを入力してください: ")
    
    # run_flowメソッドの実行
    try:
        print(f"エンドポイント '{endpoint}' にメッセージを送信中...")
        dict_data, list_data = langflow.run_flow(
            message=message,
            endpoint=endpoint
        )
        
        # 結果の表示
        print("\n=== 応答結果 ===")
        for bot_name, response_text in dict_data.items():
            print(f"\n[{bot_name}]")
            print(f"{response_text}")
            
        # チャット履歴の表示
        print("\n=== チャット履歴 ===")
        for item in langflow.get_chat_history():
            role = item.get('role', '')
            name = item.get('name', '')
            text = item.get('text', '')
            icon = item.get('icon', '')
            
            print(f"[{role}] {icon} {name}: {text[:50]}..." if len(text) > 50 else f"[{role}] {icon} {name}: {text}")
            
    except Exception as e:
        print(f"エラーが発生しました: {str(e)}")

def main():
    """
    メイン関数
    """
    global chat_ui
    
    # 1. Ctrl+Cのハンドラを設定
    signal.signal(signal.SIGINT, signal_handler)
    
    # 2. コマンドライン引数の解析
    import argparse
    parser = argparse.ArgumentParser(description="Langflow ChatUIのサンプルプログラム")
    parser.add_argument('--direct', action='store_true', help='UIを使わずに直接run_flowを実行')
    parser.add_argument('--port', type=int, default=5000, help='Webサーバーのポート番号')
    parser.add_argument('--url', type=str, default="http://127.0.0.1:7860", help='LangflowのベースURL')
    args = parser.parse_args()
    
    # 3. 実行モードに応じた処理
    if args.direct:
        # 直接run_flowを使用するモード
        direct_run_flow_example()
    else:
        # ChatUIを使用するモード
        print(f"Langflow ChatUIを起動します (ポート: {args.port})...")
        
        # Langflowインスタンスの作成
        langflow = Langflow(langflow_base_api_url=args.url)
        
        # ChatUIインスタンスの作成と起動
        chat_ui = ChatUI(
            langflow_instance=langflow,
            port=args.port,
            host="127.0.0.1",
            title="Langflow Chat UI サンプル",
            auto_open=True
        )
        
        try:
            # UIの起動
            chat_ui.start()
        except KeyboardInterrupt:
            # Ctrl+Cが押された場合
            print("\nプログラムを終了します...")
            chat_ui.stop()
        except Exception as e:
            print(f"エラーが発生しました: {str(e)}")
            if chat_ui:
                chat_ui.stop()

if __name__ == "__main__":
    chat_ui = None
    main() 