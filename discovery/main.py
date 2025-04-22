from discovery import Discovery
from autoggen import Auto_gen
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
        self.auto_gen = Auto_gen(self.discovery)
        self.skills = None

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
        server_active = await self.discovery.check_server_and_join()
        
        if not server_active:
            print("サーバーに接続できないため、終了します")
            return
        await self.auto_gen.main(message="ダイヤを10個集めるために、行動を生成してください")

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
