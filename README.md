# Docker対応Voyager - フォークレポジトリ

**注意**: このレポジトリは[オリジナルのVoyager](https://github.com/MineDojo/Voyager)をフォークし、Docker環境での実行に対応させたものです。

## 本フォークについて

このレポジトリは、Voyagerを**Docker環境**で簡単に実行できるように改良したフォークです。オリジナルの機能を維持しながら、コンテナ化によって環境構築の手間を大幅に削減しています。

### Docker化の利点

- **環境構築の簡素化**: 複雑なPythonとNode.js依存関係を自動的に解決
- **クロスプラットフォーム対応**: Windows、macOS、Linuxで一貫した動作を保証
- **分離された実行環境**: ホストシステムに影響を与えずに実行可能
- **スケーラビリティ**: 複数のVoyagerインスタンスを簡単に管理可能

### 今後の開発予定

今後、Voyagerをさらに進化させるために、このレポジトリは随時アップデートされる可能性があります。予定している改善点は以下の通りです：

- **パフォーマンスの最適化**: 処理速度と安定性の向上
- **新しいLLMモデルへの対応**: GPT-4以外のモデルのサポート
- **スキルライブラリの拡張**: より多様なタスクに対応するスキルの追加
- **マルチエージェント対応**: 複数のエージェントが協力するシステムの構築

AIエージェント技術の発展に合わせて、新機能の追加や性能の改善を継続的に行っていく予定です。

---

# Voyager: An Open-Ended Embodied Agent with Large Language Models
<div align="center">

[[Website]](https://voyager.minedojo.org/)
[[Arxiv]](https://arxiv.org/abs/2305.16291)
[[PDF]](https://voyager.minedojo.org/assets/documents/voyager.pdf)
[[Tweet]](https://twitter.com/DrJimFan/status/1662115266933972993?s=20)

[![Python Version](https://img.shields.io/badge/Python-3.9-blue.svg)](https://github.com/MineDojo/Voyager)
[![GitHub license](https://img.shields.io/github/license/MineDojo/Voyager)](https://github.com/MineDojo/Voyager/blob/main/LICENSE)
______________________________________________________________________


https://github.com/MineDojo/Voyager/assets/25460983/ce29f45b-43a5-4399-8fd8-5dd105fd64f2

![](images/pull.png)


</div>

We introduce Voyager, the first LLM-powered embodied lifelong learning agent
in Minecraft that continuously explores the world, acquires diverse skills, and
makes novel discoveries without human intervention. Voyager consists of three
key components: 1) an automatic curriculum that maximizes exploration, 2) an
ever-growing skill library of executable code for storing and retrieving complex
behaviors, and 3) a new iterative prompting mechanism that incorporates environment
feedback, execution errors, and self-verification for program improvement.
Voyager interacts with GPT-4 via blackbox queries, which bypasses the need for
model parameter fine-tuning. The skills developed by Voyager are temporally
extended, interpretable, and compositional, which compounds the agent's abilities
rapidly and alleviates catastrophic forgetting. Empirically, Voyager shows
strong in-context lifelong learning capability and exhibits exceptional proficiency
in playing Minecraft. It obtains 3.3× more unique items, travels 2.3× longer
distances, and unlocks key tech tree milestones up to 15.3× faster than prior SOTA.
Voyager is able to utilize the learned skill library in a new Minecraft world to
solve novel tasks from scratch, while other techniques struggle to generalize.

In this repo, we provide Voyager code. This codebase is under [MIT License](LICENSE).

# Docker環境での実行方法

このフォークでは、Docker環境でVoyagerを簡単に実行できるようになっています。以下の手順に従って実行してください。

## 前提条件
- Docker
- Docker Compose
- Minecraft Java Edition（バージョン1.19.0）

## 事前準備

### 1. Modの導入
Voyagerを使用するには、特定のFabric Modsが必要です。以下の手順でModを導入してください：

1. [installation/fabric_mods_install.md](installation/fabric_mods_install.md)の手順に従って、必要なModをインストールします
2. 特にFabricのバージョンが正確に一致していることを確認してください（推奨：fabric-loader-0.14.18-1.19）

### 2. 環境変数の設定
`.env.sample`ファイルを参考に、`.env`ファイルを作成して必要な環境変数を設定します：

```bash
cp .env.sample .env
```

`.env`ファイルを編集し、以下の項目を設定してください：
- `OPENAI_API_KEY`: OpenAIのAPIキー
- `AZURE_CLIENT_ID`: MicrosoftアカウントのクライアントID (任意)
- `AZURE_REDIRECT_URL`: リダイレクトURL(任意)
- その他必要な設定項目

## 実行手順

1. リポジトリをクローンします
```bash
git clone https://github.com/[your-username]/Voyager.git
cd Voyager
```

2. Docker環境を構築・起動します
```bash
docker-compose up -d
```

3. **重要**: Minecraftクライアントを起動し、LAN公開の設定を行います
   - Minecraftを起動し、シングルプレイヤーで新しいワールドを作成します
   - ゲームモードを「クリエイティブ」、難易度を「ピースフル」に設定します
   - ワールドが作成されたら、Escキーを押して「LANに公開」を選択します
   - 「チートを許可」をONにして「LANワールドを開始」をクリックします

4. Voyagerを実行します
```bash
docker exec -it voyager python3 run_voyager.py
```

## 注意点
- Docker環境では、GUIが必要なMinecraftクライアントは別途ホストマシンで実行する必要があります
- **必ずVoyagerを起動する前にMinecraftクライアントを起動し、LANに公開しておいてください**
- 環境変数でOpenAI APIキーなどの設定を行うことができます（詳細は`.env.sample`を参照）
- 接続に問題がある場合は、ファイアウォールの設定を確認してください
- Modのバージョンが正確に一致していないと、正常に動作しない可能性があります

# Installation
Voyager requires Python ≥ 3.9 and Node.js ≥ 16.13.0. We have tested on Ubuntu 20.04, Windows 11, and macOS. You need to follow the instructions below to install Voyager.

## Python Install
```
git clone https://github.com/MineDojo/Voyager
cd Voyager
pip install -e .
```

## Node.js Install
In addition to the Python dependencies, you need to install the following Node.js packages:
```
cd voyager/env/mineflayer
npm install -g npx
npm install
cd mineflayer-collectblock
npx tsc
cd ..
npm install
```

## Minecraft Instance Install

Voyager depends on Minecraft game. You need to install Minecraft game and set up a Minecraft instance.

Follow the instructions in [Minecraft Login Tutorial](installation/minecraft_instance_install.md) to set up your Minecraft Instance.

## Fabric Mods Install

You need to install fabric mods to support all the features in Voyager. Remember to use the correct Fabric version of all the mods. 

Follow the instructions in [Fabric Mods Install](installation/fabric_mods_install.md) to install the mods.

# Getting Started
Voyager uses OpenAI's GPT-4 as the language model. You need to have an OpenAI API key to use Voyager. You can get one from [here](https://platform.openai.com/account/api-keys).

After the installation process, you can run Voyager by:
```python
from voyager import Voyager

# You can also use mc_port instead of azure_login, but azure_login is highly recommended
azure_login = {
    "client_id": "YOUR_CLIENT_ID",
    "redirect_url": "https://127.0.0.1/auth-response",
    "secret_value": "[OPTIONAL] YOUR_SECRET_VALUE",
    "version": "fabric-loader-0.14.18-1.19", # the version Voyager is tested on
}
openai_api_key = "YOUR_API_KEY"

voyager = Voyager(
    azure_login=azure_login,
    openai_api_key=openai_api_key,
)

# start lifelong learning
voyager.learn()
```

* If you are running with `Azure Login` for the first time, it will ask you to follow the command line instruction to generate a config file.
* For `Azure Login`, you also need to select the world and open the world to LAN by yourself. After you run `voyager.learn()` the game will pop up soon, you need to:
  1. Select `Singleplayer` and press `Create New World`.
  2. Set Game Mode to `Creative` and Difficulty to `Peaceful`.
  3. After the world is created, press `Esc` key and press `Open to LAN`.
  4. Select `Allow cheats: ON` and press `Start LAN World`. You will see the bot join the world soon. 

# Resume from a checkpoint during learning

If you stop the learning process and want to resume from a checkpoint later, you can instantiate Voyager by:
```python
from voyager import Voyager

voyager = Voyager(
    azure_login=azure_login,
    openai_api_key=openai_api_key,
    ckpt_dir="YOUR_CKPT_DIR",
    resume=True,
)
```

# Run Voyager for a specific task with a learned skill library

If you want to run Voyager for a specific task with a learned skill library, you should first pass the skill library directory to Voyager:
```python
from voyager import Voyager

# First instantiate Voyager with skill_library_dir.
voyager = Voyager(
    azure_login=azure_login,
    openai_api_key=openai_api_key,
    skill_library_dir="./skill_library/trial1", # Load a learned skill library.
    ckpt_dir="YOUR_CKPT_DIR", # Feel free to use a new dir. Do not use the same dir as skill library because new events will still be recorded to ckpt_dir. 
    resume=False, # Do not resume from a skill library because this is not learning.
)
```
Then, you can run task decomposition. Notice: Occasionally, the task decomposition may not be logical. If you notice the printed sub-goals are flawed, you can rerun the decomposition.
```python
# Run task decomposition
task = "YOUR TASK" # e.g. "Craft a diamond pickaxe"
sub_goals = voyager.decompose_task(task=task)
```
Finally, you can run the sub-goals with the learned skill library:
```python
voyager.inference(sub_goals=sub_goals)
```

For all valid skill libraries, see [Learned Skill Libraries](skill_library/README.md).

# FAQ
If you have any questions, please check our [FAQ](FAQ.md) first before opening an issue.

# Paper and Citation

If you find our work useful, please consider citing us! 

```bibtex
@article{wang2023voyager,
  title   = {Voyager: An Open-Ended Embodied Agent with Large Language Models},
  author  = {Guanzhi Wang and Yuqi Xie and Yunfan Jiang and Ajay Mandlekar and Chaowei Xiao and Yuke Zhu and Linxi Fan and Anima Anandkumar},
  year    = {2023},
  journal = {arXiv preprint arXiv: Arxiv-2305.16291}
}
```

Disclaimer: This project is strictly for research purposes, and not an official product from NVIDIA.
