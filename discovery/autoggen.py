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
        self.model_client = OpenAIChatCompletionClient(model="gpt-4o-mini")

        self.BotStatusAgent = AssistantAgent(
            name="BotStatusAgent",
            tools=[self.get_bot_status_tool],
            model_client=self.model_client,
            description="MinecraftBotのインベントリアイテムの情報、体力、空腹度、バイオーム、周囲ブロック情報(5ブロック以内)などを提供するエージェントです。",
            system_message="""
            あなたは、MineCraft Botの状態を分析するエージェントです。
            あなたが使えるツールは、
            - BotStatusTool: MineCraft Botの体力・空腹・バイオーム・インベントリ・周囲ブロック情報などを取得することが出来ます。
            貴方は、ツールから取得したMineCraft Botの情報を整理し、現在のBOTの情報をわかり易く他のエージェントに伝えることです。
            具体的には、Toolから得られたMineCraft Botの情報を下に、現在のMineCraft Botの状態を詳細に解説することが出来ます。
            注意: アイテムやブロック、バイオーム、ツール、エンティティは必ず英語で記述してください。
            """
        )
        self.BotViewAgent = AssistantAgent(
            name="BotViewAgent",
            tools=[self.capture_bot_view_tool],
            model_client=self.model_client,
            description="MinecraftのBotの視界情報を取得するエージェント。",
            system_message="""
            あなたは、MineCraft Botの視界情報を取得するエージェントです。
            あなたが使えるツールは、
            - CaptureBotViewTool: MineCraft Botの視界情報をyaml形式で取得することが出来ます。遠くの情報を取得する際有効です。
            貴方は、ツールから取得したMineCraft Botの情報を整理し、現在のBOTの情報をわかり易く他のエージェントに伝えることです。
            """
        )
        self.MineCraftPlannerAgent = AssistantAgent(
            name="MineCraftPlannerAgent",
            model_client=self.model_client,
            description="MinecraftのBotの状態をもとに、目標達成のためのタスクを立案するエージェント。",
            system_message="""
            あなたは、マインクラフトを熟知した高度なAIエージェントであり、目標達成のための具体的なタスクを立案するエージェントです。
            あなたの主な役割は、ユーザーが設定した目標と、Minecraft Botの現在の状況を分析し、最も最適なタスクを提案することです。
            設定した目標を達成するために必要なツールなどがある場合、そのツールを作成するタスクも含めて立案してください。

            チームメンバーは以下のとおりです。
            BotStatusAgent - Minecraft Botの現在の状態を提供します。
            BotViewAgent - Minecraft Bot の視覚情報を提供します。
            SkillProviderAgent - Botが利用可能な関数に関する情報を提供します。
            SkillCodeProviderAgent - 指定された関数のソースコードを提供します。
            ProcessReviewerAgent - 提案されたタスクがBOTのプログラムとして実行可能かを判断します。
            CodeGeneratorAgent - 提案されたタスクをPythonコードに変換します。
            CodeExecutorAgent - 提案されたタスクを実行します。
            CodeDebuggerAgent - 実行時のエラーを分析し、修正案を提案します。
            TaskCompletionAgent - タスクの進捗を判断します。
            
            考慮事項:
            - あなたはMineCraft Botの具体的なタスクを立案して委託するだけです - あなたはそれらを自分で実行できません。
            - あなたはタスクの進捗を判断することはできません。タスクの進捗はTaskCompletionAgentが行います。
            - タスクを立案するためには、MineCraft Botの現在の状態を確認することが必ず必要です。
            - 解答は、必ず日本語で行ってください。
            """
        )
        
        self.ProcessReviewerAgent = AssistantAgent(
            name="ProcessReviewerAgent",
            model_client=self.model_client,
            description="ActionDecomposerAgentが生成した行動ステップを実行するエージェント。提案されたタスクがPythonコードで実行可能な関数であるかを、Pythonコードで実行可能な関数のリストをもとに判断するエージェント。",
            system_message="""
            あなたは、提案されたタスクが、MineCraftBotにて実行可能かどうかを判断するエージェントです。
            他のエージェント（主に`MineCraftPlannerAgent`）から提案されたタスクを受け取り、Botが持つ能力（利用可能な関数）の観点からそのタスクが実行可能かどうかを評価します。
            もし利用可能な関数のリストが必要な場合は、`SkillProviderAgent` に問い合わせてください。
            
            評価のポイント:
            - 提案されたタスクが具体的で、Botの既存の機能で実現できるか？
            - 曖昧な点や、現状のBotの能力では実現不可能な点はないか？
            
            判断結果:
            - 実行可能と判断した場合: その旨を述べ、必要であればどの関数が使えそうかを簡潔に言及します。
            - 実行不可能と判断した場合: その理由（例: 対応する関数がない、タスクが曖昧すぎるなど）と、タスクをどのように修正すれば実行可能になるかの改善案を具体的に提案します。
            
            あなたは、タスクを達成するのに必要な関数を提案できるだけで、具体的なコードの生成はできません。(その役割は、CodeGeneratorAgentが行います)
            """
        )
        self.SkillProviderAgent = AssistantAgent(
            name="SkillProviderAgent",
            tools=[ self.get_skills_list_tool],
            model_client=self.model_client,
            description="Botが利用可能なPython関数（スキル）のリストや詳細を提供するエージェント。",
            system_message="""
            あなたは、Minecraft Botが利用可能なPython関数（スキル）に関する情報を提供する専門のエージェントです。
            他のエージェント（例: `ProcessReviewerAgent`, `CodeGeneratorAgent`）から、利用可能なスキルについて質問された際に、適切な情報を提供します。

            提供ツール:
            - `get_skills_list_tool`: 利用可能な関数の詳細なリスト（名前、説明、非同期フラグ、使用方法など）を取得します。特定の関数の使い方や引数を確認したい場合に利用します。

            役割:
            - 要求に応じて、上記ツールを使用してスキル情報を提供します。
            - 特定のタスクを実行するためにどのスキルが使えそうか、といった提案は行いません。あくまで情報の提供に徹します。
            - ツールは要求された際に一度だけ使用してください。
            """
        )
        self.CodeGeneratorAgent = AssistantAgent(
            name="CodeGeneratorAgent",
            model_client=self.model_client,
            description="提案されたタスクと、利用可能な関数から、Pythonのコードを生成するエージェント。",
            system_message="""
            あなたは、Minecraft Bot の操作を自動化するための Python コードを生成する専門のAIエージェントです。
            あなたの主な役割は、提案されたタスクや行動ステップを分析し、`discovery.skills` オブジェクトで利用可能なメソッドを組み合わせて、それらを実行する Python コードを生成することです。

            考慮事項:
            - 利用可能なスキル: `get_skills_list` ツールでスキルの一覧と説明を確認できます。必要であれば `get_skill_code` ツールで特定のスキルの詳細なソースコードと**正確な引数**を確認してください。
            - 非同期処理: スキルが非同期 (`Async: Yes`) の場合は、コード内で `await` を使用して呼び出す必要があります。
            - **重要:** **外部ライブラリの `import` は行わないでください。** 必要な機能は提供された `skills` オブジェクトを通じて利用してください。
            - 出力形式: 生成した Python コードは、必ず Markdown のコードブロック (` ```python ... ``` `) で囲んでください。コード以外の説明は最小限にしてください。
            - コード提案について回以上のループが発生するようなコードは提案しないでください。
            - 貴方はコードを生成するだけで、実行はCodeExecutorAgentが行います。

            コード例:
            ```python
            oak_log_block = skills.get_nearest_block('oak_log')
            if oak_log_block is None:
                spruce_log_block = skills.get_nearest_block('spruce_log')
                if spruce_log_block is None:
                    raise Exception("周囲に採取可能な原木が見つかりません。森林バイオームへの移動などを検討してください。")
                else:
                    target_block = spruce_log_block
                    target_block_name = 'spruce_log'
            else:
                target_block = oak_log_block
                target_block_name = 'oak_log'

            move_result = await skills.move_to_position(target_block.position.x, target_block.position.y, target_block.position.z, min_distance=1)
            ```
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
            3.  **成功報告:** コードの実行が成功した場合 (ツールの結果が "Code execution successful." で始まる場合)、その旨と、必要に応じて標準出力の内容を簡潔に報告してください。目標達成につながる場合は、その旨も言及してください。
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
            model_client=self.model_client,
            description="Pythonコード実行時のエラーを分析し、デバッグと修正案の提案を行います。",
            system_message="""
            あなたは、Python コードのデバッグと問題解決を専門とする高度な AI アシスタントです。
            コード実行エージェントから報告された Python コード実行時のエラー情報 (エラーメッセージ、トレースバック、実行されたコード) を詳細に分析し、問題の原因を特定し、具体的な修正案を提案してください。

            関数の詳細な実装や引数を確認する必要がある場合は、`SkillCodeProviderAgent` に問い合わせて関数のソースコードを取得してください。

            分析プロセス:
            1. 提供されたエラーメッセージとトレースバックを注意深く読み解きます。
            2. エラーが発生したコード箇所と、その周辺のロジックを確認します。
            3. 考えられるエラー原因を特定します (例: 変数名の誤り、型の不一致、API/スキルの誤用、前提条件の不足、論理的な誤りなど)。

            提案内容:
            - エラーの原因として最も可能性が高いものを明確に指摘します。
            - 問題を解決するための具体的なコード修正案を、修正箇所が明確にわかるように提示します。修正案は CodeGeneratorAgent が解釈しやすい形式であるべきです。
            - 修正案が複数考えられる場合は、それぞれのメリット・デメリットを説明します。
            - 情報が不足している場合や、原因の特定が困難な場合は、追加で確認すべき情報や試すべきデバッグ手順を提案します。
            
            注意:
            - コード提案について3回以上のループが発生するようなコードは提案しないでください。

            あなたの分析と提案は、問題解決の鍵となります。正確かつ建設的なフィードバックを提供してください。
            """
        )
        self.SkillCodeProviderAgent = AssistantAgent(
            name="SkillCodeProviderAgent",
            tools=[self.get_skill_code_tool],
            model_client=self.model_client,
            description="指定されたBotスキル関数のソースコードを提供するエージェント。",
            system_message="""
            あなたは、指定された Minecraft Bot スキル関数のソースコードを提供する専門のエージェントです。
            他のエージェントから特定のスキル関数の実装詳細や正確な引数を確認したいという要求があった場合に、`get_skill_code_tool` を使用して該当する関数のソースコードを提供します。

            提供ツール:
            - `get_skill_code_tool`: 指定されたスキル関数のソースコードを取得します。引数として関数名を正確に指定する必要があります。

            役割:
            - 要求されたスキル関数のソースコードをツールを使って取得し、そのまま提供します。
            - コードの解釈やデバッグ、提案は行いません。あくまでソースコードの提供に徹します。
            - ツールは要求された際に一度だけ使用してください。
            """
        )
        self.TaskCompletionAgent = AssistantAgent(
            name="TaskCompletionAgent",
            model_client=self.model_client,
            description="Pythonコードの実行結果をもとに、タスクの完了を確認するエージェント",
            system_message="""
            あなたは、Pythonコードの実行結果と会話の文脈全体を評価し、当初設定されたタスクが完了したかどうかを最終的に判断するAIエージェントです。

            あなたの主な役割は以下の通りです:
            1.  **実行結果の確認:** `CodeExecutorAgent` から報告されるコード実行結果（成功/失敗、標準出力、標準エラー出力）を確認します。
            2.  **目標との照合:** 会話履歴を参照し、`MineCraftPlannerAgent` が最初に設定したタスク目標や、その後の議論の流れを把握します。
            3.  **完了判断:** 実行結果が、当初のタスク目標を達成しているかを慎重に評価します。単にコードがエラーなく実行されただけでは不十分な場合があります。例えば、特定のアイテムを収集するタスクであれば、インベントリにそのアイテムが目標数だけ存在するかを確認する必要があります。
            4.  **完了報告:** タスクが完了したと判断した場合、その旨を明確に報告し、会話を終了させるために報告の最後に **必ず「タスク完了」というフレーズを含めてください。**
            5.  **未完了報告と提案:** タスクが完了していないと判断した場合、その理由を具体的に説明します（例: 実行は成功したが目標とする状態ではない、必要なアイテム数が足りない、予期せぬ状態になった等）。そして、次に取るべきアクションについて他のエージェント（例: `MineCraftPlannerAgent` に計画修正を依頼、`CodeGeneratorAgent` に別のアプローチでのコード生成を依頼）に提案してください。

            あなたは最終的な「完了」または「未完了」の判断を下す重要な役割を担っています。他のエージェントの報告を鵜呑みにせず、常に当初の目標達成という観点から状況を評価してください。
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
        """
        termination = TextMentionTermination("タスク完了")
        team = SelectorGroupChat(
            participants= [
                self.BotStatusAgent,
                self.BotViewAgent,
                self.MineCraftPlannerAgent,
                self.ProcessReviewerAgent,
                self.SkillProviderAgent,
                self.SkillCodeProviderAgent,
                self.CodeGeneratorAgent,
                self.CodeExecutorAgent,
                self.CodeDebuggerAgent,
                self.TaskCompletionAgent
            ],
            termination_condition=termination,
            model_client=self.model_client,
            selector_prompt=selector_prompt,
            allow_repeated_speaker=True,
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
            description="MineCraftBotの視界の情報を取得するツールです。BOT視点の情報を、YAML形式で返します。BOT視点からは遠くの景色も含めた情報を取得できます。"
        )
        self.get_skills_list_tool = FunctionTool(
            self.get_skills_list,
            description="MineCraftBotにて実行可能な全ての関数（メソッド）の名前、説明、非同期フラグのリストを取得するツールです。結果は、[{'name': 関数名, 'description': 説明, 'is_async': 非同期フラグ, 'usage': 使用方法}]のリスト形式で返します。全ての関数を取得するため大量のデータが返されます"
        )
        self.get_skill_code_tool = FunctionTool(
            self._get_skill_code_wrapper,
            description="指定されたMineCraftBotのスキル関数のソースコードを取得できるツールです。 (docstring除外)。スキル関数の詳細な動作や引数を確認したい場合に使用します。"
        )
        # Add the execute_python_code tool definition
        self.execute_python_code_tool = FunctionTool(
            self._execute_python_code_wrapper,
            description="指定されたPythonコード文字列を実行します。CodeGeneratorAgentが生成したコードを実行する際に使用します。引数には実行したいPythonコードを文字列として渡してください。"
        )
        # Add the new skill summary tool definition
        self.get_skill_summary_tool = FunctionTool(
            self._get_skill_summary_wrapper,
            description="Retrieves a concise list of available Minecraft Bot skill names and their brief descriptions (first line only). Useful for getting a quick overview of capabilities."
        )
    
    async def get_skills_list(self) -> str:
        """Skillsクラスで利用可能な関数の情報を取得し、LLMが読みやすい形式の英語文字列で返す"""
        skills_list = await self.discovery.get_skills_list() # 新しい形式のリストを取得

        if not skills_list:
            return "No available skills found."

        output_parts = ["Available Skills:"]
        for skill in skills_list:
            skill_name = skill.get('name', 'Unknown Name')
            description = skill.get('description', 'No description provided.').strip()
            usage = skill.get('usage', '-').strip() # Usageを取得

            skill_info = [
                f"{skill_name}",
                f"Description:",
                description,
                "", # DescriptionとUsageの間に空行
                f"Usage/Details:",
                usage # Args, Returns などを含む
            ]
            output_parts.append("\n".join(skill_info))

        # 各スキル情報を空行2つで区切る
        return "\n\n".join(output_parts)
    
    # Add the new wrapper method for skill summary
    async def _get_skill_summary_wrapper(self) -> str:
        """Retrieves only the names and descriptions of available skills, formatted concisely."""
        print("\033[34mTool:GetSkillSummary called\033[0m")
        skills_list = await self.discovery.get_skills_list()

        if not skills_list:
            return "No available skills found."

        output_lines = ["Available Skill Summaries:"]
        for skill in skills_list:
            skill_name = skill.get('name', 'Unknown Name')
            description = skill.get('description', 'No description provided.').strip()
            # Use only the first line of the description for brevity
            first_line_description = description.split('\n')[0]
            output_lines.append(f"- {skill_name}: {first_line_description}")

        return "\n".join(output_lines)
    
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
                prompt += "\n注意: 取得した視界情報はエミュレータから取得した視点であるため、天気や時間は反映されていません。また一部のエンティティのテクスチャがバグり、紫色になっていることがあります。"

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
                print("\033[34mスクリーンショットの内容をGPT-4oで分析し、YAML形式で記述しました。\033[0m")
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
        
    
        
