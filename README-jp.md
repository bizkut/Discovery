# Discovery: カスタマイズ可能なMinecraftエージェントモデル

<div align="center">

[English](README.md) | [日本語](README-jp.md)

</div>

## Discoveryについて

Discoveryは、[MineDojo Voyager](https://github.com/MineDojo/Voyager)をベースに開発された、[LangFlow](https://github.com/logspace-ai/langflow)統合により高度なカスタマイズ性を実現したMinecraftエージェントモデルです。Voyagerが先駆的なLLMを活用したMinecraftエージェントである一方、Discoveryはさらに一歩進んで、研究者や開発者がフロー型インターフェースを通じてエージェントの動作、異なるLLMモデルの適用、カスタムスキルライブラリの作成を容易に行えるようにしました。

### 主な特徴

- **LangFlow統合**: コーディングの深い知識なしで、視覚的にエージェントの動作をデザイン・カスタマイズ可能
- **モデルの柔軟性**: OpenAI、Anthropic、ローカルモデルなど、様々なLLMプロバイダーを簡単に切り替え可能
- **拡張されたカスタマイズ機能**: プロンプト、スキル、探索戦略を視覚的インターフェースで修正可能
- **Docker対応**: コンテナ化された環境で簡単にデプロイ
- **クロスプラットフォーム**: Windows、macOS、Linuxで一貫した動作を保証

## Dockerでのインストール

Discoveryは完全にDocker上で動作し、プラットフォームに依存しない一貫したセットアップを実現します。

### 前提条件

- [Docker](https://www.docker.com/products/docker-desktop/)とDocker Compose
- Minecraft Java Edition（バージョン1.19.0）
- OpenAI APIキーまたは他の対応LLMプロバイダーの認証情報

### セットアップ手順

1. **リポジトリのクローン**
   ```bash
   git clone https://github.com/[your-username]/Discovery.git
   cd Discovery
   ```

2. **環境変数の設定**
   ```bash
   cp .env.example .env
   ```
   
   `.env`ファイルを編集し、APIキーと設定を入力：
   ```
   # Minecraft接続情報
   MINECRAFT_PORT=25565
   MINECRAFT_HOST=host.docker.internal

   # OpenAI API情報
   OPENAI_API_KEY=your_openai_api_key_here

   # Azure Minecraft認証情報（必要な場合）
   CLIENT_ID=your_client_id_here
   REDIRECT_URL=https://127.0.0.1/auth-response
   SECRET_VALUE=your_secret_value_here
   ```

3. **Minecraftモッドのインストール**
   
   Discoveryには特定のFabricモッドが必要です：
   1. [Fabric Loader](https://fabricmc.io/use/installer/)をインストール（推奨：fabric-loader-0.14.18-1.19）
   2. 以下のモッドをMinecraftのmodsフォルダにダウンロード・インストール：
      - [Fabric API](https://modrinth.com/mod/fabric-api/version/0.58.0+1.19)
      - [Mod Menu](https://cdn.modrinth.com/data/mOgUt4GM/versions/4.0.4/modmenu-4.0.4.jar)
      - [Complete Config](https://www.curseforge.com/minecraft/mc-mods/completeconfig/download/3821056)
      - [Multi Server Pause](https://www.curseforge.com/minecraft/mc-mods/multiplayer-server-pause-fabric/download/3822586)
      - [Better Respawn](https://github.com/xieleo5/better-respawn/tree/1.19)（手動ビルドが必要）

4. **Dockerコンテナのビルドと起動**
   ```bash
   docker-compose up -d
   ```
   
   これにより：
   - 必要な依存関係を含むDockerイメージがビルドされます
   - コンテナがバックグラウンドで起動します
   - LangFlow（7860）、ChatUI（7850）、Minecraft（25565）用のポートが公開されます

5. **Minecraftの起動とLAN公開**
   - ホストマシンでMinecraftクライアントをFabricプロファイルで起動
   - クリエイティブモード、ピースフル難易度で新しいワールドを作成
   - Escキーを押して「LANに公開」を選択
   - チートを有効にしてLANワールドを開始
   - **重要**: 表示されたポート番号（例: 「ポート55555でローカルゲームがホストされました」）をメモしてください

6. **LangFlowインターフェースへのアクセス**
   
   LangFlowを起動：
   ```bash
   docker exec -it discovery python -m langflow run
   ```

   ブラウザで以下のURLにアクセス：
   ```
   http://localhost:7860
   ```
   
   ワークフローの読み込み：
   1. 「New Flow」をクリックして「blank flow」を選択
   2. 上部の「🔽」（ダウンロード）ボタンをクリック
   3. 「Import」から`langflow_json`フォルダ内のJSONファイルを選択
   4. ワークフローが読み込まれ、カスタマイズ可能になります

## LangFlowでのエージェントのカスタマイズ

LangFlowインターフェースでは、エージェントの動作を視覚的に調整できます：

1. **ベースワークフローの読み込み**
   - LangFlowインターフェース（`http://localhost:7860`）を開く
   - 「New Flow」から「blank flow」を選択
   - 上部の「🔽」ボタンをクリック
   - 「Import」から`langflow_json`ディレクトリのJSONファイルを選択
   - 必要なコンポーネントを含むベースワークフローが読み込まれます

2. **コンポーネントのカスタマイズ**
   - ノードをドラッグ＆ドロップしてエージェントの動作を修正
   - ノードをダブルクリックしてパラメータを調整
   - カスタマイズ可能なオプション：
     - 探索範囲と戦略
     - スキルの優先順位と実行ルール
     - LLMモデルの選択とパラメータ
     - カスタムプロンプトテンプレート

3. **エージェントのデプロイ**
   - ワークフローの調整が完了したら「Export」をクリック
   - 変更したJsonファイルに上書き保存してください
   - 更新されたJsonワークフローは次回のDiscovery実行時に自動的に読み込まれます

## Discoveryの実行

LangFlowでワークフローをカスタマイズした後、Discoveryを実行できます。

1. **run_devbox.pyの実行**
   ```bash
   docker exec -it discovery python3 run_devbox.py
   ```

   実行時、以下のような出力が表示されます：
   ```
   Minecraft接続情報:
   - ポート: 59143  # ← この番号をLANで表示されたポート番号に変更してください
   - Minecraftホスト: host.docker.internal
   - Mineflayerホスト: localhost (コンテナ内)
   ```

2. **ポート番号の変更**
   - プログラムを一度終了（Ctrl+C）
   - `run_devbox.py`を編集し、`minecraft_port`の値をLANで表示されたポート番号に変更
   - 再度プログラムを実行

エージェントは自動的に：
1. 修正したJSONから最新のワークフロー設定を読み込み
2. 指定したポートでMinecraftワールドに接続
3. カスタマイズされた動作設定に従って行動を開始します

## 重要な注意点

- MinecraftクライアントはホストマシンでのみRUN可能です（Docker内では不可）
- 必ずMinecraftを起動してLANに公開してから、Discoveryを実行してください
- 接続問題が発生した場合は以下を確認：
  - ファイアウォールの設定
  - `.env`ファイルのMINECRAFT_PORTがMinecraftのLANポートと一致していること
  - docker-compose.ymlのホスト設定
- モッドのバージョンが正確に一致していることを確認
- LangFlowでの変更は次回のDiscovery実行時に自動的に適用されます

## ライセンス

このプロジェクトは[Research and Development License - Non-Commercial Use Only](LICENSE)の下で提供されています。

**免責事項**: このプロジェクトは研究目的専用であり、公式製品ではありません。 