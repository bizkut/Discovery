import copy
import json
import os
import time
from typing import Dict

import voyager.utils as U
from .env import VoyagerEnv

from .agents import ActionAgent
from .agents import CriticAgent
from .agents import CurriculumAgent
from .agents import SkillManager

class Voyager_devbox:
    def __init__(
        self,
        mc_port: int = None,
        mc_host: str = "host.docker.internal",
        azure_login: Dict[str, str] = None,
        server_port: int = 3000,
        server_host: str = "http://127.0.0.1",
        openai_api_key: str = None,
        env_wait_ticks: int = 1,
        env_request_timeout: int = 600,
        max_iterations: int = 160,
        reset_placed_if_failed: bool = False,
        action_agent_model_name: str = "gpt-4o-mini",
        action_agent_temperature: float = 0,
        action_agent_task_max_retries: int = 4,
        action_agent_show_chat_log: bool = True,
        action_agent_show_execution_error: bool = True,
        curriculum_agent_model_name: str = "gpt-4o-mini",
        curriculum_agent_temperature: float = 0,
        curriculum_agent_qa_model_name: str = "gpt-4o-mini",
        curriculum_agent_qa_temperature: float = 0,
        curriculum_agent_warm_up: Dict[str, int] = None,
        curriculum_agent_core_inventory_items: str = r".*_log|.*_planks|stick|crafting_table|furnace"
        r"|cobblestone|dirt|coal|.*_pickaxe|.*_sword|.*_axe",
        curriculum_agent_mode: str = "auto",
        critic_agent_model_name: str = "gpt-4o-mini",
        critic_agent_temperature: float = 0,
        critic_agent_mode: str = "auto",
        skill_manager_model_name: str = "gpt-4o-mini",
        skill_manager_temperature: float = 0,
        skill_manager_retrieval_top_k: int = 5,
        openai_api_request_timeout: int = 240,
        ckpt_dir: str = "ckpt",
        skill_library_dir: str = None,
        resume: bool = False,
    ):
        """
        Voyagerのメインクラス。
        Action agentは論文中の反復的プロンプトメカニズムです。
        Curriculum agentは論文中の自動カリキュラムです。
        Critic agentは論文中の自己検証です。
        Skill managerは論文中のスキルライブラリです。
        :param mc_port: マインクラフトのゲーム内ポート
        :param mc_host: マインクラフトのホスト名またはIP（Docker環境では通常"host.docker.internal"）
        :param azure_login: マインクラフトのログイン設定
        :param server_port: mineflayerのポート
        :param server_host: mineflayerのホスト（Docker環境では"http://127.0.0.1"を使用）
        :param openai_api_key: OpenAI APIキー
        
        :param env_wait_ticks: 各ステップの最後に待機するtick数。チャットログが欠けている場合はこの値を増やす必要があります
        :param env_request_timeout: 各ステップの待機秒数。コード実行がこの時間を超えた場合、Python側で接続を終了し、再開が必要になります
        :param reset_placed_if_failed: 失敗時に設置したブロックをリセットするかどうか。建築タスクに有用です
        :param action_agent_model_name: action agentのモデル名
        :param action_agent_temperature: action agentの温度
        :param action_agent_task_max_retries: 失敗時の最大リトライ回数
        :param curriculum_agent_model_name: curriculum agentのモデル名
        :param curriculum_agent_temperature: curriculum agentの温度
        :param curriculum_agent_qa_model_name: curriculum agent QAのモデル名
        :param curriculum_agent_qa_temperature: curriculum agent QAの温度
        :param curriculum_agent_warm_up: カリキュラムのヒューマンメッセージに表示される情報
        辞書内の値より完了タスクが多い場合に表示されます。利用可能なキー:
        {
            "context": int,
            "biome": int,
            "time": int,
            "other_blocks": int,
            "nearby_entities": int,
            "health": int,
            "hunger": int,
            "position": int,
            "equipment": int,
            "chests": int,
            "optional_inventory_items": int,
        }
        :param curriculum_agent_core_inventory_items: ウォームアップでoptional_inventory_itemsに到達する前に表示するアイテムのみ
        :param curriculum_agent_mode: "auto"で自動カリキュラム、"manual"で手動カリキュラム
        :param critic_agent_model_name: critic agentのモデル名
        :param critic_agent_temperature: critic agentの温度
        :param critic_agent_mode: "auto"で自動批評、"manual"で手動批評
        :param skill_manager_model_name: skill managerのモデル名
        :param skill_manager_temperature: skill managerの温度
        :param skill_manager_retrieval_top_k: 各タスクで取得するスキルの数
        :param openai_api_request_timeout: OpenAI APIの待機秒数
        :param ckpt_dir: チェックポイントディレクトリ
        :param skill_library_dir: スキルライブラリディレクトリ
        :param resume: チェックポイントから再開するかどうか
        """
        # init env
        self.env = VoyagerEnv(
            mc_port=mc_port,
            mc_host=mc_host,
            azure_login=azure_login,
            server_host=server_host,
            server_port=server_port,
            request_timeout=env_request_timeout,
        )
        self.env_wait_ticks = env_wait_ticks
        self.reset_placed_if_failed = reset_placed_if_failed
        self.max_iterations = max_iterations

        # set openai api key
        os.environ["OPENAI_API_KEY"] = openai_api_key

        # init agents
        self.action_agent = ActionAgent(
            model_name=action_agent_model_name,
            temperature=action_agent_temperature,
            request_timout=openai_api_request_timeout,
            ckpt_dir=ckpt_dir,
            resume=resume,
            chat_log=action_agent_show_chat_log,
            execution_error=action_agent_show_execution_error,
        )
        self.action_agent_task_max_retries = action_agent_task_max_retries
        self.curriculum_agent = CurriculumAgent(
            model_name=curriculum_agent_model_name,
            temperature=curriculum_agent_temperature,
            qa_model_name=curriculum_agent_qa_model_name,
            qa_temperature=curriculum_agent_qa_temperature,
            request_timout=openai_api_request_timeout,
            ckpt_dir=ckpt_dir,
            resume=resume,
            mode=curriculum_agent_mode,
            warm_up=curriculum_agent_warm_up,
            core_inventory_items=curriculum_agent_core_inventory_items,
        )
        self.critic_agent = CriticAgent(
            model_name=critic_agent_model_name,
            temperature=critic_agent_temperature,
            request_timout=openai_api_request_timeout,
            mode=critic_agent_mode,
        )
        self.skill_manager = SkillManager(
            model_name=skill_manager_model_name,
            temperature=skill_manager_temperature,
            retrieval_top_k=skill_manager_retrieval_top_k,
            request_timout=openai_api_request_timeout,
            ckpt_dir=skill_library_dir if skill_library_dir else ckpt_dir,
            resume=True if resume or skill_library_dir else False,
        )
        self.recorder = U.EventRecorder(ckpt_dir=ckpt_dir, resume=resume)
        self.resume = resume

        # init variables for rollout
        self.action_agent_rollout_num_iter = -1
        self.task = None
        self.context = ""
        self.messages = None
        self.conversations = []
        self.last_events = None

    def learn(self):
        # mineflyer サーバーの初期化
        if self.resume:
            # 再開時はインベントリを維持
            self.env.reset(
                options={
                    "mode": "soft",  # ソフトリセット：インベントリや位置情報を保持
                    "wait_ticks": self.env_wait_ticks,  # 環境が安定するまで待機するティック数
                }
            )
        else:
            # インベントリをクリア
            self.env.reset(
                options={
                    "mode": "hard",  # ハードリセット：すべての状態を初期化
                    "wait_ticks": self.env_wait_ticks,  # 環境が安定するまで待機するティック数
                }
            )
            self.resume = True  # 次回からはresumeモードとして扱う
        self.last_events = self.env.step("")  # 空のコマンドを実行してサーバー環境の現在の状態を取得
        print(f"self.last_events:\n{self.last_events}")
        print(f"self.action_agent.render_chest_observation:\n{self.action_agent.render_chest_observation()}")