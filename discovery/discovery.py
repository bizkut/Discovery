from javascript import require, On, Once, AsyncTask, once, off
from dotenv import load_dotenv
import os
import asyncio
from skill.skills import Skills
import webbrowser
import sys

class Discovery:
    def __init__(self):
        load_dotenv()
        self.load_env()
        self.mineflayer = require("mineflayer")
        require('canvas') # エラーが出るので追加
        self.viewer_module = require('prismarine-viewer')

        self.bot = None
        self.mcdata = None
        self.is_connected = False
    
    def load_env(self):
        self.minecraft_host = os.getenv("MINECRAFT_HOST", "host.docker.internal")
        self.minecraft_port = os.getenv("MINECRAFT_PORT")
        self.minecraft_version = os.getenv("MINECRAFT_VERSION")
        self.web_inventory_port = os.getenv("WEB_INVENTORY_PORT")
        self.prismarine_viewer_port = os.getenv("PRISMARINE_VIEWER_PORT", 3000)

    def load_plugins(self):
        # Node.jsのモジュールパスを設定（mineflayerディレクトリのnode_modulesを参照）
        os.environ['NODE_PATH'] = "/workspaces/Voyager/mineflayer/node_modules"
        # pathfinder
        self.pathfinder = require("mineflayer-pathfinder")
        self.collectblock = require("mineflayer-collectblock").plugin
        self.web_inventory = require("mineflayer-web-inventory")
        self.mineflayer_tool = require("mineflayer-tool").plugin
        self.pvp = require("mineflayer-pvp").plugin
        self.bot.loadPlugin(self.pathfinder.pathfinder)
        self.bot.loadPlugin(self.collectblock)
        self.bot.loadPlugin(self.web_inventory)
        self.bot.loadPlugin(self.mineflayer_tool)
        self.bot.loadPlugin(self.pvp)
        self.movements = self.pathfinder.Movements(self.bot, self.mcdata)
        
        # Web Inventoryを有効化
        self.web_inventory(self.bot,{"port":self.web_inventory_port})
        # ブラウザでWeb Inventoryを開く
        webbrowser.open(f'http://localhost:{self.web_inventory_port}')
    
    def bot_join(self):
        """ボットをサーバーに接続します"""
        self.is_connected = False
        self.bot = self.mineflayer.createBot({
            "host": self.minecraft_host,
            "port": self.minecraft_port,
            "username": "BOT",
            "version": self.minecraft_version
        })
        
        # スポーン時の処理
        def handle_spawn(*args):
            print("Botがスポーンしました")
            self.bot.chat("Botがスポーンしました")
            self.is_connected = True
        
        # エラー時の処理
        def handle_error(err, *args):
            print(f"ボット接続エラー: {err}")
            self.is_connected = False
            
        # 切断時の処理
        def handle_end(*args):
            print("サーバー接続が終了しました")
            self.is_connected = False
        
        # ビューアーを開く
        def open_viewer():
            self.viewer_module.mineflayer(self.bot, {
                "firstPerson": True,
                "port": int(self.prismarine_viewer_port)})
            webbrowser.open(f'http://localhost:{self.prismarine_viewer_port}')
        
        # イベントリスナーを設定
        self.bot.once('spawn', handle_spawn)
        self.bot.on('error', handle_error)
        self.bot.on('end', handle_end)
        self.mcdata = require("minecraft-data")(self.bot.version)
        self.load_plugins()
        open_viewer()

    async def check_server_active(self, timeout=10):
        """
        サーバーがアクティブかどうかを確認します
        
        Args:
            timeout (int): タイムアウト秒数
            
        Returns:
            bool: サーバーがアクティブであればTrue、それ以外はFalse
        """
        if not self.bot:
            self.bot_join()
            
        start_time = asyncio.get_event_loop().time()
        while not self.is_connected:
            # タイムアウトチェック
            if asyncio.get_event_loop().time() - start_time > timeout:
                print(f"サーバー接続タイムアウト ({timeout}秒)")
                return False
            await asyncio.sleep(0.5)
            
        return True
    
    def bot_move(self, x, y, z):
        self.bot.pathfinder.setMovements(self.movements)
        self.bot.pathfinder.setGoal(self.pathfinder.goals.GoalNear(x, y, z, 1))
        self.bot.chat("移動します")
        
    def create_skills(self):
        """Skillsクラスのインスタンスを作成して返します"""
        if not self.bot:
            self.bot_join()
        return Skills(self)

    def is_server_active(self):
        """
        現在のサーバー接続状態を確認します（非同期ではない）
        
        Returns:
            bool: 接続中であればTrue、それ以外はFalse
        """
        if not self.bot:
            return False
            
        # 接続状態を確認
        return self.is_connected
        
    def get_server_info(self):
        """
        サーバーの基本情報を取得します
        
        Returns:
            dict: サーバー情報を含む辞書
        """
        if not self.is_server_active():
            return {"active": False}
            
        try:
            return {
                "active": True,
                "version": self.bot.version,
                "host": self.minecraft_host,
                "port": self.minecraft_port
            }
        except Exception as e:
            print(f"サーバー情報取得エラー: {e}")
            return {"active": False, "error": str(e)}

async def run_craft_example():
    """Skillsクラスのcraft_recipeメソッドを使用する例"""
    # Discoveryインスタンスを作成し、Skillsを初期化
    discovery = Discovery()
    discovery.bot_join()
    skills = discovery.create_skills()
    # サーバーがアクティブか確認
    server_active = await discovery.check_server_active(timeout=15)
    if not server_active:
        print("サーバーに接続できません。終了します。")
        return
        
    while True:
        try:
            print(input("Enter: "))
            results = await skills.get_surrounding_blocks(x_distance=3, y_distance=3, z_distance=4)
            #skills.test()
            #print(await skills.move_to_position(9,-60,-8,canDig=False))
            #print(await skills.move_to_position(9,-60,-30,canDig=False))
            #print(await skills.move_to_position(9,-60,-8,canDig=False))
        except Exception as e:
            print(f"エラーが発生しました: {str(e)}")
            import traceback
            traceback.print_exc()

if __name__ == "__main__":
    
    # サーバー接続チェックだけを行うモード
    if len(sys.argv) > 1 and sys.argv[1] == "--check-server":
        async def check_server_connection():
            discovery = Discovery()
            print("Minecraftサーバーの接続状態を確認しています...")
            result = await discovery.check_server_active(timeout=15)
            if result:
                print("✅ Minecraftサーバーはアクティブです！")
                # サーバーのバージョン情報表示
                print(f"サーバーバージョン: {discovery.bot.version}")
                print(f"プレイヤー数: {len(discovery.bot.players)}")
            else:
                print("❌ Minecraftサーバーに接続できませんでした")
            return result
        
        asyncio.run(check_server_connection())
    else:
        # Skillsモードで実行
        print("Skillsモードで起動します...")
        asyncio.run(run_craft_example())