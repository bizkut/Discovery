import os.path
import time
import warnings
from typing import SupportsFloat, Any, Tuple, Dict

import requests
import json

import gymnasium as gym
from gymnasium.core import ObsType

import voyager.utils as U

from .minecraft_launcher import MinecraftInstance
from .process_monitor import SubprocessMonitor


class VoyagerEnv(gym.Env):
    def __init__(
        self,
        mc_port=None,
        mc_host="host.docker.internal",  # Minecraftホストのデフォルト値
        azure_login=None,
        server_host="http://127.0.0.1",
        server_port=3000,
        request_timeout=600,
        log_path="./logs",
    ):
        """Voyager環境のコンストラクタ
        
        Gymnasiumの標準インターフェースに準拠したMinecraft環境を初期化します。
        既存のMinecraftサーバーに接続するか、新しいAzureインスタンスを作成します。
        
        Args:
            mc_port (Optional[int]): 既存のMinecraftサーバーのポート番号
            mc_host (str): Minecraftサーバーのホスト名。デフォルトは"host.docker.internal"
            azure_login (Optional[Dict]): Azureインスタンスのログイン情報
            server_host (str): Mineflayerサーバーのホスト名。デフォルトは"http://127.0.0.1"
            server_port (int): Mineflayerサーバーのポート番号。デフォルトは3000
            request_timeout (int): リクエストのタイムアウト時間（秒）。デフォルトは600
            log_path (str): ログファイルの保存先。デフォルトは"./logs"
            
        Raises:
            ValueError: mc_portとazure_loginの両方が指定されていない場合
        """
        # mc_portとazure_loginの少なくとも一方が指定されているか確認
        if not mc_port and not azure_login:
            raise ValueError("Either mc_port or azure_login must be specified")
        # 両方指定されている場合は警告を表示
        if mc_port and azure_login:
            warnings.warn(
                "Both mc_port and mc_login are specified, mc_port will be ignored"
            )
        # 各種パラメータを保存
        self.mc_port = mc_port
        self.mc_host = mc_host  # Minecraftホストを保存
        self.azure_login = azure_login
        self.server = f"{server_host}:{server_port}"
        self.server_port = server_port
        self.request_timeout = request_timeout
        self.log_path = log_path
        # Mineflayerプロセスを初期化
        self.mineflayer = self.get_mineflayer_process(server_port)
        # Azure認証情報が提供されている場合はMinecraftインスタンスを作成
        if azure_login:
            self.mc_instance = self.get_mc_instance()
        else:
            self.mc_instance = None
        # 環境の状態を初期化
        self.has_reset = False
        self.reset_options = None
        self.connected = False
        self.server_paused = False

    def get_mineflayer_process(self, server_port):
        """Mineflayerプロセスを初期化するメソッド
        
        指定されたポートでMineflayerサーバーを起動するためのSubprocessMonitorを作成します。
        
        Args:
            server_port (int): Mineflayerサーバーのポート番号
            
        Returns:
            SubprocessMonitor: Mineflayerプロセスを監視するオブジェクト
        """
        # ログディレクトリを作成
        U.f_mkdir(self.log_path, "mineflayer")
        # 現在のファイルのディレクトリパスを取得
        file_path = os.path.abspath(os.path.dirname(__file__))
        # SubprocessMonitorを作成して返す
        return SubprocessMonitor(
            commands=[
                "node",
                U.f_join(file_path, "mineflayer/index.js"),
                str(server_port),
            ],
            name="mineflayer",
            ready_match=r"Server started on port (\d+)",
            log_path=U.f_join(self.log_path, "mineflayer"),
        )

    def get_mc_instance(self):
        """Minecraftインスタンスを作成するメソッド
        
        Azure認証情報を使用して新しいMinecraftサーバーインスタンスを作成します。
        
        Returns:
            MinecraftInstance: 作成されたMinecraftインスタンス
        """
        print("Creating Minecraft server")
        # ログディレクトリを作成
        U.f_mkdir(self.log_path, "minecraft")
        # MinecraftInstanceを作成して返す
        return MinecraftInstance(
            **self.azure_login,
            mineflayer=self.mineflayer,
            log_path=U.f_join(self.log_path, "minecraft"),
        )

    def check_process(self):
        """Minecraftプロセスとmineflayerサーバーの状態を確認し、必要に応じて再起動するメソッド
        
        このメソッドは以下の処理を行います：
        1. Minecraftインスタンスが存在し、実行されていない場合は再起動を試みます
        2. Mineflayerサーバーが実行されていない場合は再起動を試みます
        3. Mineflayerサーバーに接続情報を送信し、Minecraft環境との接続を確立します
        
        Returns:
            Dict: サーバーからのレスポンスデータ（JSON形式）
            
        Raises:
            RuntimeError: プロセスの起動に失敗した場合や、サーバーとの通信に失敗した場合
        """
        # Minecraftインスタンスの状態確認と再起動
        if self.mc_instance and not self.mc_instance.is_running:
            print("Minecraft process has exited, restarting")
            self.mc_instance.run()
            if not self.mc_instance.is_running:
                raise RuntimeError("Minecraft process failed to start")
        
        # Mineflayerサーバーの状態確認と起動
        retry = 0
        max_retries = 3
        while not self.mineflayer.is_running:
            print("Mineflayer process has exited, restarting")
            self.mineflayer.run()
            if not self.mineflayer.is_running:
                if retry >= max_retries:
                    raise RuntimeError("Mineflayer process failed to start after multiple attempts")
                else:
                    retry += 1
                    print(f"リトライ {retry}/{max_retries}")
                    time.sleep(2)  # リトライ前に少し待機
                    continue
            
            # リクエスト送信前に接続情報を再確認
            print(f"Mineflayer send request: {self.reset_options}")
            #print(self.mineflayer.ready_line)
            #print(f"接続先: {self.reset_options.get('host', 'localhost')}:{self.reset_options.get('port', 'N/A')}")
            
            try:
                # サーバーに接続情報を送信
                res = requests.post(
                    f"{self.server}/start",
                    json=self.reset_options,
                    timeout=self.request_timeout,
                )
                # レスポンスのステータスコードを確認
                if res.status_code != 200:
                    print(f"エラー: サーバーから {res.status_code} コードが返されました")
                    self.mineflayer.stop()
                    if retry >= max_retries:
                        raise RuntimeError(f"Minecraft server reply with code {res.status_code}")
                    retry += 1
                    print(f"リトライ {retry}/{max_retries}")
                    time.sleep(2)
                    continue
                return res.json()
            except (requests.exceptions.ConnectionError, requests.exceptions.Timeout) as e:
                # 接続エラーまたはタイムアウトの処理
                print(f"接続エラー: {e}")
                self.mineflayer.stop()
                if retry >= max_retries:
                    raise RuntimeError(f"Failed to connect to mineflayer server: {e}")
                retry += 1
                print(f"リトライ {retry}/{max_retries}")
                time.sleep(3)  # 接続エラー後は少し長めに待機
                continue

    def step(
        self,
        code: str,
        programs: str = "",
    ) -> Tuple[ObsType, SupportsFloat, bool, bool, Dict[str, Any]]:
        """Minecraftエージェントに次のアクションを実行させるメソッド
        
        このメソッドはGymnasiumの標準インターフェースに準拠しており、
        Minecraftエージェントに指示を送るためのブリッジとして機能します。
        
        Args:
            code (str): 実行するコード文字列
            programs (str, optional): 追加のプログラム。デフォルトは空文字列
            
        Returns:
            Tuple[ObsType, SupportsFloat, bool, bool, Dict[str, Any]]: 
                標準的なGym環境の戻り値形式
                (観測, 報酬, 終了フラグ, 切り捨てフラグ, 情報辞書)
        
        返答例:
        [['observe', {
            'voxels': ['vine', 'oak_leaves', 'oak_log'],  # 周辺のブロック情報
            'status': {
                'health': 20,  # プレイヤーの体力
                'food': 20,  # 満腹度
                'saturation': 5,  # 隠し満腹度
                'position': {'x': -41.5, 'y': 66, 'z': -64.5},  # 座標
                'velocity': {'x': 0, 'y': -0.0784000015258789, 'z': 0},  # 速度
                'yaw': 3.141592653589793,  # 水平方向の向き
                'pitch': 0,  # 垂直方向の向き
                'onGround': True,  # 地面に接地しているか
                'equipment': [None, None, None, None, None, None],  # 装備状態
                'name': 'bot',  # プレイヤー名
                'timeSinceOnGround': 0,  # 最後に地面に触れてからの時間
                'isInWater': False,  # 水中にいるか
                'isInLava': False,  # 溶岩中にいるか
                'isCollidedHorizontally': False,  # 水平方向の衝突
                'isCollidedVertically': True,  # 垂直方向の衝突
                'biome': 'forest',  # バイオーム
                'entities': {'wolf': 31.9888205417697},  # 周辺のエンティティと距離
                'timeOfDay': 'sunrise',  # ゲーム内時間
                'inventoryUsed': 0,  # インベントリ使用状況
                'elapsedTime': 83  # 経過時間
            },
            'inventory': {},  # インベントリ内容
            'nearbyChests': {},  # 周辺のチェスト
            'blockRecords': ['vine', 'oak_leaves', 'oak_log']  # 記録されたブロック
        }]]
        
        Raises:
            RuntimeError: 環境が初期化されていない場合や、サーバーとの通信に失敗した場合
        """
        # 環境が初期化されているか確認
        if not self.has_reset:
            raise RuntimeError("Environment has not been reset yet")
            
        # Minecraftプロセスとmineflayerサーバーの状態を確認
        self.check_process()
        
        # サーバーが一時停止状態の場合は再開
        self.unpause()
        
        # 実行するコードとプログラムをデータ辞書にまとめる
        data = {
            "code": code,
            "programs": programs,
        }
        
        # サーバーにPOSTリクエストを送信してコードを実行
        res = requests.post(
            f"{self.server}/step", json=data, timeout=self.request_timeout
        )
        
        # レスポンスのステータスコードを確認
        if res.status_code != 200:
            raise RuntimeError("Failed to step Minecraft server")
            
        # レスポンスデータを取得
        returned_data = res.json()
        
        # 次のステップの準備のためにサーバーを一時停止
        self.pause()
        
        # JSONデータをパースして返す
        return json.loads(returned_data)

    def render(self):
        """環境の状態を視覚化するメソッド
        
        Gymnasiumの標準インターフェースに準拠していますが、
        現在の実装では対応していません。
        
        Raises:
            NotImplementedError: このメソッドは現在実装されていません
        """
        raise NotImplementedError("render is not implemented")

    def reset(
        self,
        *,
        seed=None,
        options=None,
    ) -> Tuple[ObsType, Dict[str, Any]]:
        """環境を初期化するメソッド
        
        Gymnasiumの標準インターフェースに準拠しており、Minecraft環境を
        指定されたオプションに基づいて初期化します。
        
        Args:
            seed (Optional[int]): 乱数生成のためのシード値（現在は使用されていない）
            options (Optional[Dict]): 初期化オプション
                - mode (str): リセットモード。"hard"または"soft"。デフォルトは"hard"
                - inventory (Dict): 初期インベントリ設定（"hard"モード時のみ有効）
                - equipment (List): 初期装備設定
                - spread (bool): プレイヤーをランダムな位置に配置するかどうか
                - wait_ticks (int): 初期化後の待機ティック数
                - position (Optional): 初期位置の指定
        
        Returns:
            Tuple[ObsType, Dict[str, Any]]: 初期観測値と情報辞書
            
        Raises:
            RuntimeError: 無効なオプション組み合わせが指定された場合
        """
        if options is None:
            options = {}

        # "hard"モード以外でinventoryオプションが指定された場合はエラー
        if options.get("inventory", {}) and options.get("mode", "hard") != "hard":
            raise RuntimeError("inventory can only be set when options is hard")

        # リセットオプションを設定
        self.reset_options = {
            "port": self.mc_port,
            "host": self.mc_host,  # mc_host の値を追加
            "reset": options.get("mode", "hard"),
            "inventory": options.get("inventory", {}),
            "equipment": options.get("equipment", []),
            "spread": options.get("spread", False),
            "waitTicks": options.get("wait_ticks", 5),
            "position": options.get("position", None),
        }

        # サーバーが一時停止状態の場合は再開
        self.unpause()
        # Mineflayerプロセスを停止して再起動の準備
        self.mineflayer.stop()
        time.sleep(1)  # Mineflayerが完全に終了するのを待機

        # プロセスを確認し、必要に応じて再起動
        returned_data = self.check_process()
        self.has_reset = True
        self.connected = True
        # 以降のリセットはすべて"soft"モードに設定
        self.reset_options["reset"] = "soft"
        # 次のステップの準備のためにサーバーを一時停止
        self.pause()
        return json.loads(returned_data)

    def close(self):
        """環境を閉じるメソッド
        
        Gymnasiumの標準インターフェースに準拠しており、Minecraft環境との
        接続を切断し、関連するプロセスを終了します。
        
        Returns:
            bool: 接続が正常に切断されたかどうか（True: 切断済み、False: 接続中）
        """
        # サーバーが一時停止状態の場合は再開
        self.unpause()
        # サーバーに接続されている場合は停止リクエストを送信
        if self.connected:
            res = requests.post(f"{self.server}/stop")
            if res.status_code == 200:
                self.connected = False
        # Minecraftインスタンスが存在する場合は停止
        if self.mc_instance:
            self.mc_instance.stop()
        # Mineflayerプロセスを停止
        self.mineflayer.stop()
        # 接続状態の反転値を返す（True: 切断済み、False: 接続中）
        return not self.connected

    def pause(self):
        """サーバーを一時停止状態にするメソッド
        
        Mineflayerサーバーが実行中で、かつ現在一時停止状態でない場合に
        サーバーに一時停止リクエストを送信します。
        
        Returns:
            bool: 一時停止状態かどうか（True: 一時停止中、False: 実行中）
        """
        if self.mineflayer.is_running and not self.server_paused:
            res = requests.post(f"{self.server}/pause")
            if res.status_code == 200:
                self.server_paused = True
        return self.server_paused

    def unpause(self):
        """サーバーの一時停止を解除するメソッド
        
        Mineflayerサーバーが実行中で、かつ現在一時停止状態の場合に
        サーバーに一時停止解除リクエストを送信します。
        
        Returns:
            bool: 一時停止状態かどうか（True: 一時停止中、False: 実行中）
        """
        if self.mineflayer.is_running and self.server_paused:
            res = requests.post(f"{self.server}/pause")
            if res.status_code == 200:
                self.server_paused = False
            else:
                print(res.json())
        return self.server_paused
