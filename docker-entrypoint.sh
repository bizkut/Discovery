#!/bin/bash
set -e

echo "🔧 Voyagerの設定を開始します..."

# 必要なディレクトリ構造を確認
mkdir -p /app/data

# 環境変数の設定
if [ -z "$MINECRAFT_PORT" ]; then
  echo "⚠️ MINECRAFT_PORT環境変数が設定されていません。デフォルト値(25565)を使用します。"
  export MINECRAFT_PORT=25565
else
  echo "🔌 Minecraftポート: $MINECRAFT_PORT"
fi

# OpenAI APIキーの確認
if [ -z "$OPENAI_API_KEY" ]; then
  echo "❌ OPENAI_API_KEY環境変数が設定されていません。Voyagerの実行には必須です。"
  exit 1
else
  echo "✅ OpenAI APIキーが設定されています。"
fi

echo "🔍 Azure Loginの設定を確認してください。接続に必要です。"
echo "🎮 Minecraftインスタンスを起動し、LANに公開してください。"
echo "📝 Voyagerが利用するために必要なFabricモッドがインストールされていることを確認してください。"

echo "🚀 Voyager環境の準備が完了しました！"
echo "👉 Pythonスクリプトを実行して、Voyagerエージェントを起動できます。"

# コンテナを起動状態に保つ
exec tail -f /dev/null 