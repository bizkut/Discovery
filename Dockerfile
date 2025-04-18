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

# プロジェクトの依存関係をインストール
RUN pip install --upgrade pip && \
    pip install -r requirements.txt

# プロジェクトのソースコードをコピー
WORKDIR /app
COPY . .

# langflow_chatの依存関係をインストール
WORKDIR /app/langflow_chat
RUN uv pip install --system -r requirements.txt

# mineflayerプロジェクトのセットアップ
WORKDIR /app/mineflayer
RUN npm install mineflayer && \
    npm install --save mineflayer-collectblock && \
    npm install --save mineflayer-pathfinder && \
    npm install --save mineflayer-web-inventory && \
    npm install --save mineflayer-tool && \
    npm install --save mineflayer-collectblock && \
    npm install --save mineflayer-pvp && \
    npm install --save prismarine-viewer

# 作業ディレクトリをルートに戻す
WORKDIR /app

# Langflowのポートを公開
EXPOSE 7860