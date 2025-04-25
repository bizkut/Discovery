import asyncio
import os
from langchain.prompts import PromptTemplate
import yaml
from discovery import Discovery
from openai import AsyncOpenAI
from dotenv import load_dotenv

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
from autogen_core.models import ModelFamily

class Auto_gen:
    def __init__(self,discovery: Discovery) -> None:
        # Load environment variables from .env file
        load_dotenv()

        # Now os.getenv will work correctly if keys are in .env
        self.prompt_file_dir = "LLM/prompts"
        self.discovery = discovery

        self.load_tool()
        self.load_agents()

    def deepseek_client(self, model_name: str = "deepseek-reasoner") -> OpenAIChatCompletionClient:
        """Creates an OpenAIChatCompletionClient configured for DeepSeek models."""
        api_key = os.getenv("DEEPSEEK_API_KEY")
        if not api_key:
            raise ValueError("DEEPSEEK_API_KEY environment variable is not set.")

        # Based on DeepSeek API documentation and common capabilities
        model_info = {
            "vision": False,            # Assuming standard chat model, adjust if vision model is used
            "function_calling": True,   # Supported according to DeepSeek docs
            "json_output": True,        # Supported according to DeepSeek docs (check specific model if needed)
            "structured_output": False, # Assuming not directly supported via Pydantic models in this client
            "multiple_system_messages": True, # Assuming support, adjust if needed
            "family": ModelFamily.UNKNOWN # Add the required family field
        }

        client = OpenAIChatCompletionClient(
            model=model_name,
            api_key=api_key,
            base_url="https://api.deepseek.com", # From DeepSeek documentation
            model_info=model_info
        )
        return client
    
    def load_agents(self) -> None:
        self.model_client = OpenAIChatCompletionClient(model="gpt-4.1-2025-04-14")
        self.model_client_o1 = OpenAIChatCompletionClient(model="o1")
        #self.model_client_deepseek = self.deepseek_client(model_name="deepseek-reasoner")
        
        self.BotStatusAgent = AssistantAgent(
            name="BotStatusAgent",
            tools=[self.get_bot_status_tool],
            model_client=self.model_client,
            description="An agent that provides information about MinecraftBot's inventory items, health, hunger, biome, and surrounding block information (within 5 blocks).",
            system_message="""
            You are an agent that analyzes the status of the Minecraft Bot.
            The tools you can use are:
            - BotStatusTool: You can obtain information about the Minecraft Bot's health, hunger, biome, inventory, and surrounding blocks.
            Your role is to organize the information obtained from the tools and clearly communicate the current BOT information to other agents.
            Specifically, based on the Minecraft Bot information obtained from the Tool, you can provide a detailed explanation of the current Minecraft Bot's status.
            Note:
            - If the tool times out or does not respond, please request CodeExecutionAgent to execute `await skills.handle_connection_error()`.
            - You must always provide answers in English.
            """
        )
        self.BotViewAgent = AssistantAgent(
            name="BotViewAgent",
            tools=[self.capture_bot_view_tool],
            model_client=self.model_client,
            description="An agent that obtains visual information from the Minecraft Bot.",
            system_message="""
            You are an agent that obtains and analyzes the visual information from the Minecraft Bot.

            Main roles:
            - When instructed, use `capture_bot_view_tool` to capture screenshots of what the Bot sees and analyze the content in YAML format.
            - Particularly useful when checking distant information or wanting to know the situation in specific directions.

            Available tools:
            - `capture_bot_view_tool`: Obtains Bot's visual information in YAML format.
              - **Usage:**
                - `direction` (optional): Specify the direction to face before taking the screenshot (e.g., 'north', 'east', 'up', 'down'). If not specified, captures from current direction.
                - `attention_hint` (optional): Specify points of particular interest during analysis (e.g., "look for red sheep").

            Report format:
            - Please report the analysis results obtained from the tool directly in YAML format.
            - You must always provide answers in English.
            """
        )
        self.MissionPlannerAgent = AssistantAgent(
            name="MissionPlannerAgent",
            model_client=self.model_client,
            description="MinecraftのBotの状態をもとに、目標達成のためのタスクを立案するエージェント",
            system_message="""
            あなたは、マインクラフトを熟知した高度なAIエージェントであり、最終目標達成のための**検証可能なタスク**を立案するエージェントです。
            あなたの主な役割は、ユーザーが設定した最終目標と、Minecraft Botの現在の状況（`BotStatusAgent`, `BotViewAgent` からの情報）、そして**過去の実行履歴**を分析し、目標達成に向けた**具体的で実行可能な単一のタスク**を提案することです。

            **タスク立案の要件:**
            1.  **現状と履歴の確認:** 新しいタスクを立案する前に、**必ず**以下の情報を確認してください:
                *   `BotStatusAgent` や `BotViewAgent` に問い合わせて、最新のBotの状態（特にインベントリ、位置、周囲の状況）を確認する。
                *   `ExecutionHistoryAgent` に問い合わせて、直近の実行履歴を確認し、**特に直前のタスクが失敗したか、成功条件を満たさなかったか**を確認する。
            2.  **具体的行動:** 提案するタスクは、具体的で、一つの明確な行動（例: 「オークの原木を3つ収集する」、「座標(100, 64, 200)に移動する」）を示す必要があります。
            3.  **成功条件の定義:** **最も重要:** 提案する各タスクには、そのタスクが成功したかどうかを客観的に判断できる**明確な成功条件**を必ず定義してください。成功条件は、Botの状態（インベントリ、位置、体力など）や環境の変化に基づいて検証可能なものでなければなりません。
            4.  **ツール作成タスク:** 最終目標達成に必要なツール（例: 作業台、ピッケル）が現時点で不足している場合、そのツールを作成するタスクをまず立案してください。

            **タスク停滞時の対応:**
            - **停滞の判断:** 実行履歴を確認し、同じタスクで繰り返し失敗している、または成功条件達成に向けて進捗が見られない場合、タスクが**停滞**していると判断してください。
            - **戦略の見直し:** タスクが停滞している場合、単に同じタスクを再提案するのではなく、**戦略を見直し、異なるアプローチを検討してください。**
            - **代替案の提案:** 停滞を打破するために、以下のような代替案を検討し、提案してください:
                - **タスクの分解:** 問題となっているタスクを、より小さく、より管理しやすいステップに分解する。
                - **別のアプローチ:** 異なるスキルや低レベルAPIの組み合わせ、異なるリソース（場所、材料）の探索など、別の方法を試すタスクを提案する。
                - **追加情報収集:** `BotStatusAgent` や `BotViewAgent` を活用して、より詳細な情報（例: より広い範囲の探索、特定のブロックやエンティティの有無の確認）を収集するタスクを提案する。
                - **デバッグ依頼の示唆:** コードのエラーが原因で停滞している疑いが強い場合は、`CodeDebuggerAgent` に具体的な調査を依頼する必要があるかもしれない、と示唆する（ただし、プランナー自身はデバッグを行わない）。

            **出力形式:**
            提案する際は、以下の形式で出力してください。
            ```
            **提案タスク:**
            [ここに具体的なタスク内容を記述]

            **成功条件:**
            [ここに検証可能な成功条件を具体的に記述。例: Botのインベントリに`oak_log`が3つ以上存在する。Botの座標が(100±1, 64±1, 200±1)の範囲内にある。]
            ```

            **チームメンバー:**
            - `BotStatusAgent`: Minecraft Botの現在の状態を提供します。
            - `BotViewAgent`: Minecraft Bot の視覚情報を提供します。
            - `ProcessReviewerAgent`: タスクの実行可能性をレビューします。
            - `CodeExecutionAgent`: コードを生成、実行し、スキル情報も提供します。
            - `CodeDebuggerAgent`: コード実行エラー時にデバッグ支援を行い、実行履歴やスキルコードも確認します。
            - `TaskCompletionAgent`: タスクの完了判断を行います。

            **注意事項:**
            - あなたはタスクを立案し、成功条件を定義するだけです。
            - 実行やコード生成、完了判断は他のエージェントが行います。
            - 成功条件は、`TaskCompletionAgent`が検証できる形式で記述してください。
            - 解答は、必ず日本語で行ってください。
            """
        )
        self.ProcessReviewerAgent = AssistantAgent(
            name="ProcessReviewerAgent",
            tools=[self.get_skill_summary_tool],
            model_client=self.model_client,
            description="提案されたタスクが、利用可能な関数や現在のBotの状態で実行可能かをレビューするエージェント",
            system_message="""
            あなたは、提案されたタスクが、MineCraftBotにて実行可能かどうかを評価するエージェントです。
            他のエージェント（主に`MissionPlannerAgent`）から提案されたタスクを受け取り、Botが持つ能力（利用可能な関数）や現在の状況の観点からそのタスクが実行可能かどうかを評価します。

            **利用可能なツール:**
            - `get_skill_summary_tool`: 利用可能な高レベルスキル（関数）の名前と簡単な説明の一覧を取得します。

            **評価のポイント:**
            1.  **スキル確認:** 提案されたタスクを実行するために、どのようなスキルが必要になりそうか検討します。不明な点や、特定のスキルが存在するか確認したい場合は、**まず `get_skill_summary_tool` を使用して利用可能なスキルの概要を確認してください。**
            2.  **具体性:** 提案されたタスクは具体的か？ 既存のスキル（確認したスキルを含む）で実現可能か？
            3.  **前提条件:** タスク実行に必要なアイテム（材料、ツールなど）がBotのインベントリに存在するか、または現在の状況から入手可能か？ (必要であれば `BotStatusAgent` にインベントリを確認依頼してください)
            4.  **実現可能性:** 曖昧な点や、現状のBotの能力、持ち物、確認したスキルセットでは実現不可能な点はないか？

            **判断結果:**
            - **実行可能:** タスクが具体的で、必要なスキルが存在し、前提条件も満たされていると判断した場合、その旨を述べ、どのスキルが使えそうかを簡潔に言及します。
            - **実行不可能:** 提案されたタスクが曖昧すぎる、必要なスキルが見当たらない、前提条件が満たされていないなどの理由で実行不可能と判断した場合、**具体的な理由**（例: 「`collect_specific_flower`というスキルは存在しませんでした。」、「インベントリに鉄が不足しています。」）と、**タスクをどのように修正すれば実行可能になるかの改善案**を具体的に提案します。

            あなたは提案されたタスクのレビューと改善提案を行う役割です。**具体的なコードの生成や実行は行いません。** (その役割は、CodeExecutionAgentが行います)
            """
        )
        self.TaskCompletionAgent = AssistantAgent(
            name="TaskCompletionAgent",
            model_client=self.model_client,
            description="Pythonコードの実行結果をもとに、タスクの完了を確認するエージェント",
            system_message="""
            あなたは、実行されたタスクが**当初定義された成功条件**を満たしたかどうかを最終的に判断するAIエージェントです。

            あなたの主な役割は以下の通りです:
            1.  **成功条件の把握:** 会話履歴、特に `MissionPlannerAgent` が提示した「**成功条件**」を正確に把握します。
            2.  **実行結果の確認:** `CodeExecutionAgent` から報告されるコード実行結果（成功/失敗、標準出力、標準エラー出力）を確認します。
            3.  **最新状態の取得:** **必ず `BotStatusAgent` に問い合わせて、現在のBotの最新の状態（インベントリ、体力、位置など、成功条件の評価に必要な情報）を取得してください。** コード実行後のBotの状態は変化している可能性が高いため、このステップは必須です。
            4.  **成功条件との照合:** 取得した**最新のBot状態**と、`CodeExecutionAgent` からの**実行結果**を、**当初定義された成功条件**と照合します。
            5.  **完了判断:** 照合結果に基づいて、タスクが完了したか判断します。
                 *   **成功:** 成功条件を満たしていると判断した場合、その旨を明確に報告し、会話を終了させるために報告の最後に **必ず「タスク完了」というフレーズを含めてください。**
                 *   **失敗:** 成功条件を満たしていないと判断した場合、その理由（どの条件が満たされていないか、現在の状態はどうなっているか）を具体的に説明します。
            6.  **次のアクション提案 (失敗時):** タスクが失敗した場合、次に取るべきアクションについて他のエージェント（例: `MissionPlannerAgent` に計画修正を依頼、`CodeDebuggerAgent` にエラーがないか確認依頼、`CodeExecutionAgent` に別のアプローチでのコード生成を依頼）に提案してください。

            あなたは最終的な「完了（成功条件達成）」または「未完了（成功条件未達）」の判断を下す重要な役割を担っています。**判断前には必ず `BotStatusAgent` を呼び出して最新の状態を確認し**、常に `MissionPlannerAgent` が定義した**成功条件**を基準に評価してください。
            """
        )
        self.CodeExecutionAgent = AssistantAgent(
            name="CodeExecutionAgent",
            tools=[ # 必要なツールを追加
                self.execute_python_code_tool, 
                self.get_skill_summary_tool, 
                self.get_skills_list_tool
            ],
            model_client=self.model_client,
            description="提案されたタスクを実行するためのPythonコードを生成し、即座に実行して結果を報告するエージェント",
            system_message="""
            あなたは、Minecraft Bot の操作を自動化するための Python コードを生成し、**即座に実行してその結果を客観的に報告する**専門のAIエージェントです。
            あなたの役割は、提案されたタスクや行動ステップを分析し、`skills`、`bot` オブジェクトで利用可能なメソッドを組み合わせて Python コードを生成し、それを `execute_python_code` ツールで実行し、結果を報告することです。

            **実行コンテキスト:**
            - 提供されたコード実行環境では `skills`、`bot` の変数がグローバルにアクセス可能です。これらをコード内で直接使用して構いません。
            - `skills`: 高レベルな事前定義スキル (`Skills` クラスのインスタンス)。
            - `bot`: Mineflayer の Bot インスタンス。低レベルな操作（例: `bot.chat()`, `bot.dig()`, `bot.entity.position` など）が可能です。`bot`を呼び出す際`await`は不要です。

            **コード生成と実行のルール:**
            1.  **スキル確認 (重要):** コードを生成する**前**に、**必ず** `get_skill_summary_tool` または `get_skills_list_tool` を使用して、利用可能な高レベルスキル (`skills` オブジェクトのメソッド) を確認してください。これにより、最新かつ最適なスキルを選択し、存在しない関数を呼び出すエラーを防ぎます。
                - `get_skill_summary_tool`: スキル名と簡単な説明の一覧を素早く確認する場合に利用します。
                - `get_skills_list_tool`: 各スキルの詳細な説明や使い方（引数、戻り値など）を確認する場合に利用します。
            2.  **API選択:** タスクに応じて、確認した `skills` の高レベル関数と `bot` の低レベルAPIを適切に使い分けます。
            3.  **情報参照:** 特定のスキルの内部実装（低レベルAPIの使用例）を確認したい場合は、**`CodeDebuggerAgent` に問い合わせて** `get_skill_code_tool` を使用してもらうように依頼してください。（あなたはこのツールを直接呼び出せません）
            4.  **禁止事項:**
                - **外部ライブラリの `import` は行わないでください。**
                - 提供されたAPIと関係ない関数やライブラリは使用しないでください。
                - 無限ループ防止のため `while` の使用は禁止します。
            5.  **完了報告:** **必ずコードの最後に**、タスクが達成されたかどうかの判断材料となる情報を `print` するコードを含めてください。（例: `print(f"Collected {target_count} {item_name}.")`）
            6.  **コード実行:** 生成したコードは、Markdown コードブロックを使わずに、直接 `execute_python_code` ツールで実行します。
            7.  **非同期処理の待機:** `skills` オブジェクトのメソッドなど、`async def` で定義された非同期関数を呼び出す場合は、**必ず `await` を付けて呼び出してください。** (例: `await skills.collect_block(...)`)。これを忘れると、処理が完了する前にコードが終了してしまいます。

            **結果報告:**
            - `execute_python_code` ツールの実行結果（成功/失敗、標準出力、標準エラー出力、エラー情報、トレースバック）を**そのまま客観的に報告**してください。
            - **タスクの完了/未完了の判断や、結果の解釈は行いません。** その判断は `TaskCompletionAgent` が担当します。

            **エラー発生時の対応:**
            - 実行が失敗した場合（`success: False`）、報告されたエラー情報（エラーメッセージ、トレースバック、エラー発生前の標準エラー出力）を**詳細かつ正確に**報告してください。
            - その後、`CodeDebuggerAgent` に分析を依頼するか、`MissionPlannerAgent` に計画修正を依頼することを提案してください。

            **利用可能な主要スキル (`skills` オブジェクト) - 確認用の例:**
            (利用前には必ず `get_skill_summary_tool` or `get_skills_list_tool` で確認してください)
            *   `await skills.move_to_position(x, y, z, min_distance=2)`
            *   `await skills.collect_block(block_name, num=1)`
            *   `await skills.place_block(block_name, x, y, z)`
            *   `await skills.craft_items(item_name, num=1)`
            *   `skills.get_inventory_counts()`
            *   `skills.get_nearest_block(block_name, max_distance=1000)`
            *   `skills.get_bot_position()`
            *   `await skills.look_at_direction(direction)`
            *   `await skills.smelt_item(item_name, num=1)`
            *   `await skills.put_in_chest(item_name, num=-1)`
            *   `await skills.take_from_chest(item_name, num=-1)`
            """
        )

        self.CodeDebuggerAgent = AssistantAgent(
            name="CodeDebuggerAgent",
            tools=[ # 必要なツールを追加
                self.get_code_execution_history_tool,
                self.get_skills_list_tool,
                self.get_skill_code_tool
            ],
            model_client=self.model_client,
            description="コード実行エラーを分析し、実行履歴やスキル情報をツールで確認しながらデバッグと修正案の提案を行います",
            system_message="""
            あなたは、Python コードのデバッグと問題解決を支援する、**高度な分析能力を持つ** AI アシスタントです。
            `CodeExecutionAgent` から Python コード実行時のエラーが報告された場合、以下の手順に従ってデバッグを主導してください。

            **利用可能なツール:**
            - `get_code_execution_history_tool`: 直近5回のコード実行履歴（コード、結果、エラー）を取得します。
            - `get_skills_list_tool`: 利用可能な全スキル（高レベル関数）の詳細情報を取得します。
            - `get_skill_code_tool`: 指定したスキルのソースコード（低レベルAPIの使用例）を取得します。

            **重要:** エラーが発生した場合でも、エラー発生箇所より前のコードは実行されている可能性があります。これにより、意図せずタスク目標が達成されている、あるいは目標に近い状態になっている可能性があります。

            **対応手順:**
            1.  **現状確認の提案:** まず、エラーが発生したものの、Botの現状を確認する必要があることを指摘してください。具体的には、`CodeExecutionAgent` に対し `BotStatusAgent` や `BotViewAgent` を使用して現在のBotの状態（インベントリ、位置、周囲の状況など）を確認し、当初のタスク目標 (`MissionPlannerAgent` が設定）と比較するように依頼します。
            2.  **完了判断の委任:** 次に、現状確認の結果をもとに、**タスクが完了したかどうかの最終判断は `TaskCompletionAgent` に委ねるべきである**ことを明確に提案してください。あなたは完了判断を行いません。
            3.  **デバッグの必要性:** `TaskCompletionAgent` がタスク未完了と判断した場合にのみ、以下のデバッグプロセスに進むことを示唆してください。
            4.  **エラー分析 (タスク未完了時):** ここからがデバッグの本番です。あなたの高度な分析能力と利用可能なツールを最大限に活用してください。
                *   **根本原因の探求:** 提供されたエラーメッセージとトレースバックを注意深く読み解きます。
                *   **実行履歴の活用:** **必ず `get_code_execution_history_tool` を使用して** 直近の実行履歴を確認し、以前の試行錯誤、特に同様のエラーが繰り返されていないか、エラー直前の成功したステップは何かなどを分析してください。
                *   **スキル情報の活用:** 必要に応じて **`get_skills_list_tool` や `get_skill_code_tool` を使用して**、エラーに関連する可能性のあるスキルの詳細な仕様、引数、内部実装（低レベルAPIの使用例）を確認してください。APIの誤用や予期しない動作がないか分析します。
                *   **ステップバイステップ思考:** エラーが発生したコード箇所、関連するデータフロー、Botの状態遷移、ツールから得られた情報などを**統合的に分析**し、問題の核心を特定してください。
            5.  **修正案・調査手順の提案 (タスク未完了時):** 分析に基づき、質の高い修正案や調査手順を提案します。
                *   **根本的解決:** 単にエラーを回避するだけでなく、特定した根本原因に対処する、**より堅牢で根本的な解決策**を優先して提案してください。
                *   **修正指示/調査指示:** 問題を解決するための具体的なコード修正案や、試すべき調査手順（例: 特定の条件分岐を試すコード、別のスキルを使うコード、エラー箇所周辺に `print` 文を追加して特定の変数の値や状態を確認するコード）を明確に提示し、それを **`CodeExecutionAgent` に実行させるように指示**してください。修正案は `CodeExecutionAgent` が解釈しやすい形式であるべきです。
                *   **複数案と根拠:** 可能であれば、**複数の修正/調査アプローチを提示し、それぞれのメリット・デメリット、そしてなぜそれが有効だと考えるのかという根拠**を明確に説明してください。

            注意:
            - あなたは分析と指示に専念し、コードの直接実行やBotの状態確認は他のエージェントに依頼してください。
            - コード提案について3回以上のループが発生するような指示は避けてください。

            あなたの役割は、エラー発生時に闇雲にデバッグするのではなく、まず目標達成の可能性を考慮し、適切なエージェントに判断を促した上で、必要であれば**利用可能なツールを駆使した深い分析と論理的な推論に基づき、`CodeExecutionAgent` と連携して質の高いデバッグ**を主導することです。
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
                self.MissionPlannerAgent,
                self.ProcessReviewerAgent,
                self.CodeExecutionAgent,
                self.CodeDebuggerAgent,
                self.TaskCompletionAgent
            ],
            #termination_condition=termination,
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
            description="指定された方角を向いてからMineCraftBotの視界の情報を取得するツールです。BOT視点の情報を、YAML形式で返します。引数 `direction` で方角（例: 'north', 'east', 'up'）を指定できます。遠くの景色も含めた情報を取得できます。"
        )
        self.get_skills_list_tool = FunctionTool(
            self.get_skills_list,
            description="利用可能な全ての高レベルスキル（`skills`オブジェクトのメソッド）に関する**詳細情報**を取得します。各スキルについて、**完全なシグネチャ、詳細な説明、引数や戻り値を含む包括的な使用方法**を提供します。特定のスキルの詳細な理解が必要な場合や、利用可能な全オプションを詳細に調査したい場合に使用してください。注意: 全てのスキルを返すため、出力は長くなる可能性があります。"
        )
        self.get_skill_code_tool = FunctionTool(
            self._get_skill_code_wrapper,
            description="指定されたMineCraftBotのスキル関数のソースコードを取得できるツールです。 (docstring除外)。スキル関数の詳細な動作や引数を確認したい場合に使用します。"
        )
        # Add the execute_python_code tool definition
        self.execute_python_code_tool = FunctionTool(
            self._execute_python_code_wrapper,
            description="指定されたPythonコード文字列を実行します。CodeExecutionAgentが生成したコードを実行する際に使用します。引数には実行したいPythonコードを文字列として渡してください。"
        )
        # Add the new skill summary tool definition
        self.get_skill_summary_tool = FunctionTool(
            self._get_skill_summary_wrapper,
            description="利用可能な高レベルスキル（`skills`オブジェクトのメソッド）の**簡潔な概要**を取得します。各スキルについて**名前と短い（最初の行の）説明**のみをリストします。Botの能力の**全体像を素早く把握したい**場合や、詳細情報を`get_skills_list_tool`で要求する前に関連スキル候補を見つけたい場合に使用してください。"
        )
        # Add the new execution history tool definition
        self.get_code_execution_history_tool = FunctionTool(
            self._get_code_execution_history_wrapper,
            description="直近5回のコード実行履歴（実行コード、成功/失敗、出力、エラー）を新しい順に取得します。デバッグや計画の見直しに役立ちます。"
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

        output_lines.append("\nInventory Items:")
        inventory = bot_status_dict.get('inventory', {})
        if inventory:
            for item, count in inventory.items():
                output_lines.append(f"- {item}: {count}")
        else:
            output_lines.append("- Empty")

        return "\n".join(output_lines)

    # Add the wrapper method for capture_bot_view, including direction
    async def capture_bot_view(self, direction: str = 'north', attention_hint: str = None) -> str:
        """
        指定された方角を向いてからPrismarine Viewerのスクリーンショットを取得し、
        GPT-4oで内容を分析してYAML形式の文字列として返します。

        Args:
            direction (str, optional): スクリーンショットを撮る前に向く方角。(例:'north', 'south', 'east', 'west', 'up', 'down')
            attention_hint (str, optional): 分析時に特に注意してほしい点を記述する文字列。(例:'周辺の風景', 'MOB', '脅威となる情報')

        Returns:
            str 画像の内容を表すYAML形式の文字列。エラー時は"None"。
        """
        print(f"\033[34mTool:CaptureBotView が呼び出されました(Direction: {direction or 'current'}, Hint: {attention_hint or 'None'})\033[0m")

        # --- スクリーンショット取得処理を Discovery に移譲 (direction を渡す) ---
        base64_image = await self.discovery.get_screenshot_base64(direction=direction)
        if base64_image is None:
            print("エラー: スクリーンショットの取得に失敗しました。")
            return "None" # エラーを示す文字列を返す
        # --- ここまで変更 ---

        # OpenAI クライアントを初期化
        client = AsyncOpenAI(api_key=os.getenv("OPENAI_API_KEY"))
        

        try:
            data_url = f"data:image/png;base64,{base64_image}"

            prompt = "これはMinecraftゲームのスクリーンショットです。画像の内容を詳細に分析し、視界内にある重要なオブジェクト、ブロックの種類、MOB、脅威となる情報、その他 視界から得られる情報を階層的なYAML形式で記述してください。"
            # --- attention_hint をプロンプトに追加するロジックを復元 ---
            if attention_hint is not None:
                prompt += f"\n特に、[{attention_hint}] について詳しく記述してください。"
            prompt += "\n注意: 取得した視界情報はエミュレータから取得した視点であるため、天気や時間は反映されていません。また一部のエンティティのテクスチャがバグり、紫色になっていることがあります。"
            # --- ここまで復元 ---

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

    # Add the new wrapper method for execution history
    async def _get_code_execution_history_wrapper(self) -> str:
        """Retrieves the last 5 code execution history entries and formats them for the LLM."""
        print("\033[34mTool:GetCodeExecutionHistory called\033[0m")
        history = self.discovery.code_execution_history

        if not history:
            return "No code execution history available yet."

        output_parts = ["Code Execution History (most recent first):"]
        # Iterate in reverse to show newest first (deque stores oldest first)
        for i, entry in enumerate(reversed(history), 1):
            code = entry.get('code', 'N/A')
            result = entry.get('result', {})
            success = result.get('success', False)
            status = "Success" if success else "Failure"
            output = result.get('output', '').strip()
            error_output = result.get('error_output', '').strip()
            error_msg = result.get('error', '')
            traceback_str = result.get('traceback', '')

            entry_str = [
                f"--- Entry {i} ---",
                f"Status: {status}",
                "Executed Code:",
                "```python",
                code,
                "```"
            ]
            if output:
                entry_str.extend(["Standard Output:", "---", output, "---"])
            if error_output:
                entry_str.extend(["Standard Error Output:", "---", error_output, "---"])
            if not success:
                if error_msg:
                    entry_str.append(f"Error Message: {error_msg}")
                if traceback_str:
                    entry_str.extend(["Traceback:", "---", traceback_str, "---"])
            
            output_parts.append("\n".join(entry_str))

        # Join entries with double newline
        return "\n\n".join(output_parts)
        
        
