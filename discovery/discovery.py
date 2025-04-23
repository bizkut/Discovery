from javascript import require, On, Once, AsyncTask, once, off
from dotenv import load_dotenv
import os
import asyncio
from skill.skills import Skills
import webbrowser
import sys
import math
import inspect
import ast
import textwrap
import io
import contextlib
import traceback

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
        
    async def check_server_and_join(self, timeout=15):
        """
        サーバー接続状態を確認し、接続できていればボットを召喚します
        
        Args:
            timeout (int): 接続確認のタイムアウト秒数
            
        Returns:
            bool: 接続とボット召喚が成功したらTrue、失敗したらFalse
        """
        print("Minecraftサーバーの接続状態を確認しています...")
        
        # サーバー接続状態確認
        is_active = await self.check_server_active(timeout=timeout)
        
        if is_active:
            print(f"✅ Minecraftサーバーは稼働中です！(バージョン: {self.bot.version})")
            
            # スキルのインスタンスを作成
            self.skills = Skills(self)
            print("ボットが正常に召喚されました")
            return True
        else:
            print("❌ Minecraftサーバーに接続できませんでした")
            print("サーバーが起動しているか確認してください")
            return False

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

    def disconnect_bot(self):
        """ボットをサーバーから切断します"""
        if self.bot and self.is_connected:
            try:
                self.bot.quit() # または self.bot.end() を試す
                print("ボットがサーバーから切断されました。")
            except Exception as e:
                print(f"ボットの切断中にエラーが発生しました: {e}")
            finally:
                self.is_connected = False
                self.bot = None # 必要に応じてbotインスタンスもクリア

    async def get_bot_status(self):
        """ボットの状態と周辺情報（バイオーム、時間、体力、空腹度、エンティティ、インベントリ、ブロック分類）を取得"""
        if not self.bot or not self.skills:
            print("エラー: ボットまたはスキルが初期化されていません。")
            return None
            
        try:
            # --- ボットの基本情報を取得 ---
            bot_entity = self.bot.entity
            bot_pos_raw = bot_entity.position # Y座標はエンティティ基準
            bot_health = self.bot.health
            bot_food = self.bot.food
            bot_time = self.bot.time.timeOfDay

            # ボットがいるブロックとバイオームを取得
            center_block = self.bot.blockAt(bot_pos_raw)
            #bottom_block = self.discovery.bot.blockAt(bot_pos_raw.offset(0, -1, 0))
            bot_pos = center_block.position.offset(0, 1, 0)
            bot_biome_id = self.bot.world.getBiome(bot_pos)
            bot_biome_name = self.mcdata.biomes[str(bot_biome_id)]['name']
            bot_x = bot_pos.x
            bot_z = bot_pos.z
            bot_y = bot_pos.y # y座標も追加

            # --- 周囲のブロックを取得 & 分類 ---
            blocks = await self.skills.get_surrounding_blocks(
                position=bot_pos, # スキルの引数名に合わせる
                x_distance=3,
                y_distance=2,
                z_distance=3
            )

            # ブロック名をグループごとに一時的に格納
            temp_grouped_block_names = {"group1": [], "group2": [], "group3": [], "group4": [], "group0": []}

            if blocks:
                for block in blocks:
                    block_pos_dict = block.get('position')
                    block_name = block.get('name')
                    if not isinstance(block_pos_dict, dict) or block_name is None:
                        continue

                    block_x = block_pos_dict.get('x')
                    block_z = block_pos_dict.get('z')
                    if not isinstance(block_x, (int, float)) or not isinstance(block_z, (int, float)):
                        continue

                    dx = block_x - bot_x
                    dz = block_z - bot_z

                    if math.fabs(dx) < 1e-6 and math.fabs(dz) < 1e-6:
                        temp_grouped_block_names["group0"].append(block_name)
                    elif dz > 1e-6 and math.fabs(dx) <= dz + 1e-6:
                        temp_grouped_block_names["group1"].append(block_name)
                    elif dx > 1e-6 and math.fabs(dz) <= dx + 1e-6:
                        temp_grouped_block_names["group2"].append(block_name)
                    elif dz < -1e-6 and math.fabs(dx) <= math.fabs(dz) + 1e-6:
                        temp_grouped_block_names["group3"].append(block_name)
                    elif dx < -1e-6 and math.fabs(dz) <= math.fabs(dx) + 1e-6:
                        temp_grouped_block_names["group4"].append(block_name)

            # ブロック分類結果（重複除去とソート）
            classified_blocks = {
                "front_blocks": sorted(list(set(temp_grouped_block_names["group1"]))),
                "right_blocks": sorted(list(set(temp_grouped_block_names["group2"]))),
                "back_blocks": sorted(list(set(temp_grouped_block_names["group3"]))),
                "left_blocks": sorted(list(set(temp_grouped_block_names["group4"]))),
                "center_blocks": sorted(list(set(temp_grouped_block_names["group0"])))
            }

            # --- 近くのエンティティ情報を取得 ---
            nearby_entities_info = []
            # _get_nearby_entities は同期メソッドの可能性あり
            nearby_entities_raw = self.skills._get_nearby_entities(max_distance=16) # 範囲は適宜調整
            if nearby_entities_raw:
                for entity in nearby_entities_raw:
                    # 有効なエンティティ情報のみ抽出
                    if hasattr(entity, 'name') and hasattr(entity, 'position') and entity.position:
                        nearby_entities_info.append({
                            "name": entity.name,
                            "position": {
                                "x": round(entity.position.x, 1), # 小数点以下第一位で四捨五入
                                "y": round(entity.position.y, 1), # 小数点以下第一位で四捨五入
                                "z": round(entity.position.z, 1)  # 小数点以下第一位で四捨五入
                            }
                        })

            # --- インベントリ情報を取得 ---
            inventory_info = {}
            # get_inventory_counts は同期メソッド
            inventory_info = self.skills.get_inventory_counts()

            # --- 最終的なレスポンスを作成 ---
            final_result = {
                "biome": bot_biome_name,
                "time_of_day": bot_time,
                "health": bot_health,
                "hunger": bot_food,
                "bot_position": f"x={bot_x:.1f}, y={bot_y:.1f}, z={bot_z:.1f}",
                "nearby_entities": nearby_entities_info,
                "inventory": inventory_info,
                **classified_blocks # ブロック分類結果を展開して結合
            }
            return final_result

        except Exception as e:
            print(f"ボットステータスの取得中にエラーが発生しました: {e}")
            import traceback
            traceback.print_exc()
            return None
        
    async def get_skills_list(self):
        """Skillsクラスで利用可能な関数（メソッド）の名前、説明、非同期フラグのリストを取得"""
        if self.skills is None:
            print("エラー: Skillsが初期化されていません")
            return [] # 空のリストを返す

        skill_list = []
        # inspect.getmembersでskillsオブジェクトのメソッドを取得
        for name, method in inspect.getmembers(self.skills, inspect.ismethod):
            # アンダースコアで始まらない公開メソッドのみを対象とする
            if not name.startswith('_'):
                # docstringを取得し、整形
                docstring = inspect.cleandoc(method.__doc__) if method.__doc__ else "説明がありません。"
                # メソッドが非同期関数かどうかをチェック
                is_async = inspect.iscoroutinefunction(method)

                skill_list.append({
                    "name": name,
                    "description": docstring,
                    "is_async": is_async # 非同期フラグを追加
                })

        # 名前順にソートして返す
        return sorted(skill_list, key=lambda x: x['name'])
    
    async def get_skill_code(self, skill_name: str):
        """指定されたスキル関数のソースコードを取得 (docstring除外)"""
        result = {
            "success": False,
            "message": ""
        }
        if self.skills is None:
            result["message"] = "エラー: Skillsが初期化されていません"
            return result

        # skill_nameに対応するメソッドを取得
        try:
            method = getattr(self.skills, skill_name)
        except AttributeError:
            result["message"] = f"エラー: スキル関数 '{skill_name}' が見つかりません"
            return result

        # メソッドが呼び出し可能で、アンダースコアで始まらないことを確認
        if not callable(method) or skill_name.startswith('_'):
            result["message"] = f"エラー: スキル関数 '{skill_name}' が見つかりません、またはアクセスできません"
            return result

        # --- Docstringを除去するTransformer --- (関数内に定義)
        class DocstringRemover(ast.NodeTransformer):
            def _remove_docstring(self, node):
                if not node.body:
                    return
                # 関数/クラス定義内の最初の式がdocstringであるか確認
                if isinstance(node.body[0], ast.Expr):
                    if isinstance(node.body[0].value, ast.Constant) and isinstance(node.body[0].value.value, str):
                        # Docstring (Python 3.8+)
                        node.body.pop(0)
                    elif isinstance(node.body[0].value, ast.Str):
                        # Docstring (Python 3.7 or earlier)
                        node.body.pop(0)

            def visit_FunctionDef(self, node):
                self._remove_docstring(node)
                self.generic_visit(node)
                return node

            def visit_AsyncFunctionDef(self, node):
                self._remove_docstring(node)
                self.generic_visit(node)
                return node

        # メソッドのソースコードを取得し、docstringを除去
        try:
            source_code = inspect.getsource(method)
            # ソースコードのインデントを除去 (ASTパース前にdedentが必要)
            dedented_source_code = textwrap.dedent(source_code)

            # ASTにパース
            tree = ast.parse(dedented_source_code)

            # Docstringを削除するTransformerを適用
            transformer = DocstringRemover()
            new_tree = transformer.visit(tree)
            ast.fix_missing_locations(new_tree) # Location情報を修正

            # ASTをソースコード文字列に戻す (Python 3.9+)
            # ast.unparse はインデントを再構築する
            code_without_docstring = ast.unparse(new_tree)
            result["success"] = True
            result["message"] = code_without_docstring
            return result

        except (TypeError, OSError) as e:
            # ソースコードが取得できない場合
            result["message"] = f"エラー: スキル関数 '{skill_name}' のソースコードを取得できませんでした: {e}"
            return result
        except SyntaxError as e:
            # AST パース失敗時のエラーハンドリング
            result["message"] = f"エラー: スキル関数 '{skill_name}' のソースコードの解析に失敗しました: {e}"
            return result
        except AttributeError as e:
            # ast.unparse がない場合のエラー (Python 3.9未満)
            if "'module' object has no attribute 'unparse'" in str(e):
                result["message"] = "エラー: この機能にはPython 3.9以上が必要です (ast.unparse)。"
                return result
            else:
                result["message"] = f"エラー: 予期せぬエラーが発生しました: {e}"
                return result
    
    async def execute_python_code(self, code_string: str):
        """渡されたPythonコード文字列を実行します（非同期対応）"""
        # Check if bot and skills are initialized correctly
        if not self.bot or not self.skills:
            print("エラー: ボットまたはスキルが初期化されていません。")
            return {"success": False, "error": "Bot or skills not initialized", "traceback": "", "output": "", "error_output": ""}

        output_buffer = io.StringIO()
        error_buffer = io.StringIO()

        # 実行コンテキストに渡す変数 (botを追加)
        bot = self.bot # エイリアス
        skills = self.skills # エイリアス
        discovery = self # エイリアス
        exec_globals = {
            "asyncio": asyncio,
            "skills": skills,
            "discovery": discovery,
            "bot": bot,
            "__builtins__": __builtins__ # これが含まれている点が重要
        }

        # 動的に生成する非同期ラッパー関数の名前
        dynamic_async_func_name = "__dynamic_exec_async_code__"

        # ユーザーコードを適切にインデント
        indented_user_code = textwrap.indent(code_string, '    ')

        # 非同期ラッパー関数のコード文字列を作成
        wrapper_code = f"""
import asyncio # ラッパー関数内で asyncio を利用可能にする

async def {dynamic_async_func_name}():
    # 実行コンテキストから skills, discovery, bot を参照
    # (exec_globals で渡される)
    # --- User Code Start ---
{indented_user_code}
    # --- User Code End ---
"""

        try:
            # ラッパー関数を定義
            exec(wrapper_code, exec_globals)

            # 定義された非同期関数オブジェクトを取得
            async_func_to_run = exec_globals.get(dynamic_async_func_name)

            if async_func_to_run and inspect.iscoroutinefunction(async_func_to_run):
                # 標準出力と標準エラーをキャプチャしながら非同期関数を実行
                with contextlib.redirect_stdout(output_buffer), contextlib.redirect_stderr(error_buffer):
                    await async_func_to_run()
            else:
                # 関数が正しく定義されなかった場合のエラー
                raise RuntimeError(f"Failed to define or find the async wrapper function '{dynamic_async_func_name}'.")

            # 実行結果を取得
            output = output_buffer.getvalue()
            error_output = error_buffer.getvalue()

            return {
                "success": True,
                "output": output,
                "error_output": error_output
            }

        except Exception as e:
            # exec または await 中のエラーをキャプチャ
            error_message = str(e)
            tb_str = traceback.format_exc()
            # エラー発生前のエラー出力も取得しておく
            error_output_before_exception = error_buffer.getvalue()

            print(f"コード実行中にエラーが発生しました: {error_message}") # コンソールにもエラー表示

            return {
                "success": False,
                "error": error_message,
                "traceback": tb_str,
                # エラー発生前の標準エラー出力も返す
                "error_output": error_output_before_exception
            }

async def run_craft_example():
    """Skillsクラスのcraft_recipeメソッドを使用する例"""
    # Discoveryインスタンスを作成し、Skillsを初期化
    discovery = Discovery()
    await discovery.check_server_and_join()
    skills = discovery.skills
    # サーバーがアクティブか確認
    server_active = await discovery.check_server_active(timeout=15)
    if not server_active:
        print("サーバーに接続できません。終了します。")
        return
    
    code = """
# Let's move to the nearest 'oak_log' and collect 16 logs
go_to_result = await bot.go_to_nearest_block('oak_log')
if not go_to_result['success']:
    raise Exception(f"Failed to move to oak log: {go_to_result['message']}")

collect_result = await bot.collect_block('oak_log', 16)
collect_result"""
    while True:
        try:
            print(input("Enter: "))
            print(await discovery.get_skill_code('collect_block'))

            print(await discovery.execute_python_code(code))
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
            else:
                print("❌ Minecraftサーバーに接続できませんでした")
            return result
        
        asyncio.run(check_server_connection())
    else:
        # Skillsモードで実行
        print("Skillsモードで起動します...")
        asyncio.run(run_craft_example())