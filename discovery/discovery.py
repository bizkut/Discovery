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
import collections
import base64
from playwright.async_api import async_playwright

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
        self.code_execution_history = collections.deque(maxlen=5)
        self.viewer = None
    
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
        # createBot 呼び出しがタイムアウトすることがあったため、タイムアウトを十分長く設定
        # (javascript.proxy の仕様で keyword 引数 `timeout` を与えると、JS 呼び出し待ち時間を延長できる)
        self.bot = self.mineflayer.createBot({
            "host": self.minecraft_host,
            "port": self.minecraft_port,
            "username": "BOT",
            "version": self.minecraft_version
        }, timeout=10000)  # 10 秒に延長
        
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
        
        # ビューアーを開く (初回のみ)
        if self.viewer is None:
            try:
                print(f"Starting Prismarine Viewer on port {self.prismarine_viewer_port}...")
                self.viewer = self.viewer_module.mineflayer(self.bot, {
                    "firstPerson": True,
                    "port": int(self.prismarine_viewer_port)
                })
                # ブラウザ自動起動はコメントアウト (必要なら解除)
                # webbrowser.open(f'http://localhost:{self.prismarine_viewer_port}')
                print(f"Prismarine Viewer started successfully.")
            except Exception as e:
                print(f"Failed to start Prismarine Viewer: {e}")
                self.viewer = None # 失敗したらNoneに戻す
        else:
            print("Prismarine Viewer already running.")
        
        # イベントリスナーを設定
        self.bot.once('spawn', handle_spawn)
        self.bot.on('error', handle_error)
        self.bot.on('end', handle_end)
        self.mcdata = require("minecraft-data")(self.bot.version)
        self.load_plugins()

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
        """ボットをサーバーから切断し、関連リソースを解放します。ボットが応答しない場合でも強制的に状態をリセットします。"""
        print("Disconnecting bot and releasing resources...")

        original_bot = self.bot
        original_viewer = self.viewer

        # 最初にPython側の状態をリセット
        self.bot = None
        self.is_connected = False
        self.viewer = None
        print("Internal bot state reset.")

        # --- クリーンアップ処理 (失敗しても続行) ---
        # 元のViewerを閉じる試み
        try:
            # hasattrもタイムアウトする可能性があるためtryブロック内に含める
            if original_viewer and hasattr(original_viewer, 'close'):
                original_viewer.close()
                print("Original Prismarine Viewer closed.")
        except Exception as e:
            print(f"Error closing original Prismarine Viewer (ignored): {e}")

        # 元のbotオブジェクトに関連付けられたviewerを閉じる試み
        try:
            # hasattrやプロパティアクセスもtryブロック内に含める
            if original_bot:
                bot_viewer = None
                # viewerプロパティへのアクセス試行もtry-except
                try:
                    if hasattr(original_bot, 'viewer'):
                         bot_viewer = original_bot.viewer
                except Exception as e_getattr:
                    print(f"Error accessing original_bot.viewer (ignored): {e_getattr}")

                # viewerオブジェクトのclose試行もtry-except
                try:
                    if bot_viewer and hasattr(bot_viewer, 'close'):
                        bot_viewer.close()
                        print("Original Prismarine Viewer (bot.viewer) closed.")
                except Exception as e_close:
                     print(f"Error closing bot_viewer (ignored): {e_close}")
        except Exception as e:
            # botオブジェクト自体へのアクセス等で予期せぬエラーが出た場合
            print(f"Error during bot.viewer cleanup (ignored): {e}")

        # 元のボットを切断する試み
        try:
            # hasattrもタイムアウトする可能性があるためtryブロック内に含める
            if original_bot and hasattr(original_bot, 'quit'):
                 print("Attempting to quit original bot instance...")
                 original_bot.quit()
                 print("Original bot instance quit command sent.")
        except Exception as e:
            print(f"Error quitting original bot instance (ignored): {e}")

        print("Bot disconnection process complete (cleanup attempted).")

    async def reconnect_bot(self, timeout=15):
        """
        ボットをサーバーから切断し、再接続を試みます。

        Args:
            timeout (int): 再接続時のタイムアウト秒数

        Returns:
            bool: 再接続が成功したらTrue、失敗したらFalse
        """
        print("ボットを再接続しています...")
        self.disconnect_bot() # 同期的に実行
        print("ボットを切断しました")

        # bot_join は同期的にボットの初期化を開始する
        self.bot_join()
        print("ボットを再接続しました")
        # check_server_active で接続完了を待つ (awaitを使用)
        print("再接続後のサーバー接続を確認しています...")
        return await self.check_server_active(timeout=timeout)

    async def get_bot_status(self, retry_count=0, max_retries=1):
        """ボットの状態と周辺情報（バイオーム、時間、体力、空腹度、エンティティ、インベントリ、ブロック分類）を取得"""
        # 接続状態とボットインスタンスの存在をより確実にチェック
        if not self.bot or not self.is_connected:
            print("エラー: ボットが接続されていないか、初期化されていません。")
            # 再接続を試みるロジックを追加することも検討できるが、ここではNoneを返す
            # raise Exception("ボットが接続されていないか、初期化されていません。")
            return None
        if not self.skills:
            print("エラー: スキルが初期化されていません。")
            # raise Exception("スキルが初期化されていません。")
            return None

        try:
            # --- ボットの基本情報を取得 --- 
            try:
                # entityへのアクセス前に再度接続を確認する（念のため）
                if not self.is_connected:
                     print("エラー: entityアクセス前に接続が切断されました。")
                     raise Exception("entityアクセス前に接続が切断されました。")
                bot_entity = self.bot.entity # ここでタイムアウトが発生する可能性がある
            except Exception as e:
                if "Timed out accessing 'entity'" in str(e) and retry_count < max_retries:
                    print(f"\033[93mエンティティへのアクセスがタイムアウトしました。再接続を試みます... (試行 {retry_count + 1}/{max_retries})\033[0m")
                    reconnected = await self.reconnect_bot()
                    if reconnected:
                        print("\033[92m再接続に成功しました。ステータス取得を再試行します。\033[0m")
                        # 再帰呼び出しでリトライカウントを増やす
                        return await self.get_bot_status(retry_count=retry_count + 1, max_retries=max_retries)
                    else:
                        print("\033[91m再接続に失敗しました。ステータス取得を中止します。\033[0m")
                        return None # 再接続失敗時はNoneを返す
                else:
                    # タイムアウト以外のエラー、またはリトライ上限超過
                    print(f"\033[91mエンティティ取得中に回復不能なエラーが発生しました（リトライ超過またはタイムアウト以外）: {e}\033[0m")
                    import traceback
                    traceback.print_exc()
                    return None # エラー時はNoneを返す

            # --- bot_entity を使用する以降の処理 --- 
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
            # _get_surrounding_blocks が await を必要とするか確認
            blocks = await self.skills._get_surrounding_blocks(
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
            inventory_info = await self.skills.get_inventory_counts()

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
            print(f"ボットステータスの取得中に予期せぬエラーが発生しました: {e}")
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
                docstring = inspect.cleandoc(method.__doc__) if method.__doc__ else ""
                description_lines = []
                usage_lines = []
                in_description = True
                section_headers = ("Args:", "Arguments:", "Parameters:", "Returns:", "Yields:", "Raises:", "Attributes:")

                if docstring:
                    lines = docstring.splitlines()
                    if lines:
                        description_lines.append(lines[0]) # 最初の行は必ずdescription
                        # 2行目以降を処理
                        for i in range(1, len(lines)):
                            line = lines[i]
                            stripped_line = line.strip()
                            # DescriptionとUsageの区切りを判定
                            if in_description and (not stripped_line or stripped_line.startswith(section_headers)):
                                in_description = False
                            
                            if in_description:
                                description_lines.append(line)
                            else:
                                usage_lines.append(line)

                description = "\n".join(description_lines).strip()
                usage = "\n".join(usage_lines).strip()
                if not description:
                    description = "説明がありません。"
                if not usage:
                    usage = "-" # Usageがない場合はハイフン

                # --- 関数シグネチャの取得 ---
                try:
                    source_lines = inspect.getsource(method).splitlines()
                    # 最初の 'def' または 'async def' の行を取得
                    signature_line = next((line for line in source_lines if line.strip().startswith(('def ', 'async def '))), None)
                    if signature_line:
                        # 末尾のコロンを除去
                        signature = signature_line.strip().rstrip(':')
                    else:
                        # 見つからない場合はフォールバック
                        signature = name
                except (TypeError, OSError):
                    # ソースコードが取得できない場合はフォールバック
                    signature = name
                # --- ここまで追加・変更 ---

                skill_list.append({
                    "name": signature, # name を signature に変更 (または両方含める)
                    "description": description, # 分割した説明
                    "usage": usage           # 分割した使い方
                })

        # 名前順にソートして返す (ソートキーも変更)
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
    
    async def execute_python_code(self, code_string: str, wrapper_func_name: str = "main"):
        """
        渡されたPythonコード文字列を、指定された名前の非同期関数内で実行します。
        デフォルトの関数名は 'main' です。
        """
        # Check if bot and skills are initialized correctly and bot is connected
        if not self.bot or not self.skills or not self.is_connected:
            error_msg = "エラー: ボットまたはスキルが初期化されていないか、サーバーに接続されていません。"
            print(error_msg)
            return {"success": False, "error": error_msg, "traceback": "", "output": "", "error_output": ""}

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

        # ユーザーコードを適切にインデント
        indented_user_code = textwrap.indent(code_string, '    ')

        # 非同期ラッパー関数のコード文字列を作成 (指定された関数名を使用)
        wrapper_code = f"""
import asyncio

async def {wrapper_func_name}():
{indented_user_code}
"""
        print(f"\033[32m{wrapper_code}\033[0m")

        try:
            # ラッパー関数を定義
            exec(wrapper_code, exec_globals)

            # 定義された非同期関数オブジェクトを取得 (指定された関数名を使用)
            async_func_to_run = exec_globals.get(wrapper_func_name)

            if async_func_to_run and inspect.iscoroutinefunction(async_func_to_run):
                with contextlib.redirect_stdout(output_buffer), contextlib.redirect_stderr(error_buffer):
                    await async_func_to_run()
            else:
                # 関数が正しく定義されなかった場合のエラー
                error_message = f"Failed to define or find the async wrapper function '{wrapper_func_name}'.\\n\\n{wrapper_code}"
                raise RuntimeError(error_message)

            # 実行結果を取得
            output = output_buffer.getvalue()
            error_output = error_buffer.getvalue()
            print(f"\033[32m{output}\033[0m")
            result = {
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

            print(f"\033[31mコード実行中にエラーが発生しました: {error_message}\nエラー詳細:{tb_str}\033[0m") # コンソールにもエラー表示

            result = {
                "success": False,
                "error": error_message,
                "traceback": tb_str,
                "error_output": error_output_before_exception
            }
        
        self.code_execution_history.append({"code": code_string, "result": result})
        
        return result

    async def get_screenshot_base64(self, direction: str | None = None, width: int = 960, height: int = 540) -> str | None:
        """
        指定された方角を向いてから Prismarine Viewer のスクリーンショットを取得し、
        Base64エンコードされた文字列として返します。

        Args:
            direction (str | None, optional): 向きたい方角 ('north', 'south', 'east', 'west', 'up', 'down' など)。Defaults to None.
            width (int): スクリーンショットの幅。
            height (int): スクリーンショットの高さ。

        Returns:
            str | None: Base64エンコードされたPNG画像文字列。エラー時はNone。
        """
        print(f"\033[34mCapturing screenshot from Prismarine Viewer (Direction: {direction or 'current'})...\033[0m")
        if not self.is_server_active():
            print("エラー: ボットが接続されていません。スクリーンショットを取得できません。")
            return None

        if direction:
            if self.skills: # skills オブジェクトが初期化されているか確認
                try:
                    print(f"\033[34mLooking towards {direction}...\033[0m")
                    look_result = await self.skills.look_at_direction(direction)
                    if not look_result or not look_result.get("success", False):
                         print(f"\033[93mWarning: Failed to look towards {direction}. Proceeding with current view. Message: {look_result.get('message', 'N/A') if look_result else 'N/A'}\033[0m")
                    await asyncio.sleep(1) # 視点変更が反映されるのを待つ
                except Exception as e:
                     print(f"\033[93mWarning: Error occurred while trying to look towards {direction}: {e}. Proceeding with current view.\033[0m")
            else:
                 print("\033[93mWarning: Skills object not initialized. Cannot change direction.\033[0m")

        url = f"http://localhost:{self.prismarine_viewer_port}"
        browser = None # finallyブロックで参照できるよう初期化
        try:
            async with async_playwright() as p:
                browser = await p.chromium.launch(headless=True)
                page = await browser.new_page(viewport={"width": width, "height": height})

                await page.goto(url, wait_until="load", timeout=60000) # タイムアウトを60秒に延長
                await page.wait_for_selector('canvas', timeout=30000) # canvasが現れるまで最大30秒待機
                # 描画安定のため十分な待機時間を確保
                await asyncio.sleep(5) # 必要に応じて調整

                screenshot_bytes = await page.screenshot(type="png")
                await browser.close() # スクリーンショット取得後すぐにブラウザを閉じる
                browser = None # クローズしたことを示す

                base64_image = base64.b64encode(screenshot_bytes).decode('utf-8')
                print("\033[34mScreenshot captured and encoded successfully.\033[0m")
                return base64_image

        except Exception as e:
            print(f"スクリーンショットの取得中にエラーが発生しました: {e}")
            import traceback
            traceback.print_exc()
            return None
        finally:
            if browser: # エラー発生時などでブラウザが開いたままの場合に閉じる
                 print("エラー発生のため、ブラウザをクローズします。")
                 await browser.close()

async def run_craft_example():
    """Skillsクラスのcraft_itemsメソッドを使用する例"""
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
async def main():
    # 最寄りの stone ブロックへ1ブロック以内まで移動
    await skills.go_to_nearest_block('stone', min_distance=1)

    # Botの現在位置と最寄りのstoneの座標を確認して、距離を計算して表示
    bot_pos = await skills.get_bot_position()
    nearest_stone = await skills.get_nearest_block('stone')
    print(nearest_stone.position.x)
await main()
"""
    while True:
        try:
            print(input("Enter: "))
            #await skills.move_to_position(76, 52, -110,0)
            print(await discovery.execute_python_code(code))
            #wait skills.move_to_position(67, 63, -11,0)
            #await skills.move_to_position(67, 63, -11,0)
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