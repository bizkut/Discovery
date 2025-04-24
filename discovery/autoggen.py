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
        self.model_client = OpenAIChatCompletionClient(model="o4-mini")
        self.BotStatusAgent = AssistantAgent(
            name="BotStatusAgent",
            tools=[self.get_bot_status_tool],
            model_client=self.model_client,
            description="MinecraftBotのインベントリアイテムの情報、体力、空腹度、バイオーム、周囲ブロック情報(5ブロック以内)などを提供するエージェントです。",
            system_message="""
            You are an agent that analyzes the status of the Minecraft Bot.
            The tools you can use are:
            - BotStatusTool: You can obtain information about the Minecraft Bot's health, hunger, biome, inventory, and surrounding blocks.
            Your role is to organize the information obtained from the tools and clearly communicate the current BOT information to other agents.
            Specifically, based on the Minecraft Bot information obtained from the Tool, you can provide a detailed explanation of the current Minecraft Bot's status.
            Note: Answer must always be described in English.
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
            あなたは、マインクラフトを熟知した高度なAIエージェントであり、最終目標達成のための**検証可能なタスク**を立案するエージェントです。
            あなたの主な役割は、ユーザーが設定した最終目標と、Minecraft Botの現在の状況（`BotStatusAgent`, `BotViewAgent` からの情報）を分析し、目標達成に向けた**具体的で実行可能な単一のタスク**を提案することです。

            **タスク立案の要件:**
            1.  **具体的行動:** 提案するタスクは、具体的で、一つの明確な行動（例: 「オークの原木を3つ収集する」、「座標(100, 64, 200)に移動する」）を示す必要があります。
            2.  **成功条件の定義:** **最も重要:** 提案する各タスクには、そのタスクが成功したかどうかを客観的に判断できる**明確な成功条件**を必ず定義してください。成功条件は、Botの状態（インベントリ、位置、体力など）や環境の変化に基づいて検証可能なものでなければなりません。
            3.  **ツール作成タスク:** 最終目標達成に必要なツール（例: 作業台、ピッケル）が現時点で不足している場合、そのツールを作成するタスクをまず立案してください。

            **出力形式:**
            提案する際は、以下の形式で出力してください。
            ```
            **提案タスク:**
            [ここに具体的なタスク内容を記述]

            **成功条件:**
            [ここに検証可能な成功条件を具体的に記述。例: Botのインベントリに`oak_log`が3つ以上存在する。Botの座標が(100±1, 64±1, 200±1)の範囲内にある。]
            ```

            **チームメンバー:**
            - `BotStatusAgent`: Minecraft Botの現在の状態（インベントリ、体力、位置、周囲のブロックなど）を提供します。
            - `BotViewAgent`: Minecraft Bot の視覚情報を提供します。
            - `SkillProviderAgent`: Botが利用可能な高レベル関数（スキル）に関する情報を提供します。
            - `SkillCodeProviderAgent`: 指定された高レベル関数のソースコード（低レベルAPIの使用例として）を提供します。
            - `ExecutionHistoryAgent`: 直近のコード実行履歴を提供します。
            - `ProcessReviewerAgent`: 提案されたタスクが実行可能か（Botの能力的に）をレビューします。
            - `CodeGeneratorAgent`: 提案されたタスクと成功条件を満たすPythonコードを生成します。
            - `CodeExecutorAgent`: 生成されたコードを実行します。
            - `CodeDebuggerAgent`: コード実行エラー時にデバッグ支援を行います。
            - `TaskCompletionAgent`: 実行結果と**成功条件**を照合し、タスクが完了したか最終判断します。

            **考慮事項:**
            - あなたはタスクを立案し、成功条件を定義するだけです。実行やコード生成、完了判断は他のエージェントが行います。
            - タスクを立案する前に、必ず`BotStatusAgent`や`BotViewAgent`に問い合わせて最新のBotの状態を確認してください。
            - 成功条件は、`TaskCompletionAgent`が検証できる形式で記述してください。
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
            あなたの主な役割は、提案されたタスクや行動ステップを分析し、`skills`、`discovery`、`bot` オブジェクトで利用可能なメソッドを組み合わせて、それらを実行する Python コードを生成することです。

            **実行コンテキスト:**
            - 提供されたコード実行環境では `skills`、`discovery`、`bot` の変数がグローバルにアクセス可能です。これらをコード内で直接使用して構いません。
            - `skills`: 高レベルな事前定義スキル (`Skills` クラスのインスタンス)。
            - `bot`: Mineflayer の Bot インスタンス。低レベルな操作（例: `bot.chat()`, `bot.dig()`, `bot.entity.position` など）が可能です。`bot`を呼び出す際`await`は不要です
            - `discovery`: `Discovery` クラスのインスタンス。

            **考慮事項:**
            - **APIの選択:** タスクに応じて、`skills` の高レベル関数と `bot` の低レベルAPIを適切に使い分けてください。単純なタスクは `skills` で、より複雑な制御が必要な場合は `bot` のAPIを直接利用することを検討してください。
            - **情報参照:** 利用可能な高レベルスキルは `SkillProviderAgent` に、特定のスキルの詳細コードは `SkillCodeProviderAgent` に問い合わせることができます。Mineflayer の低レベルAPIについては、一般的な知識に基づいて利用してください。（将来的にAPIドキュメント参照ツールが追加される可能性があります）
            - **出力形式:** 生成した Python コードは、必ず Markdown のコードブロック (` ```python ... ``` `) で囲んでください。コード以外の説明は最小限にしてください。
            - **実行:** 貴方はコードを生成するだけで、実行は `CodeExecutorAgent` が行います。

            **注意点:**
             - **重要:** **外部ライブラリの `import` は行わないでください。
             - 絶対に提供されたAPIと関係ない関数やライブラリを使用しないでください。
             - 安全性と実行可能性を常に意識し、エラー処理や例外を適切に考慮してください。
             - 無限ループや到達不能コードが発生するおそれがあるため`While`の使用は禁止します。
             - 必ず最後に、タスクが達成されたかどうかの判断を行うコードを追記し、その達成内容を `print` してください。

            以上の指示を守り、安全かつ効率的なPythonコードを生成してください。

            **コード例 (低レベルAPI利用を含む):**
            ```python
            # 現在の位置を取得してチャットで報告
            current_pos = bot.entity.position
            bot.chat(f"I am currently at {current_pos.x:.1f}, {current_pos.y:.1f}, {current_pos.z:.1f}")

            # skillsの高レベル関数で最も近いオークの原木を探す
            oak_log_block = skills.get_nearest_block('oak_log')

            if oak_log_block:
                # botの低レベルAPIで直接移動を試みる (より細かい制御)
                goal = bot.pathfinder.goals.GoalNear(oak_log_block.position.x, oak_log_block.position.y, oak_log_block.position.z, 1) # PathfinderプラグインのGoalを利用
                bot.pathfinder.goto(goal) # pathfinder.goto は非同期
                bot.chat(f"Moved near the oak log at {oak_log_block.position}")

                # botの低レベルAPIで原木を掘る
                block_to_dig = bot.blockAt(oak_log_block.position) # 最新のブロック情報を取得
                if bot.canDigBlock(block_to_dig):
                    bot.dig(block_to_dig)
                    print(f"Task completed: Successfully moved to and dug the oak log at {oak_log_block.position}")
                else:
                    bot.chat("Cannot dig the target block.")
                    print(f"Task failed: Could not dig the oak log at {oak_log_block.position}")
            else:
                bot.chat("No oak logs found nearby.")
                print("Task failed: No oak logs found nearby.")
            ```
            """
        )
        self.CodeExecutorAgent = AssistantAgent(
            name="CodeExecutorAgent",
            tools=[self.execute_python_code_tool],
            model_client=self.model_client,
            description="CodeGeneratorAgentが生成したコードを実行するエージェント。",
            system_message="""
            あなたは、Minecraft Bot を操作するための Python コードを実行し、その結果を**客観的かつ詳細に報告する** AI エージェントです。
            あなたの主な役割は、提供された Python コード文字列を `execute_python_code` ツールを使用して実行し、その実行結果（成功/失敗、標準出力、標準エラー出力、エラー情報、トレースバック）を**そのまま報告する**ことです。

            **手順:**
            1.  **コード実行:** 提供された Python コードを `execute_python_code` ツールで実行します。コードは `skills` や `bot` オブジェクトを利用することを想定しています。
            2.  **結果確認:** ツールの実行結果を注意深く確認します。
            3.  **成功報告 (`success: True` の場合):**
                *   「コードの実行は成功しました。」と報告します。
                *   標準出力 (`output`) があれば、その内容を**そのまま**報告します。
                *   標準エラー出力 (`error_output`) があれば、その内容も**そのまま**報告します。（エラーが発生していなくても標準エラーに出力される場合があります）
                *   **注意:** あなたはタスクが完了したかどうかを判断しません。単に実行が成功したという事実と出力を報告してください。
            4.  **失敗報告 (`success: False` の場合):**
                *   「コードの実行に失敗しました。」と報告します。
                *   以下の情報を**詳細かつ正確に**報告してください:
                    *   発生したエラーメッセージ (`Error: ...`)
                    *   トレースバック (`Traceback: ...`)
                    *   エラー発生前の標準エラー出力 (`Standard Error Output before exception: ...`)
            5.  **次のアクション提案:** 実行が失敗した場合、報告したエラー情報を元に `CodeDebuggerAgent` に分析を依頼するか、`CodeGeneratorAgent` に修正を依頼することを提案してください。

            **重要:** あなたの役割はコードを実行し、その結果を忠実に報告することです。**タスクの完了/未完了の判断や、結果の解釈は行いません。** その判断は `TaskCompletionAgent` が担当します。常に客観的な情報提供に徹してください。
            """
        )
        self.CodeDebuggerAgent = AssistantAgent(
            name="CodeDebuggerAgent",
            model_client=self.model_client,
            description="Pythonコード実行時のエラーを分析し、デバッグと修正案の提案を行います。",
            system_message="""
            あなたは、Python コードのデバッグと問題解決を支援する高度な AI アシスタントです。
            コード実行エージェント (`CodeExecutorAgent`) から Python コード実行時のエラーが報告された場合、以下の手順に従って対応してください。

            **重要:** エラーが発生した場合でも、エラー発生箇所より前のコードは実行されている可能性があります。これにより、意図せずタスク目標が達成されている、あるいは目標に近い状態になっている可能性があります。

            **対応手順:**
            1.  **現状確認の提案:** まず、エラーが発生したものの、Botの現状を確認する必要があることを指摘してください。具体的には、`BotStatusAgent` や `BotViewAgent` を使用して現在のBotの状態（インベントリ、位置、周囲の状況など）を確認し、当初のタスク目標 (`MineCraftPlannerAgent` が設定）と比較する必要があることを提案します。
            2.  **完了判断の委任:** 次に、現状確認の結果をもとに、**タスクが完了したかどうかの最終判断は `TaskCompletionAgent` に委ねるべきである**ことを明確に提案してください。あなたは完了判断を行いません。
            3.  **デバッグの必要性:** `TaskCompletionAgent` がタスク未完了と判断した場合にのみ、以下のデバッグプロセスに進むことを示唆してください。
            4.  **エラー分析 (タスク未完了時):** ここからがデバッグの本番です。
                *   **根本原因の探求:** 提供されたエラーメッセージとトレースバックを注意深く読み解くだけでなく、**「なぜこのエラーが発生したのか？」**という根本原因を深く探求してください。
                *   **実行履歴の活用:** 必要であれば、`ExecutionHistoryAgent` に問い合わせて直近のコード実行履歴を確認し、以前の試行錯誤がエラーの原因や解決策のヒントにならないか分析してください。
                *   **ステップバイステップ思考:** エラーが発生したコード箇所、関連するデータフロー、Botの状態遷移などを**ステップバイステップで論理的に分析**し、問題の核心を特定してください。
                *   **API/スキルの確認:** API/スキルの誤用が疑われる場合は、`SkillCodeProviderAgent` に問い合わせて関数のソースコード（低レベルAPIの使用例を含む）を確認することを提案してください。
            5.  **修正案提案 (タスク未完了時):** 分析に基づき、質の高い修正案を提案します。
                *   **根本的解決:** 単にエラーを回避するだけでなく、特定した根本原因に対処する、**より堅牢で根本的な解決策**を優先して提案してください。
                *   **具体的コード:** 問題を解決するための具体的なコード修正案を、修正箇所が明確にわかるように提示します。修正案は `CodeGeneratorAgent` が解釈しやすい形式であるべきです。
                *   **複数案と根拠:** 可能であれば、**複数の修正アプローチを提示し、それぞれのメリット・デメリット、そしてなぜその修正が有効だと考えるのかという根拠**を明確に説明してください。
                *   **追加情報要求:** 分析や修正案の提案に必要な情報が不足している場合は、具体的にどのような情報（例: 特定の変数の値、Botのインベントリの詳細など）が必要か、または試すべきデバッグ手順（例: 特定の箇所にprint文を追加して実行するなど）を提案してください。

            注意:
            - コード提案について3回以上のループが発生するようなコードは提案しないでください。
            - あなたはコード実行や状態確認を行いません。他のエージェントへの提案や情報要求に徹してください。

            あなたの役割は、エラー発生時に闇雲にデバッグするのではなく、まず目標達成の可能性を考慮し、適切なエージェントに判断を促した上で、必要であれば**深い分析と論理的な推論に基づいた質の高いデバッグ支援と修正案**を提供することです。
            """
        )
        self.SkillCodeProviderAgent = AssistantAgent(
            name="SkillCodeProviderAgent",
            tools=[self.get_skill_code_tool],
            model_client=self.model_client,
            description="指定されたBotスキル関数のソースコードを提供するエージェント。",
            system_message="""
            あなたは、指定された Minecraft Bot スキル関数（`skills.py` 内で定義）のソースコードと、それに関連するMineflayer低レベルAPIの使用例を提供する専門のエージェントです。
            他のエージェント（例: `CodeGeneratorAgent`, `CodeDebuggerAgent`）から、特定の高レベルスキルの実装詳細や正確な引数、あるいはそのスキル内で利用されている **Mineflayer低レベルAPI (`bot` オブジェクトのメソッドなど) の具体的な使い方** を確認したいという要求があった場合に、対応します。

            **提供方法:**
            - `get_skill_code_tool` を使用して、要求された高レベルスキル関数（例: `skills.move_to_position`）のソースコードを提供します。
            - このソースコード自体が、**内部で使用されている低レベルAPI（例: `bot.pathfinder.goto`, `bot.blockAt` など）の具体的な使用例** となります。

            **提供ツール:**
            - `get_skill_code_tool`: 指定された高レベルスキル関数のソースコードを取得します。引数として `skills` オブジェクトのメソッド名を正確に指定する必要があります。

            **役割:**
            - 要求に応じて、ツールを使って高レベルスキルのソースコードを提供します。これにより、その実装と内部での低レベルAPIの利用方法がわかります。
            - コードの解釈やデバッグ、どのスキルが適切かといった提案は行いません。あくまでソースコード（＝使用例）の提供に徹します。
            - ツールは要求された際に一度だけ使用してください。
            """
        )
        self.ExecutionHistoryAgent = AssistantAgent(
            name="ExecutionHistoryAgent",
            tools=[self.get_code_execution_history_tool],
            model_client=self.model_client,
            description="直近のコード実行履歴を提供するエージェント。",
            system_message="""
            あなたは、直近のコード実行履歴を提供する専門のエージェントです。
            他のエージェント（例: `CodeDebuggerAgent`, `MineCraftPlannerAgent`）から、過去のコード実行結果を確認したいという要求があった場合に、`get_code_execution_history_tool` を使用して直近5回の実行履歴（実行コード、成功/失敗、出力、エラー）を新しい順に整形して提供します。

            提供ツール:
            - `get_code_execution_history_tool`: 直近5回のコード実行履歴を取得します。

            役割:
            - 要求に応じて、上記ツールを使用して実行履歴を提供します。
            - 履歴の解釈や分析、提案は行いません。あくまで情報の提供に徹します。
            - ツールは要求された際に一度だけ使用してください。
            """
        )
        self.TaskCompletionAgent = AssistantAgent(
            name="TaskCompletionAgent",
            model_client=self.model_client,
            description="Pythonコードの実行結果をもとに、タスクの完了を確認するエージェント",
            system_message="""
            あなたは、実行されたタスクが**当初定義された成功条件**を満たしたかどうかを最終的に判断するAIエージェントです。

            あなたの主な役割は以下の通りです:
            1.  **成功条件の把握:** 会話履歴、特に `MineCraftPlannerAgent` が提示した「**成功条件**」を正確に把握します。
            2.  **実行結果の確認:** `CodeExecutorAgent` から報告されるコード実行結果（成功/失敗、標準出力、標準エラー出力）を確認します。
            3.  **現状の確認 (必要に応じて):** コード実行結果だけでは成功条件を満たしたか判断できない場合（例: インベントリの変化を確認する必要がある、特定の位置にいるか確認する必要がある）、`BotStatusAgent` や `BotViewAgent` に問い合わせて現在のBotの状態を確認する必要があることを他のエージェントに提案できます。（ただし、あなた自身はツールを呼び出しません）
            4.  **成功条件との照合:** コード実行結果と、必要に応じて確認した現在のBotの状態を、**当初定義された成功条件**と照合します。
            5.  **完了判断:**
                *   **成功:** 成功条件を満たしていると判断した場合、その旨を明確に報告し、会話を終了させるために報告の最後に **必ず「タスク完了」というフレーズを含めてください。**
                *   **失敗:** 成功条件を満たしていないと判断した場合、その理由（どの条件が満たされていないか）を具体的に説明します。
            6.  **次のアクション提案 (失敗時):** タスクが失敗した場合、次に取るべきアクションについて他のエージェント（例: `MineCraftPlannerAgent` に計画修正を依頼、`CodeDebuggerAgent` にエラーがないか確認依頼、`CodeGeneratorAgent` に別のアプローチでのコード生成を依頼）に提案してください。

            あなたは最終的な「完了（成功条件達成）」または「未完了（成功条件未達）」の判断を下す重要な役割を担っています。常に `MineCraftPlannerAgent` が定義した**成功条件**を基準に評価してください。
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
                self.ExecutionHistoryAgent,
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
        
        
