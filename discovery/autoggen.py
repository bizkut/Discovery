import asyncio
import os
from langchain.prompts import PromptTemplate
import yaml
from discovery import Discovery
import base64
from playwright.async_api import async_playwright
from openai import AsyncOpenAI

from autogen_agentchat.agents import AssistantAgent
from autogen_agentchat.base import TaskResult
from autogen_agentchat.conditions import ExternalTermination, TextMentionTermination
from autogen_agentchat.teams import RoundRobinGroupChat
from autogen_agentchat.teams import SelectorGroupChat
from autogen_agentchat.ui import Console
from autogen_core import CancellationToken
from autogen_ext.models.openai import OpenAIChatCompletionClient
from autogen import Agent, ConversableAgent, UserProxyAgent, config_list_from_dotenv
from autogen.agentchat.contrib.capabilities.vision_capability import VisionCapability
from autogen.agentchat.contrib.img_utils import get_pil_image, pil_to_data_uri
from autogen.agentchat.contrib.multimodal_conversable_agent import MultimodalConversableAgent
from autogen.code_utils import content_str
from autogen_core.tools import FunctionTool

class Auto_gen:
    def __init__(self,discovery: Discovery) -> None:
        self.openai_api_key = os.getenv("OPENAI_API_KEY")
        self.gemini_api_key = os.getenv("GOOGLE_API_KEY")
        self.prompt_file_dir = "LLM/prompts"
        self.discovery = discovery

        self.load_tool()
        self.load_agents()

    def load_agents(self) -> None:
        self.model_client = OpenAIChatCompletionClient(model="gpt-4o")

        self.BotStatusAgent = AssistantAgent(
            name="BotStatusAgent",
            tools=[self.get_bot_status_tool,self.capture_bot_view_tool],
            model_client=self.model_client,
            description="MinecraftのBotのインベントリ情報、周囲ブロック情報などをもとに、現在のBOTの状況を分析するエージェント。",
            system_message="""
            あなたは、Minecraftを熟知した親切なアシスタントです。ツールを使用してタスクを解決します。
            具体的には、ツールから得られたMineCraft Botの情報を下に、現在のMineCraft Botの状態を詳細に解説することが出来ます。
            また、設定された'最終目標'について、Minecraft Botの状態を元に、'最終目標'が達成されたか評価することも出来ます。達成したと判断した場合は'タスク完了'というメッセージを返してください。
            """
        )
        self.MasterPlannerAgent = AssistantAgent(
            name="MasterPlannerAgent",
            model_client=self.model_client,
            description="MinecraftのBotの状態をもとに、目標達成のための計画を立案するエージェント。",
            system_message="""
            あなたは、マインクラフトを熟知した高度なAIエージェントの最上位プランナーです。
            あなたの主な役割は、ユーザーが設定した最終目標と、Minecraft Botの現在の状況を分析し、目標達成のための中〜高レベルのタスク計画を立案することです。
            中〜高レベルのタスクとは、個々のアクション（例：「1ブロック前に進む」「自座標よりy+10のブロック掘る」）ではなく、より抽象的な目標（例：「木材を10個集める」「作業台を作成する」「鉄のピッケルを作成する」）をリストアップし、目標達成のためのに絶対に必要な工程を立案することです。
            更に、設定した目標を達成するために必要なツールなどがある場合、そのツールを作成するタスクも含めて立案してください。
            また解答は、必ず日本語で行ってください。
            """
        )
        self.ActionDecomposerAgent = AssistantAgent(
            name="ActionDecomposerAgent",
            model_client=self.model_client,
            description="MasterPlannerAgentが生成したタスクを元に、Minecraft Botが実行可能な具体的な行動ステップに分解するエージェント。",
            system_message="""
            あなたは、マインクラフトを熟知した高度なAIエージェントであり、提案されたタスクを達成するための具体的な行動ステップに分解するエージェントです。
            提案されたタスクを達成するために必要なアイテムやツールが不足している場合、それらを収集または作成するステップを追加してください。
            また、Minecraft Botの現在の状態を考慮し、安全な行動を提案してください。
            """
        )
        self.ProcessReviewerAgent = AssistantAgent(
            name="ProcessReviewerAgent",
            tools=[self.get_skills_list_tool],
            model_client=self.model_client,
            description="ActionDecomposerAgentが生成した行動ステップを実行するエージェント。提案された行動がPythonコードで実行可能なスキルか判断し、必要であればスキルのコード情報、引数、動作を確認します。",
            system_message="""
            あなたは、提案された行動が、MineCraftBotにて実行可能な関数（メソッド）であるかを判断し、実行ができない場合、行動ステップまたは目標の修正や改善を提案するエージェントです。
            具体的には、ツールから得られた実行可能関数のリストをもとに、提案された行動が実行可能な関数であるかを判断てください。
            もし判断に迷う場合や、より詳細な情報が必要な場合は、get_skill_code ツールを使用して関数のソースコードを取得し、引数や動作を確認してください。
            """
        )
        self.CodeGeneratorAgent = AssistantAgent(
            name="CodeGeneratorAgent",
            tools=[self.get_skills_list_tool],
            model_client=self.model_client,
            description="提案された行動ステップから、スキル関数を元に、Pythonのコードを生成するエージェント。",
            system_message="""
            あなたは、Minecraft Bot の操作を自動化するための Python コードを生成する専門のAIエージェントです。
            あなたの主な役割は、提案されたタスクや行動ステップを分析し、`discovery.skills` オブジェクトで利用可能なメソッドを組み合わせて、それらを実行する Python コードを生成することです。

            考慮事項:
            - 利用可能なスキル: `get_skills_list` ツールでスキルの一覧と説明を確認できます。必要であれば `get_skill_code` ツールで特定のスキルの詳細なソースコードと**正確な引数**を確認してください。
            - 非同期処理: スキルが非同期 (`Async: Yes`) の場合は、コード内で `await` を使用して呼び出す必要があります。
            - **重要:** **外部ライブラリの `import` は行わないでください。** 必要な機能は提供された `skills` オブジェクトを通じて利用してください。
            - 出力形式: 生成した Python コードは、必ず Markdown のコードブロック (` ```python ... ``` `) で囲んでください。コード以外の説明は最小限にしてください。
            """
        )
        self.CodeExecutorAgent = AssistantAgent(
            name="CodeExecutorAgent",
            tools=[self.execute_python_code_tool],
            model_client=self.model_client,
            description="CodeGeneratorAgentが生成したコードを実行するエージェント。",
            system_message="""
            あなたは、Minecraft Bot を操作するための Python コードを実行し、その結果を報告する AI エージェントです。
            あなたの主な役割は、提供された Python コード文字列を `execute_python_code` ツールを使用して実行することです。

            手順:
            1.  **コード実行:** 提供された Python コードを `execute_python_code` ツールで実行します。コードは `skills`オブジェクトを利用することを想定しています。(例: `skills.collect_block('oak_log', 16)`)
            2.  **結果分析:** ツールの実行結果 (成功/失敗、標準出力、標準エラー出力、トレースバック) を注意深く確認します。
            3.  **成功報告:** コードの実行が成功した場合 (ツールの結果が "Code execution successful." で始まる場合)、その旨と、必要に応じて標準出力の内容を簡潔に報告してください。最終的な目標達成につながる場合は、その旨も言及してください。
            4.  **失敗報告:** コードの実行が失敗した場合 (ツールの結果が "Code execution failed." で始まる場合)、以下の情報を**詳細に**報告してください。
                *   発生したエラーメッセージ (`Error: ...`)
                *   トレースバック (`Traceback: ...`)
                *   エラー発生前の標準エラー出力 (`Standard Error Output before exception: ...`)
                *   可能であれば、エラーの原因についての簡単な考察や、コードのどの部分が問題かについての推測。
            5.  **次のアクション:** 実行が失敗した場合、エラー情報を元に `CodeGeneratorAgent` や他の関連エージェントにコードの修正を依頼するか、計画の見直しを提案してください。

            常に明確かつ正確な情報を提供し、問題解決に貢献してください。
            """
        )
        self.CodeDebuggerAgent = AssistantAgent(
            name="CodeDebuggerAgent",
            tools=[self.get_skill_code_tool],
            model_client=self.model_client,
            description="Pythonコード実行時のエラーを分析し、デバッグと修正案の提案を行います。",
            system_message="""
            あなたは、Python コードのデバッグと問題解決を専門とする高度な AI アシスタントです。
            コード実行エージェントから報告された Python コード実行時のエラー情報 (エラーメッセージ、トレースバック、実行されたコード) を詳細に分析し、問題の原因を特定し、具体的な修正案を提案してください。

            分析プロセス:
            1. 提供されたエラーメッセージとトレースバックを注意深く読み解きます。
            2. エラーが発生したコード箇所と、その周辺のロジックを確認します。
            3. 考えられるエラー原因を特定します (例: 変数名の誤り、型の不一致、API/スキルの誤用、前提条件の不足、論理的な誤りなど)。

            提案内容:
            - エラーの原因として最も可能性が高いものを明確に指摘します。
            - 問題を解決するための具体的なコード修正案を、修正箇所が明確にわかるように提示します。修正案は CodeGeneratorAgent が解釈しやすい形式であるべきです。
            - 修正案が複数考えられる場合は、それぞれのメリット・デメリットを説明します。
            - 情報が不足している場合や、原因の特定が困難な場合は、追加で確認すべき情報や試すべきデバッグ手順を提案します。

            あなたの分析と提案は、問題解決の鍵となります。正確かつ建設的なフィードバックを提供してください。
            """
        )
    async def main(self,message:str) -> None:
        selector_prompt = """あなたは優秀なリーダーとして、タスクを実行するエージェントを選択してください。

        {roles}

        現在の会話コンテキスト:
        {history}

        上記の会話を読み、{participants}の中から次のタスクを実行するエージェントを選択してください。
        プランナーエージェントが他のエージェントの作業開始前にタスクを割り当てていることを確認してください。
        エージェントは1つだけ選択してください。

        なお、以下のプロセスで選択することをおすすめします。
        1. BotStatusAgentでMinecraft Botの状態を確認する
        2. MasterPlannerAgentで目標達成のためのタスクを立案する
        3. ActionDecomposerAgentでタスクを具体的な行動ステップに分解する
        4. ProcessReviewerAgentで行動ステップが実行可能か確認する
        5. CodeGeneratorAgentで行動ステップをPythonコードに変換する
        6. CodeExecutorAgentでPythonコードを実行する
        7. BotStatusAgentでPythonコードでの実行後の状態を確認する
           - ActionDecomposerAgentが提案したタスクが、達成されたか評価する。達成されている場合は、次のステップに移る。
           - 達成されていない場合、CodeDebuggerAgentでエラーを分析し、修正案を提案する
           - 提案された修正案を元に、CodeGeneratorAgentでコードを修正する
           - 修正後、CodeExecutorAgentでコードを再実行する
           - コードを修正してもエラーが改善しない場合は、ProcessReviewerAgentで行動ステップの見直しを提案する。その際、タスクの見直しが必要な場合は、MasterPlannerAgentに相談を行う。
           - エラーがなく、目標が達成された場合、次のステップに移る。
        8. ActionDecomposerAgentが提案した次のタスクを実行するために4.から繰り返す。
        9. ActionDecomposerAgentが提案したタスクが全て達成された場合は、1.から繰り返す。
        """
        termination = TextMentionTermination("タスク完了")
        team = SelectorGroupChat(
            participants= [
                self.BotStatusAgent,
                self.MasterPlannerAgent,
                self.ActionDecomposerAgent,
                self.ProcessReviewerAgent,
                self.CodeGeneratorAgent,
                self.CodeExecutorAgent,
                self.CodeDebuggerAgent
            ],
            termination_condition=termination,
            model_client=self.model_client,
            selector_prompt=selector_prompt,
            allow_repeated_speaker=False,
        )
        await Console(
            team.run_stream(task=message)
        )
    
    def load_prompt_template(self, prompt_name: str) -> PromptTemplate:
        """指定されたプロンプト名のYAMLファイルをpromptsディレクトリから読み込み、PromptTemplateを返す"""
        prompt_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), self.prompt_file_dir)
        file_path = os.path.join(prompt_dir, f"{prompt_name}.yaml")
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                data = yaml.safe_load(f)
            
            # YAMLファイルに必要なキーが存在するか確認
            if not isinstance(data, dict) or "template" not in data or "input_variables" not in data:
                raise ValueError(f"YAMLファイル '{file_path}' の形式が不正か、'template' または 'input_variables' キーがありません。")

            # input_variables がリストであることを確認 (より厳密なチェック)
            if not isinstance(data["input_variables"], list):
                 raise ValueError(f"YAMLファイル '{file_path}' の 'input_variables' はリストである必要があります。")

            return PromptTemplate(
                template=data["template"],
                input_variables=data["input_variables"]
            )
        except Exception as e:
            print(f"プロンプト '{prompt_name}' の読み込み中に予期せぬエラーが発生しました: {e}")
            raise
    
    # ------- Tool -------
    def load_tool(self) -> None:
        self.get_bot_status_tool = FunctionTool(
            self.get_bot_status,
            description="MineCraftBotの状態を取得するツールです。辞書形式で、BOTの現在地、バイオーム、体力、空腹度、時間、近くの周辺ブロック情報、周囲のエンティティ情報、インベントリ情報を返します。"
        )
        self.capture_bot_view_tool = FunctionTool(
            self.capture_bot_view,
            description="MineCraftBotの視点の情報を取得するツールです。BOT視点の情報を、YAML形式で返します。BOT視点からは遠くの景色も含めた情報を取得できます。"
        )
        self.get_skills_list_tool = FunctionTool(
            self.get_skills_list,
            description="MineCraftBotにて実行可能な全ての関数（メソッド）の名前、説明、非同期フラグのリストを取得するツールです。結果は、[{'name': 関数名, 'description': 説明, 'is_async': 非同期フラグ}]のリスト形式で返します。"
        )
        self.get_skill_code_tool = FunctionTool(
            self._get_skill_code_wrapper,
            description="指定されたMineCraftBotのスキル関数のソースコードを取得します (docstring除外)。スキル関数の詳細な動作や引数を確認したい場合に使用します。"
        )
        # Add the execute_python_code tool definition
        self.execute_python_code_tool = FunctionTool(
            self._execute_python_code_wrapper,
            description="指定されたPythonコード文字列を実行します。CodeGeneratorAgentが生成したコードを実行する際に使用します。引数には実行したいPythonコードを文字列として渡してください。"
        )
    
    async def get_skills_list(self) -> str:
        """Skillsクラスで利用可能な関数（メソッド）の名前、説明、非同期フラグのリストを取得し、LLMが読みやすい形式の英語文字列で返す"""
        skills_list = await self.discovery.get_skills_list()
        
        if not skills_list:
            return "No available skills found."
        
        output_parts = ["Available Skills:"]
        for skill in skills_list:
            skill_name = skill.get('name', 'Unknown Name')
            is_async = skill.get('is_async', False)
            description = skill.get('description', 'No description').strip()
            async_str = "Yes" if is_async else "No"
            
            skill_info = [
                f"--- Skill: {skill_name} ---",
                f"Async: {async_str}",
                f"Description:",
                description
            ]
            output_parts.append("\n".join(skill_info))
            
        # Separate each skill info with two newlines
        return "\n\n".join(output_parts)
    
    async def _get_skill_code_wrapper(self, skill_name: str) -> str:
        """discovery.get_skill_codeのラッパーです。LLM用にフォーマットされた文字列を返します。"""
        print(f"\033[34mTool:GetSkillCode called for skill: {skill_name}\033[0m")
        result = await self.discovery.get_skill_code(skill_name)
        
        if result.get("success", False):
            code = result.get("message", "")
            return f"Source code for skill '{skill_name}':\n```python\n{code}\n```"
        else:
            error_message = result.get("message", "Unknown error")
            return f"Error getting source code for skill '{skill_name}': {error_message}"
    
    # Add the wrapper method for execute_python_code
    async def _execute_python_code_wrapper(self, code_string: str) -> str:
        """Wrapper for discovery.execute_python_code. Executes the code and returns formatted results for the LLM."""
        print(f"\033[34mTool:ExecutePythonCode called. Executing code:\n```python\n{code_string}\n```\033[0m")
        result = await self.discovery.execute_python_code(code_string)

        output_parts = []
        if result.get("success", False):
            output_parts.append("Code execution successful.")
            output = result.get("output", "").strip()
            error_output = result.get("error_output", "").strip()
            if output:
                output_parts.append("Standard Output:")
                output_parts.append("---")
                output_parts.append(output)
                output_parts.append("---")
            if error_output:
                output_parts.append("Standard Error Output:")
                output_parts.append("---")
                output_parts.append(error_output)
                output_parts.append("---")
            if not output and not error_output:
                 output_parts.append("(No output on stdout or stderr)")

        else:
            output_parts.append("Code execution failed.")
            error_message = result.get("error", "Unknown error")
            traceback_str = result.get("traceback", "No traceback available")
            error_output_before = result.get("error_output", "").strip()
            
            output_parts.append(f"Error: {error_message}")
            output_parts.append("Traceback:")
            output_parts.append("---")
            output_parts.append(traceback_str)
            output_parts.append("---")
            if error_output_before:
                output_parts.append("Standard Error Output before exception:")
                output_parts.append("---")
                output_parts.append(error_output_before)
                output_parts.append("---")

        return "\n".join(output_parts)
    
    async def get_bot_status(self) -> str:
        """Retrieves the bot's status from discovery and returns it as a formatted string for the LLM."""
        print("\033[34mTool:GetBotStatus called (Retrieving BOT status)\033[0m")
        bot_status_dict = await self.discovery.get_bot_status()

        if bot_status_dict is None:
            return "Could not retrieve bot status."

        output_lines = ["Bot Status:"]
        output_lines.append(f"- Biome: {bot_status_dict.get('biome', 'N/A')}")
        # Time of Day with explanation
        time_of_day = bot_status_dict.get('time_of_day', 'N/A')
        time_explanation = "  (Dawn: 0, Noon: 6000, Dusk: 12000, Night: 13000, Midnight: 18000, Sunrise: 23000)"
        output_lines.append(f"- Time of Day: {time_of_day} / 23992")
        output_lines.append(time_explanation)
        # Health and Hunger with max values
        health = bot_status_dict.get('health', 'N/A')
        hunger = bot_status_dict.get('hunger', 'N/A')
        output_lines.append(f"- Health: {health} / 20")
        output_lines.append(f"- Hunger: {hunger} / 20")
        output_lines.append(f"- Position: {bot_status_dict.get('bot_position', 'N/A')}")

        output_lines.append("\nNearby Blocks:")
        for direction in ["front", "right", "back", "left", "center"]:
            blocks = bot_status_dict.get(f"{direction}_blocks", [])
            blocks_str = ", ".join(blocks) if blocks else "None"
            output_lines.append(f"- {direction.capitalize()}: {blocks_str}")

        output_lines.append("\nNearby Entities:")
        entities = bot_status_dict.get('nearby_entities', [])
        if entities:
            for entity in entities:
                pos = entity.get('position', {})
                pos_str = f"x={pos.get('x', '?')}, y={pos.get('y', '?')}, z={pos.get('z', '?')}"
                output_lines.append(f"- {entity.get('name', 'Unknown')} at ({pos_str})")
        else:
            output_lines.append("- None nearby")

        output_lines.append("\nInventory:")
        inventory = bot_status_dict.get('inventory', {})
        if inventory:
            for item, count in inventory.items():
                output_lines.append(f"- {item}: {count}")
        else:
            output_lines.append("- Empty")

        return "\n".join(output_lines)

    async def capture_bot_view(self,attention_hint:str=None) -> str:
        """
        Prismarine Viewerのスクリーンショットを取得し、
        GPT-4oで内容を分析してYAML形式の文字列として返します。

        Args:
            attention_hint (str): 注意点を指定する文字列。

        Returns:
            str 画像の内容を表すYAML形式の文字列。エラー時は"None"。
        """
        width = 960
        height = 540
        print("\033[34mTool:CaptureBotView が呼び出されました(BOT視点の情報をGPT-4oで分析し、YAML形式で記述します)\033[0m")
        if not self.discovery.is_server_active():
            print("エラー: ボットが接続されていません。")
            return None

        url = f"http://localhost:{os.getenv('PRISMARINE_VIEWER_PORT', 3000)}"
        # OpenAI クライアントを初期化
        client = AsyncOpenAI(api_key=self.openai_api_key)

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
                data_url = f"data:image/png;base64,{base64_image}"

                prompt = "これはMinecraftゲームのスクリーンショットです。画像の内容を詳細に分析し、視界内にある重要なオブジェクト、ブロックの種類、MOB、脅威となる情報、その他 視界から得られる情報を階層的なYAML形式で記述してください。"
                if attention_hint is not None:
                    prompt += f"[{attention_hint}] の内容も含めてYAML形式で記述してください。"

                response = await client.chat.completions.create(
                    model="gpt-4o",
                    messages=[
                        {
                            "role": "user",
                            "content": [
                                {"type": "text", "text": prompt},
                                {
                                    "type": "image_url",
                                    "image_url": {"url": data_url},
                                },
                            ],
                        }
                    ],
                    max_tokens=1500, # YAML出力のために十分なトークン数を確保
                )
                yaml_output = response.choices[0].message.content
                # YAML出力が```yaml ... ```で囲まれている場合、中身だけ取り出す
                if yaml_output.startswith("```yaml\\n"):
                    yaml_output = yaml_output[len("```yaml\\n"):]
                if yaml_output.endswith("\\n```"):
                    yaml_output = yaml_output[:-len("\\n```")]
                
                return yaml_output.strip() # 前後の空白を削除

        except Exception as e:
            print(f"スクリーンショットの取得またはGPT-4o API呼び出し中にエラーが発生しました: {e}")
            import traceback
            traceback.print_exc()
            return "None"
        finally:
            if browser: # エラー発生時などでブラウザが開いたままの場合に閉じる
                 print("エラー発生のため、ブラウザをクローズします。")
                 await browser.close()
            # OpenAI AsyncClient には明示的な close は不要
        
    
        
