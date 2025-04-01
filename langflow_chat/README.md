# Langflow Chat UI

LangflowのチャットメッセージをChatGPTのようなUIで表示するシンプルなWebインターフェース。

## 機能

- ChatGPTのようなUIでチャットメッセージを表示
- name（ボット名）、icon（ボットアイコン）、text（チャット内容）を時系列順に表示
- チャット履歴の保存と表示
- レスポンシブデザイン

## インストール方法

```bash
# 依存パッケージのインストール
pip install -r requirements.txt
```

## 使用方法

```python
from langflow_chat import Langflow, ChatUI

# Langflowインスタンスの作成
langflow = Langflow(langflow_base_api_url="http://127.0.0.1:7860")

# ChatUIインスタンスの作成
chat_ui = ChatUI(
    langflow_instance=langflow,
    port=5000,
    host="127.0.0.1",
    title="Langflow Chat UI",
    auto_open=True
)

# UIの起動
chat_ui.start()
```

または、サンプルコードを実行するには：

```bash
python main.py
```

## 設定オプション

### Langflowクラス

- `langflow_base_api_url`: Langflow APIのベースURL（デフォルト: "http://127.0.0.1:7860"）

### ChatUIクラス

- `langflow_instance`: Langflowインスタンス
- `port`: Webサーバーのポート番号（デフォルト: 5000）
- `host`: ホスト名（デフォルト: "127.0.0.1"）
- `debug`: デバッグモード（デフォルト: False）
- `title`: チャットUIのタイトル（デフォルト: "Langflow Chat"）
- `auto_open`: 自動的にブラウザで開くかどうか（デフォルト: True）

## APIエンドポイント

ChatUIクラスは以下のAPIエンドポイントを提供します：

- `GET /api/chat_history`: チャット履歴を取得
- `POST /api/send_message`: メッセージを送信
  - リクエストボディ: `{ "message": "メッセージ内容", "endpoint": "エンドポイント名" }`
- `POST /api/clear_history`: チャット履歴をクリア 