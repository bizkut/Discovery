import os
import subprocess
import sys
from dotenv import load_dotenv
from voyager.devbox import Voyager_devbox

def check_minecraft_connection(host, port):
    """Minecraftサーバーへの接続をチェックする"""
    print(f"\nMinecraftサーバーの接続確認を開始します...")
    
    # pingでホストへの到達性を確認
    try:
        ping_result = subprocess.run(['ping', '-c', '4', host], 
                                   capture_output=True, 
                                   text=True)
        print("\nPing結果:")
        print(ping_result.stdout)
        
        if ping_result.returncode != 0:
            print(f"警告: {host}へのpingに失敗しました")
            print("エラー出力:", ping_result.stderr)
            return False
    except Exception as e:
        print(f"Pingテスト中にエラーが発生しました: {e}")
        return False
    
    return True

# .envファイルから環境変数を読み込む
load_dotenv()

# 環境変数から情報を取得
minecraft_port = 49697
openai_api_key = os.getenv("OPENAI_API_KEY")
minecraft_host = os.getenv("MINECRAFT_HOST", "host.docker.internal")  # 環境変数から読み込み、デフォルト値はhost.docker.internal

# 接続情報を表示
print(f"Minecraft接続情報:")
print(f"- ポート: {minecraft_port}")
print(f"- Minecraftホスト: {minecraft_host}")
print(f"- Mineflayerホスト: localhost (コンテナ内)")

# Minecraftサーバーへの接続確認
if not check_minecraft_connection(minecraft_host, minecraft_port):
    print("Minecraftサーバーへの接続確認に失敗しました。")
    sys.exit(1)

# Voyagerの初期化
devbox = Voyager_devbox(
    mc_port=minecraft_port,
    mc_host=minecraft_host,  # Minecraftホストを指定
)

# 継続的学習の開始
devbox.learn()
