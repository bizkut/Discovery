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


# TODO: remove event memory
class Voyager:
    def __init__(
        self,
        mc_port: int = None,
        mc_host: str = "host.docker.internal",
        azure_login: Dict[str, str] = None,
        server_port: int = 3000,
        server_host: str = "http://127.0.0.1",
        openai_api_key: str = None,
        env_wait_ticks: int = 20,
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

    def reset(self, task, context="", reset_env=True):
        """
        エージェントを初期化し、新しいタスクを開始する準備をする関数
        環境のリセット、初期メッセージの設定を行う
        """
        # エージェントの試行回数をリセット
        self.action_agent_rollout_num_iter = 0
        
        # タスクとコンテキストを設定
        self.task = task
        self.context = context
        
        if reset_env:
            # 環境をソフトリセット
            self.env.reset(
                options={
                    "mode": "soft",
                    "wait_ticks": self.env_wait_ticks,
                }
            )
            
        # 難易度の設定（完了タスク数に応じて調整）
        difficulty = (
            "easy" if len(self.curriculum_agent.completed_tasks) > 15 else "peaceful"
        )
        
        # 時間設定と難易度設定のコマンドを実行
        events = self.env.step(
            "bot.chat(`/time set ${getNextTime()}`);\n"
            + f"bot.chat('/difficulty {difficulty}');"
        )
        
        # コンテキストに関連するスキルを取得
        skills = self.skill_manager.retrieve_skills(query=self.context)
        print(
            f"\033[33mアクションエージェントのシステムメッセージを{len(skills)}個のスキルで生成します\033[0m"
        )
        
        # システムメッセージとヒューマンメッセージを生成
        system_message = self.action_agent.render_system_message(skills=skills)
        human_message = self.action_agent.render_human_message(
            events=events, code="", task=self.task, context=context, critique=""
        )
        
        # メッセージを設定
        self.messages = [system_message, human_message]
        print(
            f"\033[32m****Action Agent human message****\n{human_message.content}\033[0m"
        )
        
        # メッセージが正しく設定されていることを確認
        assert len(self.messages) == 2
        
        # 会話履歴をクリア
        self.conversations = []
        return self.messages

    def close(self):
        self.env.close()

    def step(self):
        """
        エージェントの1ステップを実行する関数
        AIによるコード生成、実行、評価、次のステップの準備を行う
        """
        # エージェントが初期化されているか確認
        if self.action_agent_rollout_num_iter < 0:
            raise ValueError("Agent must be reset before stepping")
            
        # AIモデルからの応答を取得
        ai_message = self.action_agent.llm(self.messages)
        print(f"\033[34m****Action Agent ai message****\n{ai_message.content}\033[0m")
        
        # 会話履歴を保存
        self.conversations.append(
            (self.messages[0].content, self.messages[1].content, ai_message.content)
        )
        
        # AIメッセージからコードを抽出
        parsed_result = self.action_agent.process_ai_message(message=ai_message)
        success = False
        
        if isinstance(parsed_result, dict):
            # 有効なコードが生成された場合の処理
            
            # プログラムコードと実行コードを結合
            code = parsed_result["program_code"] + "\n" + parsed_result["exec_code"]
            
            # 環境内でコードを実行
            events = self.env.step(
                code,
                programs=self.skill_manager.programs,
            )
            
            # イベントを記録
            self.recorder.record(events, self.task)
            
            # チェストの内容を更新
            self.action_agent.update_chest_memory(events[-1][1]["nearbyChests"])
            
            # タスク成功の判定
            success, critique = self.critic_agent.check_task_success(
                events=events,
                task=self.task,
                context=self.context,
                chest_observation=self.action_agent.render_chest_observation(),
                max_retries=5,
            )

            if self.reset_placed_if_failed and not success:
                # タスク失敗時に設置したブロックを元に戻す処理
                blocks = []
                positions = []
                for event_type, event in events:
                    if event_type == "onSave" and event["onSave"].endswith("_placed"):
                        # 設置されたブロックの情報を収集
                        block = event["onSave"].split("_placed")[0]
                        position = event["status"]["position"]
                        blocks.append(block)
                        positions.append(position)
                        
                # 設置したブロックを回収するコードを実行
                new_events = self.env.step(
                    f"await givePlacedItemBack(bot, {U.json_dumps(blocks)}, {U.json_dumps(positions)})",
                    programs=self.skill_manager.programs,
                )
                
                # 最新のインベントリと地形情報で更新
                events[-1][1]["inventory"] = new_events[-1][1]["inventory"]
                events[-1][1]["voxels"] = new_events[-1][1]["voxels"]
                
            # 関連スキルの取得
            new_skills = self.skill_manager.retrieve_skills(
                query=self.context
                + "\n\n"
                + self.action_agent.summarize_chatlog(events)
            )
            
            # 次のステップのためのメッセージを準備
            system_message = self.action_agent.render_system_message(skills=new_skills)
            human_message = self.action_agent.render_human_message(
                events=events,
                code=parsed_result["program_code"],
                task=self.task,
                context=self.context,
                critique=critique,
            )
            
            # 最新のイベントとメッセージを保存
            self.last_events = copy.deepcopy(events)
            self.messages = [system_message, human_message]
        else:
            # コード生成に失敗した場合の処理
            assert isinstance(parsed_result, str)
            self.recorder.record([], self.task)
            print(f"\033[34m{parsed_result} Trying again!\033[0m")
            
        # メッセージが正しく設定されていることを確認
        assert len(self.messages) == 2
        
        # 試行回数をカウントアップ
        self.action_agent_rollout_num_iter += 1
        
        # 終了条件の判定（最大試行回数に達したか、タスク成功）
        done = (
            self.action_agent_rollout_num_iter >= self.action_agent_task_max_retries
            or success
        )
        
        # 結果情報の準備
        info = {
            "task": self.task,
            "success": success,
            "conversations": self.conversations,
        }
        
        if success:
            # タスク成功時はプログラム情報を追加
            assert (
                "program_code" in parsed_result and "program_name" in parsed_result
            ), "program and program_name must be returned when success"
            info["program_code"] = parsed_result["program_code"]
            info["program_name"] = parsed_result["program_name"]
        else:
            # タスク失敗時は次のメッセージを表示
            print(
                f"\033[32m****Action Agent human message****\n{self.messages[-1].content}\033[0m"
            )
            
        return self.messages, 0, done, info

    def rollout(self, *, task, context, reset_env=True):
        """
        タスクを完了するまでstep関数を繰り返し実行する関数
        タスクが成功するか最大試行回数に達するまで実行を続ける
        """
        # エージェントをリセットして新しいタスクを開始
        self.reset(task=task, context=context, reset_env=reset_env)
        
        # タスクが完了するまでステップを繰り返す
        while True:
            messages, reward, done, info = self.step()
            if done:
                break
        return messages, reward, done, info

    def learn(self, reset_env=True):
        """
        カリキュラムエージェントが生成したタスクを学習する関数
        タスクの生成、実行、スキルの保存を行う
        """
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

        # 学習ループの開始
        while True:
            # 最大イテレーション数に達したら学習を終了
            if self.recorder.iteration > self.max_iterations:
                print("イテレーション制限に到達しました")
                break
            
            # カリキュラムエージェントに次のタスクを提案させる
            task, context = self.curriculum_agent.propose_next_task(
                events=self.last_events,  # 最新の環境イベント
                chest_observation=self.action_agent.render_chest_observation(),  # チェストの内容
                max_retries=5,  # タスク提案の最大再試行回数
            )
            print(
                f"\033[35mタスク「{task}」を最大{self.action_agent_task_max_retries}回実行します\033[0m"
            )
            try:
                # タスクを実行（rollout関数を呼び出し）
                messages, reward, done, info = self.rollout(
                    task=task,  # 実行するタスク内容
                    context=context,  # カリキュラムエージェントが返したタスクのコンテキスト情報
                    reset_env=reset_env,  # 環境をリセットするかどうか
                )
            except Exception as e:
                time.sleep(3)  # mineflayerが終了するのを待つ
                info = {
                    "task": task,
                    "success": False,  # エラーが発生したため失敗とマーク
                }
                # エージェントの状態をリセット
                self.last_events = self.env.reset(
                    options={
                        "mode": "hard",  # ハードリセット
                        "wait_ticks": self.env_wait_ticks,  # 待機ティック数
                        "inventory": self.last_events[-1][1]["inventory"],  # 前回のインベントリを保持
                        "equipment": self.last_events[-1][1]["status"]["equipment"],  # 前回の装備を保持
                        "position": self.last_events[-1][1]["status"]["position"],  # 前回の位置を保持
                    }
                )
                # 赤色背景でエラーを表示
                print("Your last round rollout terminated due to error:")
                print(f"\033[41m{e}\033[0m")

            # タスクが成功した場合、新しいスキルとして追加
            if info["success"]:
                self.skill_manager.add_new_skill(info)  # スキルマネージャーに新しいスキルを追加

            # カリキュラムエージェントの探索進捗を更新
            self.curriculum_agent.update_exploration_progress(info)
            # 完了したタスクと失敗したタスクを表示
            print(
                f"\033[35mCompleted tasks: {', '.join(self.curriculum_agent.completed_tasks)}\033[0m"
            )
            print(
                f"\033[35mFailed tasks: {', '.join(self.curriculum_agent.failed_tasks)}\033[0m"
            )

        # 学習結果を返す
        return {
            "completed_tasks": self.curriculum_agent.completed_tasks,  # 完了したタスクのリスト
            "failed_tasks": self.curriculum_agent.failed_tasks,  # 失敗したタスクのリスト
            "skills": self.skill_manager.skills,  # 獲得したスキルのリスト
        }

    def decompose_task(self, task):
        if not self.last_events:
            self.last_events = self.env.reset(
                options={
                    "mode": "hard",
                    "wait_ticks": self.env_wait_ticks,
                }
            )
        return self.curriculum_agent.decompose_task(task, self.last_events)

    def inference(self, task=None, sub_goals=[], reset_mode="hard", reset_env=True):
        if not task and not sub_goals:
            raise ValueError("Either task or sub_goals must be provided")
        if not sub_goals:
            sub_goals = self.decompose_task(task)
        self.env.reset(
            options={
                "mode": reset_mode,
                "wait_ticks": self.env_wait_ticks,
            }
        )
        self.curriculum_agent.completed_tasks = []
        self.curriculum_agent.failed_tasks = []
        self.last_events = self.env.step("")
        while self.curriculum_agent.progress < len(sub_goals):
            next_task = sub_goals[self.curriculum_agent.progress]
            context = self.curriculum_agent.get_task_context(next_task)
            print(
                f"\033[35mStarting task {next_task} for at most {self.action_agent_task_max_retries} times\033[0m"
            )
            messages, reward, done, info = self.rollout(
                task=next_task,
                context=context,
                reset_env=reset_env,
            )
            self.curriculum_agent.update_exploration_progress(info)
            print(
                f"\033[35mCompleted tasks: {', '.join(self.curriculum_agent.completed_tasks)}\033[0m"
            )
            print(
                f"\033[35mFailed tasks: {', '.join(self.curriculum_agent.failed_tasks)}\033[0m"
            )
