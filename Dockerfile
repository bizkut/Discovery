FROM python:3.11-slim

# 必要な開発ツールとPythonヘッダーをインストール
RUN apt-get update && apt-get install -y \
    curl \
    gnupg \
    build-essential \
    git \
    python3-dev \
    python3-pip \
    python3.11-dev \
    iputils-ping \
    && curl -fsSL https://deb.nodesource.com/setup_22.x | bash - \
    && apt-get install -y nodejs \
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/*

# バージョン確認
RUN node --version && npm --version

# uvのインストールとlangflowのインストール
RUN pip install uv && \
    uv pip install langflow --system

# Pythonの依存関係をインストール
WORKDIR /app
COPY requirements.txt setup.py README.md ./

RUN pip install --upgrade pip && \
    pip install -e .

# プロジェクトのソースコードをコピー
WORKDIR /app
COPY . .

# langflow_chatの依存関係をインストール
WORKDIR /app/langflow_chat
RUN pip install -r requirements.txt

# 親ディレクトリに移動してmineflayerの依存関係をインストール
WORKDIR /app/voyager/env/mineflayer
RUN npm install || (echo "npm installに失敗しました。パスやファイルの存在を確認してください。" && exit 1)

# mineflayer-collectblockの依存関係をインストールしてコンパイル
WORKDIR /app/voyager/env/mineflayer/mineflayer-collectblock
RUN npx tsc

WORKDIR /app/voyager/env/mineflayer
RUN npm install

# 作業ディレクトリをルートに戻す
WORKDIR /app

# エントリポイントスクリプトの設定
COPY docker-entrypoint.sh /docker-entrypoint.sh
RUN chmod +x /docker-entrypoint.sh

# Langflowのポートを公開
EXPOSE 7860
# ChatUIのポートも公開
EXPOSE 7850

# デフォルトコマンド
CMD ["/docker-entrypoint.sh"]