# Voyager スタートガイド

このREADMEでは、Voyagerプロジェクトの`start.py`スクリプトの使用方法について説明します。

## 概要

`start.py`は、Voyagerエージェントを簡単に起動するためのヘルパースクリプトです。このスクリプトは以下の機能を提供します：

1. 必要な環境変数の読み込み
2. 必要なパッケージのバージョン確認
3. 不足しているパッケージの自動インストール
4. Voyagerエージェントの初期化と学習の開始

## 前提条件

- Python 3.9以上
- 必要なライブラリ（自動インストールもサポート）
  - langchain（最新バージョン）
  - langchain-openai
  - langchain-core
  - python-dotenv
  - openai
- Minecraftゲームとインスタンスのセットアップ（メインREADMEを参照）
- OpenAI APIキー

## セットアップ

1. `.env`ファイルを作成し、以下の情報を設定します：

```
# Minecraft接続情報
MINECRAFT_PORT=<PORT_NUMBER>

# OpenAI API情報
OPENAI_API_KEY=<YOUR_API_KEY>

# Azure Minecraft認証情報（オプション）
CLIENT_ID=<your_client_id_here>
REDIRECT_URL=<redirect_url>
SECRET_VALUE=<your_secret_value_here>
```

2. `start.py`を実行します：

```bash
python start.py
```

## 機能の詳細

### 環境変数の読み込み

スクリプトは`.env`ファイルから以下の変数を読み込みます：
- `OPENAI_API_KEY`: OpenAI APIキー
- `MINECRAFT_PORT`: Minecraftサーバーのポート番号

### パッケージのバージョン確認

スクリプトは以下のパッケージがインストールされているか確認します：
- langchain
- langchain-openai
- langchain-core
- openai

不足しているパッケージがある場合は、インストールするかどうかの確認を表示します。

### Voyagerの初期化と実行

スクリプトは以下のパラメータでVoyagerエージェントを初期化します：
- `openai_api_key`: OpenAI APIキー
- `mc_port`: Minecraftポート
- `action_agent_model_name`: 使用するGPTモデル（デフォルト: "gpt-3.5-turbo-0125"）
- `action_agent_temperature`: 生成の温度パラメータ（デフォルト: 0）

初期化後、`voyager.learn()`メソッドを呼び出して学習プロセスを開始します。

## トラブルシューティング

問題が発生した場合は、以下を確認してください：

1. `.env`ファイルに正しい情報が設定されているか
2. 必要なパッケージがすべてインストールされているか
3. Minecraftが正しく設定され、実行されているか

詳細な情報については、メインのREADMEファイルとFAQを参照してください。 