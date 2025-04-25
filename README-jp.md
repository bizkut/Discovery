# Discovery: AutoGenによるカスタマイズ可能なMinecraftエージェント
<div align="center">

[English](README.md) | [日本語](README-jp.md)

![MinecraftAI](https://github.com/Mega-Gorilla/Discovery/blob/main/images/MinecraftAI.png?raw=true)
</div>

## Discoveryについて

Discoveryは、Minecraftの自動操作エージェントであり、[Mineflayer](https://github.com/PrismarineJS/mineflayer)によるBot操作と[AutoGen](https://github.com/microsoft/autogen)フレームワークによる高度なタスク実行・カスタマイズ性を組み合わせています。複数のAIエージェント（プランナー、コード実行、デバッガーなど）が連携し、ユーザーが設定した目標を達成するためにMinecraft内で自律的に行動します。

### 主な特徴

- **AutoGen統合**: 複数のAIエージェントが協調してタスクを計画、実行、デバッグします。
- **Mineflayerベース**: 実績のあるMineflayerライブラリを使用してMinecraft Botを操作します。
- **エージェントカスタマイズ**: 各エージェントのプロンプト (`discovery/autoggen.py` 内) を変更することで、動作や役割を調整可能。
- **モデルの柔軟性**: OpenAI、Google Geminiなど、AutoGenがサポートする様々なLLMモデルを利用可能（設定ファイルで変更）。
- **Docker対応**: コンテナ化された環境で簡単にセットアップ・実行。
- **スキル拡張性**: `discovery/skill/skills.py` にPython関数を追加することで、Botの能力を拡張可能。

## Dockerでのインストール

DiscoveryはDocker上で動作し、プラットフォームに依存しないセットアップを実現します。

### 前提条件

- [Docker](https://www.docker.com/products/docker-desktop/)とDocker Compose
- Minecraft Java Edition（バージョン1.19.0推奨）
- OpenAI APIキーまたは他の対応LLMプロバイダーのAPIキー

### セットアップ手順

1.  **リポジトリのクローン**
    ```bash
    git clone https://github.com/Mega-Gorilla/Discovery.git
    cd Discovery
    ```

2.  **環境変数の設定**
    ```bash
    cp .env.example .env
    ```

    `.env`ファイルを編集し、APIキーとMinecraft接続情報を入力します。
    ```dotenv
    # LLM API Keys
    OPENAI_API_KEY=your_openai_api_key_here
    GOOGLE_API_KEY=your_google_api_key_here # 必要に応じて

    # Minecraft接続情報 (Minecraftをホストマシンで実行する場合)
    MINECRAFT_PORT=25565 # MinecraftクライアントがLAN公開時に使用するポート (後で変更)
    MINECRAFT_HOST=host.docker.internal # Dockerからホストマシン上のMinecraftに接続する場合
    MINECRAFT_VERSION=1.19.0 # Minecraftのバージョン

    # Bot Viewer & Web Inventory Ports (変更可能)
    PRISMARINE_VIEWER_PORT=3000
    WEB_INVENTORY_PORT=3001
    ```
    **注意:** `MINECRAFT_PORT` は、後述するMinecraftのLAN公開時に表示されるポート番号に合わせて**再度編集が必要**になります。

3.  **Minecraftモッドのインストール (任意だが推奨)**

    必須ではありませんが、以下のModを導入するとBotの動作が安定し、デバッグが容易になります。
    1.  [Fabric Loader](https://fabricmc.io/use/installer/)をインストール（推奨：バージョン1.19.0に対応するもの）
    2.  Minecraftの`mods`フォルダに以下のModをダウンロード・インストール：
        *   [Fabric API](https://modrinth.com/mod/fabric-api) (バージョン確認)
        *   [Mod Menu](https://modrinth.com/mod/modmenu) (バージョン確認)
        *   必要に応じて他のデバッグ用Modなど

4.  **Dockerコンテナのビルドと起動**
    ```bash
    docker-compose up -d --build
    ```
    これにより、必要な依存関係を含むDockerイメージがビルドされ、コンテナがバックグラウンドで起動します。

5.  **Minecraftの起動とLAN公開**
    - ホストマシンでMinecraftクライアントをFabricプロファイル（Modを使用する場合）またはバニラで起動します。
    - クリエイティブモード、ピースフル難易度で新しいワールドを作成（または既存のワールドをロード）します。
    - Escキーを押して「LANに公開」を選択します。
    - チートを有効にして「LANワールドを開始」をクリックします。
    - **重要:** チャット欄に表示される**ポート番号**（例: `ポート 51234 でローカルゲームがホストされました`）をメモしてください。

6.  **`.env`ファイルのポート番号更新**
    - メモしたポート番号を `.env` ファイルの `MINECRAFT_PORT` の値に設定します。
    - **Dockerコンテナの再起動が必要です:**
      ```bash
      docker-compose restart discovery # 'discovery' は docker-compose.yml で定義されたサービス名
      ```

## エージェントのカスタマイズ

AutoGenエージェントの動作は、主にシステムメッセージ（プロンプト）を変更することでカスタマイズできます。

1.  **プロンプトの編集**:
    - `discovery/autoggen.py` ファイルを開きます。
    - `load_agents` メソッド内に各エージェント（`MineCraftPlannerAgent`, `CodeExecutionAgent`, `CodeDebuggerAgent` など）の定義があります。
    - 各エージェントの `system_message` パラメータの内容を編集することで、そのエージェントの役割、指示、制約などを変更できます。

2.  **スキルの追加**:
    - Botに新しい能力を追加したい場合は、`discovery/skill/skills.py` に新しいPythonメソッド（関数）を実装します。
    - `autoggen.py` の `CodeExecutionAgent` や `CodeDebuggerAgent` が新しいスキルを認識できるように、必要に応じてプロンプトやツール定義を更新します。

3.  **コンテナの再ビルド**:
    - Pythonコード (`.py` ファイル) を変更した場合、変更を反映させるためにDockerコンテナの再ビルドが必要です。
      ```bash
      docker-compose up -d --build
      ```

## Discoveryの実行

セットアップとカスタマイズが完了したら、Discoveryを実行できます。

1.  **ターミナルでコンテナ内に入る**:
    ```bash
    docker-compose exec discovery /bin/bash
    # または docker exec -it <container_id_or_name> /bin/bash
    ```

2.  **AutoGenスクリプトの実行**:
    コンテナ内で以下のコマンドを実行します。
    ```bash
    python -m discovery.autoggen # または python discovery/autoggen.py
    ```

   これにより、AutoGenのフレームワークが起動し、各エージェントが連携してタスクを開始します。
   - まず、Minecraftサーバーへの接続が行われます。
   - その後、ユーザーが設定した目標（現在は `autoggen.py` の `main` 関数内で定義されている可能性があります。将来的に対話的に設定できるようになるかもしれません）に基づいて、エージェントたちが計画、コード生成、実行、デバッグのサイクルを開始します。
   - コンソールには、各エージェントの発言やコード実行の結果が表示されます。

3.  **Botの視覚的確認 (任意)**:
    `.env` ファイルで設定したポート（デフォルト: 3000）で Prismarine Viewer が起動します。ブラウザで `http://localhost:3000` (またはDockerが動作しているマシンのIP) にアクセスすると、Botの視点を確認できます。

## 重要な注意点

- Minecraftクライアントはホストマシンで実行し、LANに公開する必要があります。
- 必ずMinecraftを起動してLANに公開し、`.env` の `MINECRAFT_PORT` を更新してから、Discoveryを実行してください。
- 接続問題が発生した場合は以下を確認：
  - ファイアウォールの設定
  - `.env`ファイルの`MINECRAFT_PORT`がMinecraftのLANポートと一致していること
  - Dockerのネットワーク設定 (`host.docker.internal` がホストマシンを指しているか)
- Modを使用する場合は、バージョンがMinecraft本体やFabric Loaderと互換性があることを確認してください。
- AutoGenエージェントのプロンプトを変更した場合、期待通りの動作をするかテストが必要です。

## ライセンス

このプロジェクトは[Research and Development License - Non-Commercial Use Only](LICENSE)の下で提供されています。

**免責事項**: このプロジェクトは研究目的専用であり、公式製品ではありません。 