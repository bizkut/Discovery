from __future__ import annotations

import random
import re
import os
import shutil

import voyager.utils as U
from voyager.prompts import load_prompt
from voyager.utils.json_utils import fix_and_parse_json
from langchain_openai import ChatOpenAI, OpenAIEmbeddings
from langchain_core.messages import HumanMessage, SystemMessage
from langchain_community.vectorstores import Chroma


class CurriculumAgent:
    """Minecraftにおけるタスクのカリキュラムを管理するエージェント
    
    このエージェントは、プレイヤーの現在の状態や進捗に基づいて次に実行すべき
    タスクを提案し、タスクの成功/失敗を追跡します。また、Minecraftに関する
    質問応答（QA）機能も提供し、タスクの実行に役立つ情報を提供します。
    
    主な機能:
    - 環境の観察に基づく次のタスクの提案
    - タスクの成功/失敗の追跡と記録
    - Minecraftに関する質問応答
    - 複雑なタスクの分解
    """
    
    def __init__(
        self,
        model_name="gpt-3.5-turbo",
        temperature=0,
        qa_model_name="gpt-3.5-turbo",
        qa_temperature=0,
        request_timout=120,
        ckpt_dir="ckpt",
        resume=False,
        mode="auto",
        warm_up=None,
        core_inventory_items: str | None = None,
    ):
        """CurriculumAgentの初期化
        
        Args:
            model_name (str): タスク提案に使用する言語モデルの名前。デフォルトは"gpt-3.5-turbo"
            temperature (float): タスク提案モデルの温度パラメータ。デフォルトは0（決定論的な出力）
            qa_model_name (str): 質問応答に使用する言語モデルの名前。デフォルトは"gpt-3.5-turbo"
            qa_temperature (float): 質問応答モデルの温度パラメータ。デフォルトは0
            request_timout (int): APIリクエストのタイムアウト時間（秒）。デフォルトは120秒
            ckpt_dir (str): チェックポイントディレクトリのパス。デフォルトは"ckpt"
            resume (bool): 以前の状態から再開するかどうか。デフォルトはFalse
            mode (str): エージェントの動作モード。"auto"または"manual"。デフォルトは"auto"
            warm_up (Dict, optional): 観察情報の表示制御パラメータ
            core_inventory_items (str, optional): 基本的なインベントリアイテムを指定する正規表現
            
        Raises:
            AssertionError: サポートされていないモードが指定された場合
        """
        self.llm = ChatOpenAI(
            model_name=model_name,
            temperature=temperature,
            request_timeout=request_timout,
        )
        self.qa_llm = ChatOpenAI(
            model_name=qa_model_name,
            temperature=qa_temperature,
            request_timeout=request_timout,
        )
        assert mode in [
            "auto",
            "manual",
        ], f"mode {mode} not supported"
        self.mode = mode
        self.ckpt_dir = ckpt_dir
        
        # resume=Falseの場合、既存のckptディレクトリをクリーンアップ
        if not resume:
            curriculum_dir = f"{ckpt_dir}/curriculum"
            if os.path.exists(curriculum_dir):
                print(f"\033[33mCleaning up existing curriculum directory: {curriculum_dir}\033[0m")
                try:
                    shutil.rmtree(curriculum_dir)
                    print(f"\033[32mSuccessfully removed curriculum directory\033[0m")
                except Exception as e:
                    print(f"\033[31mFailed to remove curriculum directory: {e}\033[0m")
        
        # 必要なディレクトリ構造を作成
        U.f_mkdir(f"{ckpt_dir}/curriculum/vectordb")
        
        if resume:
            print(f"\033[35mLoading Curriculum Agent from {ckpt_dir}/curriculum\033[0m")
            self.completed_tasks = U.load_json(
                f"{ckpt_dir}/curriculum/completed_tasks.json"
            )
            self.failed_tasks = U.load_json(f"{ckpt_dir}/curriculum/failed_tasks.json")
            self.qa_cache = U.load_json(f"{ckpt_dir}/curriculum/qa_cache.json")
        else:
            self.completed_tasks = []
            self.failed_tasks = []
            self.qa_cache = {}
        # vectordb for qa cache
        self.qa_cache_questions_vectordb = Chroma(
            collection_name="qa_cache_questions_vectordb",
            embedding_function=OpenAIEmbeddings(),
            persist_directory=f"{ckpt_dir}/curriculum/vectordb",
        )
        assert self.qa_cache_questions_vectordb._collection.count() == len(
            self.qa_cache
        ), (
            f"Curriculum Agent's qa cache question vectordb is not synced with qa_cache.json.\n"
            f"There are {self.qa_cache_questions_vectordb._collection.count()} questions in vectordb "
            f"but {len(self.qa_cache)} questions in qa_cache.json.\n"
            f"Did you set resume=False when initializing the agent?\n"
            f"You may need to manually delete the qa cache question vectordb directory for running from scratch.\n"
        )
        # if warm up not defined, initialize it as a dict, else, initialize all the missing value as a default value
        if not warm_up:
            warm_up = self.default_warmup
        self.warm_up = {}
        if "optional_inventory_items" in warm_up:
            assert core_inventory_items is not None
            self._core_inv_items_regex = re.compile(core_inventory_items)
            self.warm_up["optional_inventory_items"] = warm_up[
                "optional_inventory_items"
            ]
        else:
            self.warm_up["optional_inventory_items"] = 0
        for key in self.curriculum_observations:
            self.warm_up[key] = warm_up.get(key, self.default_warmup[key])
        self.warm_up["nearby_blocks"] = 0
        self.warm_up["inventory"] = 0
        self.warm_up["completed_tasks"] = 0
        self.warm_up["failed_tasks"] = 0

    @property
    def default_warmup(self):
        return {
            "context": 15,
            "biome": 10,
            "time": 15,
            "nearby_blocks": 0,
            "other_blocks": 10,
            "nearby_entities": 5,
            "health": 15,
            "hunger": 15,
            "position": 0,
            "equipment": 0,
            "inventory": 0,
            "optional_inventory_items": 7,
            "chests": 0,
            "completed_tasks": 0,
            "failed_tasks": 0,
        }

    @property
    def curriculum_observations(self):
        return [
            "context",
            "biome",
            "time",
            "nearby_blocks",
            "other_blocks",
            "nearby_entities",
            "health",
            "hunger",
            "position",
            "equipment",
            "inventory",
            "chests",
            "completed_tasks",
            "failed_tasks",
        ]

    @property
    def progress(self):
        return len(self.completed_tasks)

    def render_system_message(self):
        system_message = SystemMessage(content=load_prompt("curriculum"))
        assert isinstance(system_message, SystemMessage)
        return system_message

    def render_observation(self, *, events, chest_observation):
        assert events[-1][0] == "observe", "Last event must be observe"
        event = events[-1][1]
        biome = event["status"]["biome"]
        time_of_day = event["status"]["timeOfDay"]
        voxels = event["voxels"]
        block_records = event["blockRecords"]
        entities = event["status"]["entities"]
        health = event["status"]["health"]
        hunger = event["status"]["food"]
        position = event["status"]["position"]
        equipment = event["status"]["equipment"]
        inventory_used = event["status"]["inventoryUsed"]
        inventory = event["inventory"]

        if not any(
            "dirt" in block
            or "log" in block
            or "grass" in block
            or "sand" in block
            or "snow" in block
            for block in voxels
        ):
            biome = "underground"

        other_blocks = ", ".join(
            list(
                set(block_records).difference(set(voxels).union(set(inventory.keys())))
            )
        )

        other_blocks = other_blocks if other_blocks else "None"

        nearby_entities = (
            ", ".join([k for k, v in sorted(entities.items(), key=lambda x: x[1])])
            if entities
            else "None"
        )

        completed_tasks = (
            ", ".join(self.completed_tasks) if self.completed_tasks else "None"
        )
        failed_tasks = ", ".join(self.failed_tasks) if self.failed_tasks else "None"

        # filter out optional inventory items if required
        if self.progress < self.warm_up["optional_inventory_items"]:
            inventory = {
                k: v
                for k, v in inventory.items()
                if self._core_inv_items_regex.search(k) is not None
            }

        observation = {
            "context": "",
            "biome": f"Biome: {biome}\n\n",
            "time": f"Time: {time_of_day}\n\n",
            "nearby_blocks": f"Nearby blocks: {', '.join(voxels) if voxels else 'None'}\n\n",
            "other_blocks": f"Other blocks that are recently seen: {other_blocks}\n\n",
            "nearby_entities": f"Nearby entities: {nearby_entities}\n\n",
            "health": f"Health: {health:.1f}/20\n\n",
            "hunger": f"Hunger: {hunger:.1f}/20\n\n",
            "position": f"Position: x={position['x']:.1f}, y={position['y']:.1f}, z={position['z']:.1f}\n\n",
            "equipment": f"Equipment: {equipment}\n\n",
            "inventory": f"Inventory ({inventory_used}/36): {inventory if inventory else 'Empty'}\n\n",
            "chests": chest_observation,
            "completed_tasks": f"Completed tasks so far: {completed_tasks}\n\n",
            "failed_tasks": f"Failed tasks that are too hard: {failed_tasks}\n\n",
        }
        return observation

    def render_human_message(self, *, events, chest_observation):
        content = ""
        observation = self.render_observation(
            events=events, chest_observation=chest_observation
        )
        if self.progress >= self.warm_up["context"]:
            questions, answers = self.run_qa(
                events=events, chest_observation=chest_observation
            )
            i = 1
            for question, answer in zip(questions, answers):
                if "Answer: Unknown" in answer or "language model" in answer:
                    continue
                observation["context"] += f"Question {i}: {question}\n"
                observation["context"] += f"{answer}\n\n"
                i += 1
                if i > 5:
                    break

        for key in self.curriculum_observations:
            if self.progress >= self.warm_up[key]:
                if self.warm_up[key] != 0:
                    should_include = random.random() < 0.8
                else:
                    should_include = True
                if should_include:
                    content += observation[key]

        print(f"\033[35m****Curriculum Agent human message****\n{content}\033[0m")
        return HumanMessage(content=content)

    def propose_next_task(self, *, events, chest_observation, max_retries=5):
        """環境の状態に基づいて次に実行すべきタスクを提案するメソッド
        
        現在の環境状態（イベント履歴、チェストの状態など）を分析し、
        エージェントの進捗状況に応じて適切な次のタスクとその実行コンテキストを提案します。
        
        特別なケース:
        1. 初回タスク（進捗が0）の場合は「木を1つ採取」というタスクを提案
        2. インベントリがほぼ満杯（33/36以上）の場合は、アイテムの整理タスクを提案
           - チェストが存在する場合: 不要なアイテムをチェストに預ける
           - チェストがない場合: チェストを作成または設置
        3. その他の場合: AIまたは手動で次のタスクを決定
        
        Args:
            events (List): 環境で発生したイベントのリスト
            chest_observation (str): チェストの観察情報
            max_retries (int): AIタスク提案の最大再試行回数。デフォルトは5
            
        Returns:
            Tuple[str, str]: タスク名とタスク実行のためのコンテキスト情報
            
        Raises:
            RuntimeError: AIタスク提案が最大再試行回数を超えて失敗した場合
            ValueError: 無効なモードが指定されている場合
        """
        if self.progress == 0 and self.mode == "auto":
            task = "wood logを1つ採取する"
            context = "oak, birch, spruce, jungle, acacia, dark oak, mangrove のいずれかの原木を採取できます。"
            return task, context

        # インベントリがほぼ満杯の場合の特別処理
        inventoryUsed = events[-1][1]["status"]["inventoryUsed"]
        if inventoryUsed >= 33:
            if chest_observation != "Chests: None\n\n":
                chests = chest_observation[8:-2].split("\n")
                for chest in chests:
                    content = chest.split(":")[1]
                    if content == " Unknown items inside" or content == " Empty":
                        position = chest.split(":")[0]
                        task = f"Deposit useless items into the chest at {position}"
                        context = (
                            f"預ける前のインベントリには{inventoryUsed}個のスロットが使用されています。"
                            "預けた後のインベントリは20個のスロットのみ使用するようにしてください。"
                            "andesite、dirt、cobblestoneなどの不要なアイテムを預けてください。"
                            "また、低レベルの道具も預けることができます。"
                            "例えば、stone pickaxeを持っている場合は、wooden pickaxeを預けることができます。"
                            "不要なアイテムのリストがインベントリにあることを確認してください"
                            "（チェストに既にあるアイテムはリストに含めないでください）。"
                            "bot.inventoryUsed()を使用して、使用されているインベントリスロットの数を確認できます。"
                        )
                        return task, context
            if "chest" in events[-1][1]["inventory"]:
                task = "Place a chest"
                context = (
                    f"インベントリにchestがあるので、周囲に設置してください。"
                    f"chestsがNoneでない、または近くのブロックにchestが含まれている場合、このタスクは成功です。"
                )
            else:
                task = "chest を1つ作成する"
                context = "任意の種類の wood planks 8個を使って chest を1つ作成してください。"
            return task, context

        messages = [
            self.render_system_message(),
            self.render_human_message(
                events=events, chest_observation=chest_observation
            ),
        ]

        if self.mode == "auto":
            return self.propose_next_ai_task(messages=messages, max_retries=max_retries)
        elif self.mode == "manual":
            return self.propose_next_manual_task()
        else:
            raise ValueError(f"Invalid curriculum agent mode: {self.mode}")

    def propose_next_ai_task(self, *, messages, max_retries=5):
        """AIを使用して次のタスクを提案するメソッド
        
        言語モデルにメッセージを送信し、返答からタスクを抽出します。
        エラーが発生した場合は、指定された回数まで再試行します。
        
        Args:
            messages (List): 言語モデルに送信するメッセージのリスト
            max_retries (int): 最大再試行回数。デフォルトは5
            
        Returns:
            Tuple[str, str]: タスク名とタスク実行のためのコンテキスト情報
            
        Raises:
            RuntimeError: 最大再試行回数を超えてもタスク提案に失敗した場合
        """
        if max_retries == 0:
            raise RuntimeError("Max retries reached, failed to propose ai task.")
        curriculum = self.llm(messages).content
        print(f"\033[31m****Curriculum Agent ai message****\n{curriculum}\033[0m")
        try:
            response = self.parse_ai_message(curriculum)
            assert "next_task" in response
            context = self.get_task_context(response["next_task"])
            return response["next_task"], context
        except Exception as e:
            print(
                f"\033[35mError parsing curriculum response: {e}. Trying again!\033[0m"
            )
            return self.propose_next_ai_task(
                messages=messages,
                max_retries=max_retries - 1,
            )

    def parse_ai_message(self, message):
        """AIからの応答メッセージからタスク情報を抽出するメソッド
        
        AIの応答テキストを解析し、「Task:」で始まる行からタスク名を抽出します。
        
        Args:
            message (str): AIからの応答メッセージ
            
        Returns:
            Dict: 抽出されたタスク情報を含む辞書（"next_task"キーにタスク名）
            
        Raises:
            AssertionError: タスクが見つからなかった場合
        """
        task = ""
        for line in message.split("\n"):
            if line.startswith("Task:"):
                task = line[5:].replace(".", "").strip()
        assert task, "Task not found in Curriculum Agent response"
        return {"next_task": task}

    def propose_next_manual_task(self):
        """ユーザー入力によって次のタスクを提案するメソッド
        
        ユーザーにタスク名とコンテキスト情報の入力を求め、
        確認後にそれらの情報を返します。
        
        Returns:
            Tuple[str, str]: タスク名とタスク実行のためのコンテキスト情報
        """
        confirmed = False
        task, context = "", ""
        while not confirmed:
            task = input("Enter task: ")
            context = input("Enter context: ")
            print(f"Task: {task}\nContext: {context}")
            confirmed = input("Confirm? (y/n)").lower() in ["y", ""]
        return task, context

    def update_exploration_progress(self, info):
        """タスクの実行結果に基づいて進捗状況を更新するメソッド
        
        タスクの成功/失敗情報に基づいて、完了タスクまたは失敗タスクのリストを更新し、
        その情報をディスクに保存します。特定のタスク（チェストへのアイテム預け入れなど）は
        記録から除外されます。
        
        Args:
            info (Dict): タスク実行の結果情報
                - "task": タスク名
                - "success": タスクが成功したかどうかのブール値
        """
        task = info["task"]
        if task.startswith("Deposit useless items into the chest at"):
            # No need to record the deposit task
            return
        if info["success"]:
            print(f"\033[35mCompleted task {task}.\033[0m")
            self.completed_tasks.append(task)
        else:
            print(
                f"\033[35mFailed to complete task {task}. Skipping to next task.\033[0m"
            )
            self.failed_tasks.append(task)

        # clean up tasks and dump to disk
        self.clean_up_tasks()

    def clean_up_tasks(self):
        """タスクリストを整理し、ディスクに保存するメソッド
        
        このメソッドは以下の処理を行います：
        1. 完了タスクリストから重複を削除（順序は保持）
        2. 失敗タスクリストから完了済みのタスクを削除
        3. 更新されたタスクリストをJSONファイルとして保存
        
        これにより、タスクの進捗状況が一貫して管理され、
        チェックポイントから再開する際に正確な状態が復元されます。
        """
        updated_completed_tasks = []
        # record repeated failed tasks
        updated_failed_tasks = self.failed_tasks
        # dedup but keep order
        for task in self.completed_tasks:
            if task not in updated_completed_tasks:
                updated_completed_tasks.append(task)

        # remove completed tasks from failed tasks
        for task in updated_completed_tasks:
            while task in updated_failed_tasks:
                updated_failed_tasks.remove(task)

        self.completed_tasks = updated_completed_tasks
        self.failed_tasks = updated_failed_tasks

        # dump to json
        U.dump_json(
            self.completed_tasks, f"{self.ckpt_dir}/curriculum/completed_tasks.json"
        )
        U.dump_json(self.failed_tasks, f"{self.ckpt_dir}/curriculum/failed_tasks.json")

    def decompose_task(self, task, events):
        """複雑なタスクをより小さなサブタスクに分解するメソッド
        
        大きな目標タスクを達成するために必要な一連のステップを
        言語モデルを使用して特定します。現在の環境状態と最終目標を
        入力として、実行可能なサブタスクのリストを生成します。
        
        Args:
            task (str): 分解する最終目標タスク
            events (List): 環境で発生したイベントのリスト
            
        Returns:
            Dict: 分解されたサブタスクのリストを含むJSON形式のデータ
        """
        messages = [
            SystemMessage(
                content=load_prompt("curriculum_task_decomposition"),
            ),
            self.render_human_message(events=events, chest_observation=""),
            HumanMessage(content=f"Final task: {task}"),
        ]
        print(
            f"\033[31m****Curriculum Agent task decomposition****\nFinal task: {task}\033[0m"
        )
        response = self.llm(messages).content
        print(f"\033[31m****Curriculum Agent task decomposition****\n{response}\033[0m")
        return fix_and_parse_json(response)

    def run_qa(self, *, events, chest_observation):
        """Minecraftに関する質問応答を実行するメソッド
        
        現在の環境状態に基づいて質問を生成し、それらの質問に対する回答を取得します。
        キャッシュ機能を使用して、以前に回答された類似の質問の結果を再利用します。
        
        プロセス:
        1. 環境状態に基づいて質問を生成（run_qa_step1_ask_questions）
        2. 各質問について:
           - キャッシュに類似の質問がある場合はそれを使用
           - なければ新たに回答を生成（run_qa_step2_answer_questions）
        3. 新しい質問と回答をキャッシュに保存
        
        Args:
            events (List): 環境で発生したイベントのリスト
            chest_observation (str): チェストの観察情報
            
        Returns:
            Tuple[List[str], List[str]]: 質問リストと対応する回答リスト
        """
        questions_new, _ = self.run_qa_step1_ask_questions(
            events=events, chest_observation=chest_observation
        )
        questions = []
        answers = []
        for question in questions_new:
            if self.qa_cache_questions_vectordb._collection.count() > 0:
                docs_and_scores = (
                    self.qa_cache_questions_vectordb.similarity_search_with_score(
                        question, k=1
                    )
                )
                if docs_and_scores and docs_and_scores[0][1] < 0.05:
                    question_cached = docs_and_scores[0][0].page_content
                    assert question_cached in self.qa_cache
                    answer_cached = self.qa_cache[question_cached]
                    questions.append(question_cached)
                    answers.append(answer_cached)
                    continue
            answer = self.run_qa_step2_answer_questions(question=question)
            assert question not in self.qa_cache
            self.qa_cache[question] = answer
            self.qa_cache_questions_vectordb.add_texts(
                texts=[question],
            )
            U.dump_json(self.qa_cache, f"{self.ckpt_dir}/curriculum/qa_cache.json")
            self.qa_cache_questions_vectordb.persist()
            questions.append(question)
            answers.append(answer)
        assert len(questions_new) == len(questions) == len(answers)
        return questions, answers

    def get_task_context(self, task):
        """タスクに関連するコンテキスト情報を取得するメソッド
        
        指定されたタスクの実行方法に関する情報をMinecraftの知識ベースから取得します。
        「〜をどうやって行うか」という形式の質問を生成し、その回答をコンテキストとして返します。
        
        特殊処理:
        - 鉱石関連のタスクでは、シルクタッチ関連の問題を避けるために単語を調整
        - 回答がキャッシュにある場合はそれを使用し、なければ新たに生成
        
        Args:
            task (str): コンテキストを取得するタスク名
            
        Returns:
            str: タスク実行に役立つコンテキスト情報
        """
        # if include ore in question, gpt will try to use tool with skill touch enhancement to mine
        question = (
            f"How to {task.replace('_', ' ').replace(' ore', '').replace(' ores', '').replace('.', '').strip().lower()}"
            f" in Minecraft?"
        )
        if question in self.qa_cache:
            answer = self.qa_cache[question]
        else:
            answer = self.run_qa_step2_answer_questions(question=question)
            self.qa_cache[question] = answer
            self.qa_cache_questions_vectordb.add_texts(
                texts=[question],
            )
            U.dump_json(self.qa_cache, f"{self.ckpt_dir}/curriculum/qa_cache.json")
            self.qa_cache_questions_vectordb.persist()
        context = f"Question: {question}\n{answer}"
        return context

    def render_system_message_qa_step1_ask_questions(self):
        """質問生成のためのシステムメッセージを作成するメソッド
        
        質問生成プロンプトをロードし、システムメッセージとして返します。
        
        Returns:
            SystemMessage: 質問生成のためのシステムメッセージ
        """
        return SystemMessage(content=load_prompt("curriculum_qa_step1_ask_questions"))

    def render_human_message_qa_step1_ask_questions(self, *, events, chest_observation):
        """質問生成のためのヒューマンメッセージを作成するメソッド
        
        現在の環境観察情報をヒューマンメッセージとして整形します。
        
        Args:
            events (List): 環境で発生したイベントのリスト
            chest_observation (str): チェストの観察情報
            
        Returns:
            HumanMessage: 質問生成のためのヒューマンメッセージ
        """
        observation = self.render_observation(
            events=events, chest_observation=chest_observation
        )
        content = ""
        for key in self.curriculum_observations:
            content += observation[key]
        return HumanMessage(content=content)

    def run_qa_step1_ask_questions(self, *, events, chest_observation):
        """環境状態に基づいて質問を生成するメソッド（QAステップ1）
        
        現在のバイオームに関する基本的な質問と、環境観察に基づく追加の質問を生成します。
        
        基本質問:
        - バイオームで見つかるブロック
        - バイオームで見つかるアイテム
        - バイオームで見つかるモブ（生物）
        
        Args:
            events (List): 環境で発生したイベントのリスト
            chest_observation (str): チェストの観察情報
            
        Returns:
            Tuple[List[str], List[str]]: 生成された質問リストと関連する概念リスト
        """
        biome = events[-1][1]["status"]["biome"].replace("_", " ")
        questions = [
            f"What are the blocks that I can find in the {biome} in Minecraft?",
            f"What are the items that I can find in the {biome} in Minecraft?",
            f"What are the mobs that I can find in the {biome} in Minecraft?",
        ]
        concepts = [biome, biome, biome]
        messages = [
            self.render_system_message_qa_step1_ask_questions(),
            self.render_human_message_qa_step1_ask_questions(
                events=events, chest_observation=chest_observation
            ),
        ]
        qa_response = self.qa_llm(messages).content
        try:
            # Regex pattern to extract question and concept pairs
            pattern = r"Question \d+: (.+)\nConcept \d+: (.+)"
            # Extracting all question and concept pairs from the text
            pairs = re.findall(pattern, qa_response)
            # Storing each question and concept in separate lists
            questions_new = [pair[0] for pair in pairs]
            concepts_new = [pair[1] for pair in pairs]
            assert len(questions_new) == len(concepts_new)
            questions.extend(questions_new)
            concepts.extend(concepts_new)
        except Exception as e:
            print(
                f"\033[35mError parsing curriculum response for "
                f"QA step 1 ask questions: {e}.\033[0m"
            )
        return questions, concepts

    def render_system_message_qa_step2_answer_questions(self):
        """質問回答のためのシステムメッセージを作成するメソッド
        
        質問回答プロンプトをロードし、システムメッセージとして返します。
        
        Returns:
            SystemMessage: 質問回答のためのシステムメッセージ
        """
        return SystemMessage(
            content=load_prompt("curriculum_qa_step2_answer_questions")
        )

    def render_human_message_qa_step2_answer_questions(self, question):
        """質問回答のためのヒューマンメッセージを作成するメソッド
        
        質問をヒューマンメッセージとして整形します。
        
        Args:
            question (str): 回答を得たい質問
            
        Returns:
            HumanMessage: 質問回答のためのヒューマンメッセージ
        """
        content = f"Question: {question}"
        return HumanMessage(content=content)

    def run_qa_step2_answer_questions(self, question):
        """質問に対する回答を生成するメソッド（QAステップ2）
        
        指定された質問に対して言語モデルを使用して回答を生成します。
        
        Args:
            question (str): 回答を得たい質問
            
        Returns:
            str: 質問に対する回答
        """
        messages = [
            self.render_system_message_qa_step2_answer_questions(),
            self.render_human_message_qa_step2_answer_questions(question=question),
        ]
        print(f"\033[35mCurriculum Agent Question: {question}\033[0m")
        qa_answer = self.qa_llm(messages).content
        print(f"\033[31mCurriculum Agent {qa_answer}\033[0m")
        return qa_answer
