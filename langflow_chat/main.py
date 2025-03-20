from langflow_chat import Langflow, ChatUI

def main():
    """
    Langflow ChatUIのサンプル実行コード
    """
    # Langflowインスタンスの作成
    # URLは必要に応じて変更してください
    langflow = Langflow(langflow_base_api_url="http://127.0.0.1:7860")
    
    # ChatUIインスタンスの作成
    # Langflowインスタンスを渡す
    chat_ui = ChatUI(
        langflow_instance=langflow,
        port=5000,
        host="127.0.0.1",
        title="Langflow Chat UI",
        auto_open=True
    )
    
    # UIの起動
    chat_ui.start()

if __name__ == "__main__":
    main() 