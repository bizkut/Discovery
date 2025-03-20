import os
from dotenv import load_dotenv
from voyager import Voyager

# .envファイルから環境変数を読み込む
load_dotenv()

# 環境変数から情報を取得
openai_api_key = os.getenv("openai_api_key")
minecraft_port = os.getenv("MINECRAFT_PORT")
minecraft_host = os.getenv("MINECRAFT_HOST", "host.docker.internal")  # 環境変数から読み込み、デフォルト値はhost.docker.internal

# 接続情報を表示
print(f"Minecraft接続情報:")
print(f"- ポート: {minecraft_port}")
print(f"- Minecraftホスト: {minecraft_host}")
print(f"- Mineflayerホスト: localhost (コンテナ内)")

# Voyagerの初期化
voyager = Voyager(
    openai_api_key=openai_api_key,
    mc_port=minecraft_port,
    mc_host=minecraft_host,  # Minecraftホストを指定
    action_agent_model_name="gpt-4o-mini",
    curriculum_agent_model_name="gpt-4o-mini",
    curriculum_agent_qa_model_name="gpt-4o-mini",
    critic_agent_model_name="gpt-4o-mini",
    skill_manager_model_name="gpt-4o-mini",
)

# 継続的学習の開始
print("Voyagerの学習を開始します...")
voyager.learn()
