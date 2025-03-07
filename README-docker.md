# Voyager Docker環境

このドキュメントでは、Docker環境を使用してVoyagerを実行する方法について説明します。

## 前提条件

- Docker と Docker Compose がインストールされていること
- Minecraft クライアント（バージョン：fabric-loader-0.14.18-1.19）が用意されていること
- Fabric モッドが正しくインストールされていること（[Fabric Mods Install](installation/fabric_mods_install.md)参照）
- OpenAI API キーを取得していること

## セットアップ手順

1. 環境変数ファイルを作成します：
   ```
   cp .env.example .env
   ```

2. `.env` ファイルを編集して、必要な値を設定します：
   - `OPENAI_API_KEY`: OpenAI API キー
   - `CLIENT_ID`: Azure Minecraft アカウントのクライアントID
   - `SECRET_VALUE`: Azure Minecraft アカウントのシークレット値（オプション）
   - `MINECRAFT_PORT`: Minecraft LAN世界のポート（デフォルト：25565）

3. Docker イメージをビルドして起動します：
   ```
   docker-compose up -d --build
   ```

## Voyagerの使用方法

1. Minecraft クライアントを起動し、シングルプレイヤーワールドを作成します：
   - ゲームモード：クリエイティブ
   - 難易度：ピースフル

2. 作成したワールドでLANに公開します：
   - ESCキーを押してメニューを開く
   - 「LANに公開」を選択
   - 「チートを許可：オン」に設定
   - 「LANワールドを開始」をクリック

3. Dockerコンテナに接続してVoyagerを実行します：
   ```
   docker-compose exec voyager python
   ```

4. Pythonインタプリタで以下のコードを実行します：
   ```python
   from voyager import Voyager
   
   azure_login = {
       "client_id": "YOUR_CLIENT_ID",  # .envで設定したCLIENT_ID
       "redirect_url": "https://127.0.0.1/auth-response",
       "secret_value": "YOUR_SECRET_VALUE",  # オプション
       "version": "fabric-loader-0.14.18-1.19", 
   }
   
   openai_api_key = "YOUR_API_KEY"  # .envで設定したOPENAI_API_KEY
   
   voyager = Voyager(
       azure_login=azure_login,
       openai_api_key=openai_api_key,
   )
   
   # 学習を開始
   voyager.learn()
   ```

## トラブルシューティング

- **Minecraft接続エラー**: LANワールドが正しく公開されているか、ポート設定が正しいか確認してください。
- **Azure Login認証エラー**: クライアントIDとリダイレクトURLが正しいかを確認してください。
- **API Key制限エラー**: OpenAI API Keyの利用制限を超えていないか確認してください。

## 注意事項

- Docker環境ではGUIが使えないため、Azureログイン認証が必要な場合は、ホストマシンで先に認証を行ってから設定ファイルをコンテナにマウントする必要があります。
- Voyagerのチェックポイントと学習データは `/app/data` ディレクトリに保存されます。このディレクトリはホストの `./data` にマウントされています。
- Minecraftクライアントはホストマシンで実行する必要があります。DockerコンテナからMinecraftサーバーへの接続のみをサポートしています。 