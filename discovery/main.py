from discovery import Discovery
from autoggen import Auto_gen
import asyncio
import traceback # トレースバック取得のため

class DiscoveryMain:
    def __init__(self):
        # Discoveryインスタンスを作成
        self.discovery = Discovery()
        self.auto_gen = Auto_gen(self.discovery)
        self.skills = None

    async def run(self):
        """メイン実行関数"""
        # サーバー接続確認とボット召喚
        server_active = await self.discovery.check_server_and_join()
        
        if not server_active:
            print("サーバーに接続できないため、終了します")
            return
        await self.auto_gen.main(message="貴方の目標は、ネザーに到達することです。ダイヤピッケルを作成し、Obsidianを集めネザーゲートを作成しましょう！")

        # 終了時の処理（tryの外で実行）
        if self.discovery:
            self.discovery.disconnect_bot()
            print("ボットをサーバーから切断しました")

# メイン処理
if __name__ == "__main__":
    try:
        # DiscoveryMainインスタンスを作成して実行
        discovery_main = DiscoveryMain()
        asyncio.run(discovery_main.run())
    except Exception as e:
        print(f"エラーが発生しました: {e}")
        import traceback
        traceback.print_exc()
