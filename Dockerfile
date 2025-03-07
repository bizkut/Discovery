FROM python:3.9-slim

# Node.jsをインストール (v16を使用)
RUN apt-get update && apt-get install -y \
    curl \
    gnupg \
    build-essential \
    git \
    && curl -fsSL https://deb.nodesource.com/setup_16.x | bash - \
    && apt-get install -y nodejs \
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/*

# バージョン確認
RUN node --version && npm --version

# Pythonの依存関係をインストール
WORKDIR /app
COPY requirements.txt setup.py README.md ./
RUN pip install -e .

# Node.jsの依存関係をインストール
COPY voyager/env/mineflayer /app/voyager/env/mineflayer
WORKDIR /app/voyager/env/mineflayer

# mineflayer-collectblockをビルドせずにインストール
RUN cd mineflayer-collectblock && \
    npm install --only=prod && \
    cd .. && \
    npm install

# プロジェクトのソースコードをコピー
WORKDIR /app
COPY . .

# エントリポイントスクリプトの設定
COPY docker-entrypoint.sh /docker-entrypoint.sh
RUN chmod +x /docker-entrypoint.sh

# デフォルトコマンド
CMD ["/docker-entrypoint.sh"]