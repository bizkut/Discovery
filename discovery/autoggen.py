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
from autogen_agentchat.ui import Console
from autogen_core import CancellationToken
from autogen_ext.models.openai import OpenAIChatCompletionClient
import autogen
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
        model_client = OpenAIChatCompletionClient(model="gpt-4o")

        self.BotStatusAgent = AssistantAgent(
            name="BotStatusAgent",
            tools=[self.get_bot_status_tool,self.capture_bot_view_tool],
            model_client=model_client,
            description="MinecraftのBotのインベントリ情報、周囲ブロック情報などをもとに、現在のBOTの状況を分析するエージェント。",
            system_message="""
            あなたは、Minecraftを熟知した親切なアシスタントです。ツールを使用してタスクを解決します。
            具体的には、ツールから得られたMineCraft Botの情報を下に、現在のMineCraft Botの状態を詳細に解説することが出来ます。
            """
        )
        self.MasterPlannerAgent = AssistantAgent(
            name="MasterPlannerAgent",
            model_client=model_client,
            description="MinecraftのBotの状態をもとに、目標達成のための計画を立案するエージェント。",
            system_message="""
            あなたは、マインクラフトを熟知した高度なAIエージェントの最上位プランナーです。
            あなたの主な役割は、ユーザーが設定した最終目標と、Minecraft Botの現在の状況を分析し、目標達成のための中〜高レベルのタスク計画を立案することです。
            中〜高レベルのタスクとは、個々のアクション（例：「1ブロック前に進む」「自座標よりy+10のブロック掘る」）ではなく、より抽象的な目標（例：「木材を10個集める」「作業台を作成する」「鉄のピッケルを作成する」）をリストアップし、目標達成のためのに絶対に必要な工程を立案することです。
            更に、設定した目標を達成するために必要なツールなどがある場合、そのツールを作成するタスクも含めて立案してください。
            """
        )
        self.ActionDecomposerAgent = AssistantAgent(
            name="ActionDecomposerAgent",
            model_client=model_client,
            description="MasterPlannerAgentが生成したタスクを元に、Minecraft Botが実行可能な具体的な行動ステップに分解するエージェント。",
            system_message="""
            あなたは、マインクラフトを熟知した高度なAIエージェントであり、提案されたタスクを達成するための具体的な行動ステップに分解するエージェントです。
            提案されたタスクを達成するために必要なアイテムやツールが不足している場合、それらを収集または作成するステップを追加してください。
            また、Minecraft Botの現在の状態を考慮し、安全な行動を提案してください。
            """
        )
        self.SkillExecutorAgent = AssistantAgent(
            name="SkillExecutorAgent",
            tools=[self.get_skills_list_tool],
            model_client=model_client,
            description="ActionDecomposerAgentが生成した行動ステップを実行するエージェント。",
            system_message="""
            あなたは、提案された行動が、MineCraftBotにて実行可能な関数（メソッド）であるかを判断し、実行ができない場合、行動ステップまたは目標の修正や改善を提案するエージェントです。
            具体的には、ツールから得られた実行可能関数のリストをもとに、提案された行動が実行可能な関数であるかを判断てください。また、提案された全ての行動が実行可能と判断した場合は、'タスク完了' というメッセージを出力してください。
            """
        )

        
    async def main(self,message:str) -> None:
        termination = TextMentionTermination("タスク完了")
        team = RoundRobinGroupChat(
            participants= [
                self.BotStatusAgent,
                self.MasterPlannerAgent,
                self.ActionDecomposerAgent,
                self.SkillExecutorAgent
            ],
            termination_condition=termination
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
            description="MineCraftBotにて実行可能な関数（メソッド）の名前、説明、非同期フラグのリストを取得するツールです。結果は、[{'name': 関数名, 'description': 説明, 'is_async': 非同期フラグ}]のリスト形式で返します。"
        )
    
    async def get_skills_list(self) -> str:
        """Skillsクラスで利用可能な関数（メソッド）の名前、説明、非同期フラグのリストを取得"""
        return str(await self.discovery.get_skills_list())
    
    async def get_bot_status(self) -> str:
        """MinecraftのBotのインベントリ情報、周囲ブロック情報などをもとに、現在のBOTの状況を分析する"""
        print("\033[34mTool:GetBotStatus が呼び出されました(BOTの状態を取得します)\033[0m")
        bot_status = await self.discovery.get_bot_status()
        return str(bot_status)

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
        
