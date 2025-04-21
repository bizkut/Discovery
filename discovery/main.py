from discovery import Discovery
from llm import LLMClient
import asyncio
import math
import inspect
import textwrap
import ast
import io # 標準出力/エラー出力キャプチャのため
import contextlib # redirect_stdout/stderrのため
import traceback # トレースバック取得のため

class DiscoveryMain:
    def __init__(self):
        # Discoveryインスタンスを作成
        self.discovery = Discovery()
        self.llm = LLMClient()
        self.skills = None

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
        is_active = await self.discovery.check_server_active(timeout=timeout)
        
        if is_active:
            print(f"✅ Minecraftサーバーは稼働中です！(バージョン: {self.discovery.bot.version})")
            
            # スキルのインスタンスを作成
            self.skills = self.discovery.create_skills()
            print("ボットが正常に召喚されました")
            return True
        else:
            print("❌ Minecraftサーバーに接続できませんでした")
            print("サーバーが起動しているか確認してください")
            return False

    async def get_bot_status(self):
        """ボットの状態と周辺情報（バイオーム、時間、体力、空腹度、エンティティ、インベントリ、ブロック分類）を取得"""
        if not self.discovery or not self.discovery.bot or not self.skills:
            print("エラー: ボットまたはスキルが初期化されていません。")
            return None
            
        try:
            # --- ボットの基本情報を取得 ---
            bot_entity = self.discovery.bot.entity
            bot_pos_raw = bot_entity.position # Y座標はエンティティ基準
            bot_health = self.discovery.bot.health
            bot_food = self.discovery.bot.food
            bot_time = self.discovery.bot.time.timeOfDay

            # ボットがいるブロックとバイオームを取得
            center_block = self.discovery.bot.blockAt(bot_pos_raw)
            #bottom_block = self.discovery.bot.blockAt(bot_pos_raw.offset(0, -1, 0))
            bot_pos = center_block.position.offset(0, 1, 0)
            bot_biome_id = self.discovery.bot.world.getBiome(bot_pos)
            bot_biome_name = self.discovery.mcdata.biomes[str(bot_biome_id)]['name']
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
        if self.skills is None:
            print("エラー: Skillsが初期化されていません")
            return None

        # skill_nameに対応するメソッドを取得
        try:
            method = getattr(self.skills, skill_name)
        except AttributeError:
            print(f"エラー: スキル関数 '{skill_name}' が見つかりません")
            return None

        # メソッドが呼び出し可能で、アンダースコアで始まらないことを確認
        if not callable(method) or skill_name.startswith('_'):
            print(f"エラー: スキル関数 '{skill_name}' が見つかりません、またはアクセスできません")
            return None

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

            # ClassDefのvisitは不要（メソッドのソースのみ取得するため）

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

            return code_without_docstring

        except (TypeError, OSError) as e:
            # ソースコードが取得できない場合
            print(f"エラー: スキル関数 '{skill_name}' のソースコードを取得できませんでした: {e}")
            return None
        except SyntaxError as e:
            # AST パース失敗時のエラーハンドリング
            print(f"エラー: スキル関数 '{skill_name}' のソースコードの解析に失敗しました: {e}")
            return None
        except AttributeError as e:
            # ast.unparse がない場合のエラー (Python 3.9未満)
            if "'module' object has no attribute 'unparse'" in str(e):
                 print("エラー: この機能にはPython 3.9以上が必要です (ast.unparse)。")
                 return None
            else:
                 print(f"エラー: 予期せぬエラーが発生しました: {e}")
                 return None

    async def execute_python_code(self, code_string: str):
        """渡されたPythonコード文字列を実行します（非同期対応）"""
        if not self.discovery or not self.discovery.bot or not self.skills:
            print("エラー: ボットまたはスキルが初期化されていません。")
            return {"success": False, "error": "Bot or skills not initialized", "traceback": "", "output": "", "error_output": ""}

        output_buffer = io.StringIO()
        error_buffer = io.StringIO()

        # 実行コンテキストに渡す変数 (botを追加)
        bot = self.discovery.bot # エイリアス
        skills = self.skills # エイリアス
        discovery = self.discovery # エイリアス
        exec_globals = {
            "asyncio": asyncio,
            "skills": skills,
            "discovery": discovery,
            "bot": bot,
            "__builtins__": __builtins__ # 安全のため、組み込み関数へのアクセスを許可
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

    async def run(self):
        """メイン実行関数"""
        # サーバー接続確認とボット召喚
        server_active = await self.check_server_and_join()
        
        if not server_active:
            print("サーバーに接続できないため、終了します")
            return
        
        # ボットのステータスを取得して表示（例）
        bot_status = await self.get_bot_status()
        if bot_status:
            print("\n--- Bot Status ---")
            for key, value in bot_status.items():
                print(f"{key}: {value}")
            print("------------------\n")
            
        # スキルリストを取得して表示（例）
        skills_list = await self.get_skills_list()
        if skills_list:
            print("\n--- Available Skills ---")
            for skill in skills_list:
                async_flag = "(async)" if skill['is_async'] else ""
                print(f"- {skill['name']}{async_flag}: {skill['description']}")
            print("----------------------\n")

        # 特定のスキルコードを取得して表示（例）
        skill_name_to_get = "get_inventory_counts" # 例として同期スキルを選択
        print(f"\n--- Code for skill '{skill_name_to_get}' ---")
        skill_code = await self.get_skill_code(skill_name_to_get)
        if skill_code:
            print(skill_code)
        print("-------------------------------------\n")

        # コード実行の例
        print("\n--- Executing Sync Code Example ---")
        sync_code = "print(f'Bot health: {bot.health}')\nprint(f'Inventory count: {len(skills.get_inventory_counts())}')"
        sync_result = await self.execute_python_code(sync_code)
        print(f"Execution Result: {sync_result}")
        print("------------------------------------\n")
        
        print("\n--- Executing Async Code Example ---")
        async_code = "await asyncio.sleep(0.2)\nprint(f'Bot position after wait: {bot.entity.position}')\nawait skills.move_to_position(bot.entity.position.x + 1, bot.entity.position.y, bot.entity.position.z, canDig=False)"
        async_result = await self.execute_python_code(async_code)
        print(f"Execution Result: {async_result}")
        print("-------------------------------------\n")

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
