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
        server_port: int = 3000,
        server_host: str = "http://127.0.0.1",
        env_wait_ticks: int = 1,
        env_request_timeout: int = 600,
        ckpt_dir: str = "ckpt",
        resume: bool = False,
    ):
        """
        Voyagerのメインクラス。
        :param mc_port: マインクラフトのゲーム内ポート
        :param mc_host: マインクラフトのホスト名またはIP
        :param server_port: mineflayerのポート
        :param server_host: mineflayerのホスト
        :param env_wait_ticks: 各ステップの最後に待機するtick数
        :param env_request_timeout: 各ステップの待機秒数
        :param resume: チェックポイントから再開するかどうか
        """
        # init env
        self.env = VoyagerEnv(
            mc_port=mc_port,
            mc_host=mc_host,
            server_host=server_host,
            server_port=server_port,
            request_timeout=env_request_timeout,
        )
        self.env_wait_ticks = env_wait_ticks
        self.recorder = U.EventRecorder(ckpt_dir=ckpt_dir, resume=resume)
        self.resume = resume
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
            mineflayer_data=self.env.reset(
                options={
                    "mode": "hard",  # ハードリセット：すべての状態を初期化
                    "wait_ticks": self.env_wait_ticks,  # 環境が安定するまで待機するティック数
                }
            )
            print(f"mineflayer_data:\n{mineflayer_data}")
            self.resume = True  # 次回からはresumeモードとして扱う
        self.last_events = self.env.step("")  # 空のコマンドを実行してサーバー環境の現在の状態を取得
        print(f"self.last_events:\n{self.last_events}")