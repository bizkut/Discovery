from javascript import require, On, Once, AsyncTask, once, off
import asyncio
import math
from concurrent.futures import ThreadPoolExecutor

class Skills:
    def __init__(self, discovery):
        """
        Discoveryインスタンスを受け取り、そのプロパティを使用します
        
        Args:
            discovery: Discoveryクラスのインスタンス
        """
        self.discovery = discovery
        self.bot = discovery.bot
        self.mcdata = discovery.mcdata
        self.pathfinder = discovery.pathfinder
        self.movements = discovery.movements
        self.mineflayer = discovery.mineflayer

    async def get_bot_position(self):
        """
        ボットの現在位置を取得します。

        Returns:
            tuple[float, float, float]: ボットの位置のx, y, z座標を含むtuple。 

        Example:
            >>>result = get_bot_position()
            >>>print(result)
            (100, 50, 200)
            >>>print(result[0])
            100
        """
        bot_pos = self.bot.blockAt(self.bot.entity.position).position
        return bot_pos.x, bot_pos.y, bot_pos.z
    
    async def look_at_direction(self, direction):
        """
        BOTが指定された方角を向きます。BotViewAgentと組み合わせて、BOTの周辺視界を確認する際に有効です。

        Args:
            direction (str): 方角 ('north', 'south', 'east', 'west', 'up', 'down')

        Returns:
            dict: 結果を含む辞書
                - success (bool): 方向転換に成功した場合はTrue
                - message (str): 結果メッセージ
        """
        result = {
            "success": False,
            "message": ""
        }

        try:
            # 現在のヨーとピッチを取得
            current_yaw = self.bot.entity.yaw
            current_pitch = self.bot.entity.pitch
            
            target_yaw = current_yaw # デフォルトは現在のヨー
            target_pitch = 0.0 # デフォルトは水平

            direction_lower = direction.lower()

            if direction_lower == 'north':
                target_yaw = 0
            elif direction_lower == 'east':
                target_yaw = math.pi / 2
            elif direction_lower == 'south':
                target_yaw = math.pi
            elif direction_lower == 'west':
                target_yaw = -math.pi / 2
            elif direction_lower == 'up':
                target_pitch = math.pi / 2  # 真上
                target_yaw = current_yaw # 上下を見る場合はヨーは維持
            elif direction_lower == 'down':
                target_pitch = -math.pi / 2 # 真下
                target_yaw = current_yaw # 上下を見る場合はヨーは維持
            else:
                result["message"] = f"無効な方角が指定されました: {direction}"
                self.bot.chat(result["message"])
                return result

            # bot.look は同期メソッドの可能性が高いが、念のため await するか確認
            # Mineflayer の bot.look は通常同期ですが、javascript ライブラリ経由だと非同期の場合がある
            # ここでは同期として扱う（もしエラーが出たら await self.bot.look(...) に変更）
            self.bot.look(target_yaw, target_pitch)
            
            result["success"] = True
            result["message"] = f"{direction.capitalize()} を向きました。"
            # self.bot.chat(result["message"]) # 頻繁に呼ばれる可能性があるのでチャットは省略
            return result

        except Exception as e:
            result["message"] = f"{direction} を向く際にエラーが発生しました: {str(e)}"
            self.bot.chat(result["message"])
            import traceback
            traceback.print_exc()
            return result
        
    async def _get_surrounding_blocks(self, position=None, x_distance=10, y_distance=10, z_distance=10):
        """
        指定位置周囲のブロックを取得します。広い範囲でブロック情報を取得する際に有効です。

        Args:
            position (Vec3 or tuple): 探索の中心位置（未指定の場合はBOTの位置）。タプルでも可。
            x_distance (int): X方向の探索距離（デフォルト: 10）
            y_distance (int): Y方向の探索距離（デフォルト: 10）
            z_distance (int): Z方向の探索距離（デフォルト: 10）

        Returns:
            list: 周囲のブロック情報のリスト（各要素は{'name': ブロック名, 'position': 位置}の辞書）

        動作の詳細:
            - 小範囲: 全ブロックを取得
            - 大範囲: 3つのゾーンに分けて最適化
              - 近距離（半径5ブロック以内）: 全ブロック取得
              - 中距離（半径5-10ブロック）: 2ブロックごとに取得
              - 遠距離（半径10ブロック以上）: 3ブロックごとに取得
            - バッチ処理でブロック取得を最適化（500ブロックずつ）
            - 並列処理でフィルタリングを高速化
        """
        Vec3 = require('vec3') # Vec3 を利用可能にする

        self.bot.chat(f"{x_distance}x{y_distance}x{z_distance}の範囲でブロックを取得します。")
        # デフォルト値の設定
        if position is None:
            position = self.bot.entity.position

        # --- 型チェックと変換を追加 --- 
        if isinstance(position, tuple) and len(position) == 3:
            try:
                position = Vec3(position[0], position[1], position[2])
            except Exception as e:
                self.bot.chat("座標の型変換エラーが発生しました。")
                return [] # エラー時は空リストを返す
        elif not hasattr(position, 'offset'): # offset メソッドがない場合 (Vec3 でない場合)
            self.bot.chat("無効な座標オブジェクトタイプです。")
            return [] # エラー時は空リストを返す
        # --- ここまで追加 --- 

        x_dist = x_distance
        y_dist = y_distance
        z_dist = z_distance
        
        # 距離に応じたサンプリングレートの設定
        coords = []
        total_vol = (2 * x_dist + 1) * (2 * y_dist + 1) * (2 * z_dist + 1)
        
        # 距離に応じたサンプリング（大きな範囲では間引きを行う）
        if total_vol > 8000:  # 範囲が大きい場合
            # 近距離は密に、遠距離は疎に
            near_dist = 5  # 近距離の境界
            
            # 近距離ゾーン（完全取得）
            for x in range(-min(near_dist, x_dist), min(near_dist, x_dist) + 1):
                for y in range(-min(near_dist, y_dist), min(near_dist, y_dist) + 1):
                    for z in range(-min(near_dist, z_dist), min(near_dist, z_dist) + 1):
                        coords.append(position.offset(x, y, z))
            
            # 中間ゾーン（2ブロックごとに取得）
            mid_dist = 10
            if x_dist > near_dist or y_dist > near_dist or z_dist > near_dist:
                for x in range(-min(mid_dist, x_dist), min(mid_dist, x_dist) + 1, 2):
                    for y in range(-min(mid_dist, y_dist), min(mid_dist, y_dist) + 1, 2):
                        for z in range(-min(mid_dist, z_dist), min(mid_dist, z_dist) + 1, 2):
                            # 近距離ゾーンに含まれないブロックのみ追加
                            if abs(x) > near_dist or abs(y) > near_dist or abs(z) > near_dist:
                                coords.append(position.offset(x, y, z))
            
            # 遠距離ゾーン（3ブロックごとに取得）
            if x_dist > mid_dist or y_dist > mid_dist or z_dist > mid_dist:
                for x in range(-x_dist, x_dist + 1, 3):
                    for y in range(-y_dist, y_dist + 1, 3):
                        for z in range(-z_dist, z_dist + 1, 3):
                            # 中間ゾーンに含まれないブロックのみ追加
                            if abs(x) > mid_dist or abs(y) > mid_dist or abs(z) > mid_dist:
                                coords.append(position.offset(x, y, z))
            
        else:
            # 範囲が小さい場合は全ブロック取得
            for x in range(-x_dist, x_dist + 1):
                for y in range(-y_dist, y_dist + 1):
                    for z in range(-z_dist, z_dist + 1):
                        coords.append(position.offset(x, y, z))

        # バッチサイズの決定（大量のリクエストを分割して処理）
        batch_size = 500
        all_blocks = []
        
        # バッチ処理
        for i in range(0, len(coords), batch_size):
            batch_end = min(i + batch_size, len(coords))
            batch = coords[i:batch_end]
            
            async def _get_block_async(position):
                return self.bot.blockAt(position)
            
            # バッチ内のブロック取得を並列実行
            batch_tasks = [_get_block_async(pos) for pos in batch]
            batch_results = await asyncio.gather(*batch_tasks)
            all_blocks.extend(batch_results)
        
        try:
            def chunks(lst, n):
                """リストをn個のチャンクに分割"""
                for i in range(0, len(lst), n):
                    yield lst[i:i + n]
            
            def process_chunk(chunk):
                return [{'name': block.name, 'position': {'x': block.position.x, 'y': block.position.y, 'z': block.position.z}} 
                        for block in chunk if block and block.type != 0]
            
            # CPUコア数に基づいて最適なチャンクサイズを計算
            import os
            cpu_count = os.cpu_count() or 4
            chunk_size = max(100, len(all_blocks) // (cpu_count * 2))
            block_chunks = list(chunks(all_blocks, chunk_size))
            
            # マルチスレッドでフィルタリングを実行
            with ThreadPoolExecutor(max_workers=cpu_count) as executor:
                filtered_chunks = list(executor.map(process_chunk, block_chunks))
            
            # 結果を結合
            surrounding_blocks = []
            for chunk in filtered_chunks:
                surrounding_blocks.extend(chunk)
                
        except ImportError:
            # 並列処理ライブラリがインポートできない場合は標準的なリスト内包表記を使用
            surrounding_blocks = [
                {'name': block.name, 'position': {'x': block.position.x, 'y': block.position.y, 'z': block.position.z}}
                for block in all_blocks
                if block and block.type != 0
            ]
        
        return surrounding_blocks
    
    
    async def get_inventory_counts(self):
        """
        ボットのインベントリ内の各アイテムの名前と数を辞書形式で返します。

        Returns:
            dict: キーがアイテム名、値がその数量の辞書
            
        Example:
            >>> get_inventory_counts()
            {'birch_planks': 1, 'dirt': 1}
        """
        print("インベントリ内のアイテムを取得します。")
        inventory_counts = {}
        
        # インベントリ内の全アイテムをループ
        for item in self.bot.inventory.items():
            # アイテム名が既に辞書にある場合は数を加算、なければ新規追加
            if item.name in inventory_counts:
                inventory_counts[item.name] += item.count
            else:
                inventory_counts[item.name] = item.count
        await asyncio.sleep(0.1)
        print(inventory_counts)
        return inventory_counts
    
    async def get_nearest_block(self, block_name, max_distance=1000, canMove=True):
        """
        BOTの周囲で指定されたブロック名のブロックを検索し、最も近いブロックの情報を返します。
        
        Args:
            block_name (str): 探すブロック名 (例: "oak_log")
            max_distance (int): 探索する最大ブロック数(デフォルトは1000)
            canMove (bool): 到達可能なブロックのみを返すか。デフォルトはTrue
        Returns:
            Block: 最も近いブロック、見つからない場合はNone
        
        Example:
            >>> get_nearest_block('oak_log')
            Block {
            type: 40,
            metadata: 1,
            light: 0,
            skyLight: 15,
            biome: {
                color: 0,
                height: null,
                name: '',
                rainfall: 0,
                temperature: 0,
                id: 1
            },
            position: Vec3 { x: -83, y: 73, z: 52 },
            name: 'oak_log',
            displayName: 'Oak Log',
            shapes: [ [ 0, 0, 0, 1, 1, 1 ] ],
            boundingBox: 'block',
            transparent: false,
            diggable: true,
            harvestTools: undefined,
            drops: [ 104 ]
            }
            >>> print(get_nearest_block('oak_log').position.x)
            -83
        """
        try:
            # ブロックのIDを取得
            block_id = None
            if hasattr(self.bot.registry, 'blocksByName') and block_name in self.bot.registry.blocksByName:
                block_id = self.bot.registry.blocksByName[block_name].id
            else:
                print(f"get_nearest_blockを実行しましたが、ブロック '{str(block_name)}' はminecraftのブロック名では見つかりません")
                return None
                
            # ブロックを検索
            blocks = self.bot.findBlocks({
                'point': self.bot.entity.position,
                'matching': block_id,
                'maxDistance': max_distance,
                'count': 20
            })
            for block in blocks:
                if canMove:
                    canMove = await self.move_to_position(block.x, block.y, block.z, onlyCheckPath=True)
                    if not canMove["success"]:
                        await asyncio.sleep(0.1)
                        continue
                return self.bot.blockAt(block)
            return None
            
        except Exception as e:
            print(f"ブロック検索中にエラーが発生しました: {str(e)}")
            import traceback
            traceback.print_exc()
            return None
    
    async def get_nearest_free_space(self, X_size=1, Y_size=1, Z_size=1, distance=15, y_offset=0):
        """
        BOTの周囲で指定されたサイズの空きスペース（上部が空気で下部が固体ブロック）を見つけます。
        
        Args:
            X_size (int): 探す空きスペースのXサイズ。(Minecraftのブロックの幅)
            Y_size (int): 探す空きスペースのYサイズ。(Minecraftのブロックの高さ)
            Z_size (int): 探す空きスペースのZサイズ。(Minecraftのブロックの幅)
            distance (int): 探索する最大距離。デフォルトは8。
            y_offset (int): 見つかった空きスペースに適用するY座標オフセット。デフォルトは0。
            
        Returns:
            Vec3: 見つかった空きスペースの南西角の座標。見つからない場合はボットの足元の座標を返します。
        
        Example:
            >>> free_space = skills.get_nearest_free_space(2, 10)
            >>> print(f"見つかった空きスペース: x={free_space.x}, y={free_space.y}, z={free_space.z}")
        """
        self.bot.chat("空きスペースを検索します。")
        try:
            Vec3 = require('vec3')
            result = None
        
            # 空気ブロックを検索
            empty_pos = self.bot.findBlocks({
                'point': self.bot.entity.position,
                'matching': self.mcdata.blocksByName['air'].id,
                'maxDistance': distance,
                'count': 1000
            })
            
            # 各空気ブロックについて、指定されたサイズの空きスペースを確認
            for pos in empty_pos:
                empty = True

                # ボットの位置と同じ場合はスキップ
                bot_pos = self.bot.blockAt(self.bot.entity.position).position
                if (pos.x == bot_pos.x and pos.y == bot_pos.y and pos.z == bot_pos.z):
                    continue
                # 空きスペースを確認
                for x_offset in range(X_size):
                    for y_offset in range(Y_size):
                        for z_offset in range(Z_size):
                            # 上部のブロックが空気であることを確認
                            top = self.bot.blockAt(Vec3(
                                pos.x + x_offset,
                                pos.y + y_offset,
                                pos.z + z_offset
                            ))
                            
                            # 下部のブロックが掘れる固体ブロックであることを確認
                            bottom = self.bot.blockAt(Vec3(
                                pos.x + x_offset,
                                pos.y - 1,
                                pos.z + z_offset
                            ))
                            # 条件チェック
                            if (not top or top.name != 'air' or 
                                not bottom or not hasattr(bottom, 'drops') or not bottom.diggable):
                                empty = False
                                break
                        
                        if not empty:
                            break
                
                # 適切なスペースが見つかった場合は、そのポジションを返す
                if empty:
                    result = pos
                    return result
            
            # 適切なスペースが見つからなかった場合は、Noneを返す
            return None
            
        except Exception as e:
            # エラーが発生した場合はデフォルト値を返す
            self.bot.chat(f"空きスペースの検索中にエラーが発生しました: {str(e)}")
            import traceback
            traceback.print_exc()
            
            # デバッグ情報を出力
            position = self.bot.entity.position
            print(f"Debug: {position}")
            
            # デフォルト値としてボットの足元の座標を返す
            return Vec3(int(position.x), int(position.y) + y_offset, int(position.z))
        
    async def craft_items(self, item_name, num=1):
        """
        指定されたアイテムを指定個数分作成します。
        
        このメソッドは以下の処理を行います：
        1. 指定されたアイテムのレシピを検索します
        2. 取得したレシピが、クラフトテーブルが必要な場合、クラフティングテーブルを探すか設置します
        3. 必要な材料がインベントリにあるか確認します
        4. クラフティングを実行します
        5. 作成したアイテムの結果と詳細を返します
        
        Args:
            item_name (str): 作成するアイテムの名前。Minecraftの内部アイテム名を使用します
                             (例: "stick", "crafting_table", "wooden_pickaxe")
            num (int): 作成する数量。デフォルトは1
            
        Returns:
            dict: 結果を含む辞書
                - success (bool): 作成に成功した場合はTrue、失敗した場合はFalse
                - message (str): 結果メッセージ
                - error (str, optional): エラーがある場合のエラーコード
                - exception (str, optional): 例外が発生した場合の例外メッセージ
                - item (str): 作成しようとしたアイテム名
                - count (int): 作成しようとした数量
        """
        self.bot.chat(f"{str(item_name)}を{str(num)}個作成します。")
        result = {
            "success": False,
            "message": "",
            "item": item_name,
            "count": num
        }
        
        try:
            placed_table = False
            
            # レシピが存在するか確認
            item_id = self._get_item_id(item_name)
            
            recipes = self.bot.recipesFor(item_id, None, num, None)
            crafting_table_recipes = self.bot.recipesFor(item_id, None, num, True)
            if not any(True for _ in recipes) and not any(True for _ in crafting_table_recipes):
                # 材料不足の場合、必要な材料を調べる
                required_materials = []
                # レシピから必要な材料を取得
                recipe_data = self.get_item_crafting_recipes(item_name)
                if recipe_data and recipe_data[0]:
                    recipe_dict = recipe_data[0][0]
                    required_materials = [f"{key}: {value}" for key, value in recipe_dict.items()]
                else:
                    required_materials.append("レシピが見つかりません")
                
                error_msg = f"{str(item_name)}を作成するための材料が不足しています"
                if required_materials:
                    error_msg += f"。必要な材料: {', '.join(required_materials)}"
                    
                self.bot.chat(error_msg)
                result["message"] = error_msg
                result["error"] = "insufficient_materials"
                
                if placed_table:
                    await self.collect_block('crafting_table', 1)
                return result

            crafting_table = None
            crafting_table_range = 32

            # クラフティングテーブルが必要な場合
            if not any(True for _ in recipes) and any(True for _ in crafting_table_recipes):  # Proxyオブジェクトの空チェック
                recipes = self.bot.recipesFor(item_id, None, num, True)
                if not recipes:
                    self.bot.chat(f"{str(item_name)}のレシピが見つかりません")
                    error_msg = f"{str(item_name)}のレシピが見つかりません"
                    self.bot.chat(error_msg)
                    result["message"] = error_msg
                    result["error"] = "recipe_not_found"
                    return result
                    
                # クラフティングテーブルを探す
                crafting_table = await self.get_nearest_block('crafting_table', crafting_table_range)
                if not crafting_table:
                    # インベントリにクラフティングテーブルがあるか確認
                    if (await self.get_inventory_counts()).get('crafting_table', 0) > 0:
                        # クラフティングテーブルを設置
                        pos = await self.get_nearest_free_space(X_size=1,Z_size=1,distance=6)
                        place_result =await self.place_block('crafting_table', pos.x, pos.y, pos.z)
                        if not place_result["success"]:
                            result["message"] = place_result["message"]
                            result["error"] = "crafting_table_placement_failed"
                            self.bot.chat(place_result["message"])
                            print(result)
                            return result

                        crafting_table = await self.get_nearest_block('crafting_table', crafting_table_range)
                        if crafting_table:
                            recipes = self.bot.recipesFor(item_id, None, 1, crafting_table)
                            placed_table = True
                    else:
                        self.bot.chat(f"{str(item_name)}の作成には作業台が必要ですが、周辺32ブロック以内に作業台が見つからず、インベントリにも作業台がないため作成できません")
                        error_msg = f"{str(item_name)}の作成には作業台が必要ですが、周辺32ブロック以内に作業台が見つからず、インベントリにも作業台がないため作成できません"
                        self.bot.chat(error_msg)
                        result["message"] = error_msg
                        result["error"] = "crafting_table_required"
                        return result
                else:
                    # 近くに作業台がある場合は、レシピを取得
                    recipes = self.bot.recipesFor(item_id, None, 1, crafting_table)
                
            # クラフティングテーブルまで移動
            if crafting_table and self.bot.entity.position.distanceTo(crafting_table.position) > 4:
                move_result = await self.move_to_position(crafting_table.position.x, crafting_table.position.y, crafting_table.position.z)
                if not move_result:
                    error_msg = "クラフティングテーブルまで移動できません"
                    self.bot.chat(str(error_msg))
                    result["message"] = error_msg
                    result["error"] = "movement_failed"
                    return result
                
            recipe = recipes[0]
            try:

                # レシピの有効性チェック
                if not recipe or not hasattr(recipe, 'result'):
                    error_msg = f"{str(item_name)}の有効なレシピが見つかりません"
                    self.bot.chat(str(error_msg))
                    result["message"] = error_msg
                    result["error"] = "invalid_recipe"
                    return result

                # クラフト実行
                self.bot.craft(recipe, num, crafting_table)
                success_msg = f"{str(item_name)}を{str(num)}個作成しました"
                self.bot.chat(success_msg)
                
                # 設置したクラフティングテーブルを回収
                if placed_table:
                    await self.collect_block('crafting_table', 1)
                
                result["success"] = True
                result["message"] = success_msg
                return result
                
            except Exception as e:
                error_msg = f"クラフト中にエラーが発生しました: {str(e)}"
                self.bot.chat(str(error_msg))
                result["message"] = error_msg
                result["error"] = "crafting_error"
                result["exception"] = str(e)
                
                if placed_table:
                    await self.collect_block('crafting_table', 1)
                return result
                
        except Exception as e:
            error_msg = f"予期せぬエラーが発生しました: {str(e)}"
            self.bot.chat(str(error_msg))
            result["message"] = error_msg
            result["error"] = "unexpected_error"
            result["exception"] = str(e)
            import traceback
            traceback.print_exc()
            return result
        
    async def place_block(self, block_name, x, y, z, place_on='bottom'):
        """
        指定された座標にブロックを設置します。隣接するブロックから設置します。
        設置場所にブロックがある場合や、設置できる場所がない場合は失敗します。
        
        Args:
            block_name (str): 設置するブロック名
            x : 設置するX座標
            y : 設置するY座標
            z : 設置するZ座標
            place_on (str): 優先的に設置する面の方向。'top', 'bottom', 'north', 'south', 'east', 'west', 'side'から選択。デフォルトは'bottom'
            dont_cheat (bool): チートモードでも通常の方法でブロックを設置するかどうか。デフォルトはFalse
            
        Returns:
            dict: 結果を含む辞書
                - success (bool): 設置に成功した場合はTrue、失敗した場合はFalse
                - message (str): 結果メッセージ
                - position (dict): 設置を試みた位置 {x, y, z}
                - block_name (str): 設置しようとしたブロック名
                - error (str, optional): エラーがある場合のエラーコード
        """
        self.bot.chat(f"{block_name}を座標({x}, {y}, {z})に設置します。")
        result = {
            "success": False,
            "message": "",
            "position": {"x": x, "y": y, "z": z},
            "block_name": block_name
        }
        
        # ブロックIDの検証
        try:
            block_id = None
            
            # ブロック名からIDを取得
            block_id = self._get_item_id(block_name)
    
            if block_id is None:
                self.bot.chat(f"無効なブロック名です: {block_name}")
                result["message"] = f"無効なブロック名です: {block_name}"
                result["error"] = "invalid_block_name"
                self.bot.chat(result["message"])
                return result
        except Exception as e:
            self.bot.chat(f"ブロック名の検証中にエラーが発生しました: {str(e)}")
            result["message"] = f"ブロック名の検証中にエラーが発生しました: {str(e)}"
            result["error"] = "block_validation_error"
            self.bot.chat(result["message"])
            return result
            
        # Vec3オブジェクトを作成
        Vec3 = require('vec3')
        target_dest = Vec3(int(x), int(y), int(z))
        
        try:
            # アイテム名の修正（一部のブロックは設置時に名前が変わる）
            item_name = block_name
            if item_name == "redstone_wire":
                item_name = "redstone"
                
            # インベントリからブロックを探す
            block_item = None
            for item in self.bot.inventory.items():
                if item.name == item_name:
                    block_item = item
                    break
                    
            # クリエイティブモードでブロックがない場合は取得
            if not block_item and self.bot.game.gameMode == 'creative' and not (hasattr(self.bot, 'restrict_to_inventory') and self.bot.restrict_to_inventory):
                try:
                    # スロット36が最初のホットバースロット
                    await self.bot.creative.setInventorySlot(36, self._make_item(item_name, 1))
                    # 再度ブロックを探す
                    for item in self.bot.inventory.items():
                        if item.name == item_name:
                            block_item = item
                            break
                except Exception as e:
                    self.bot.chat(f"クリエイティブモードでのアイテム取得エラー: {e}")
                    print(f"クリエイティブモードでのアイテム取得エラー: {e}")
            
            # ブロックがない場合は失敗
            if not block_item:
                result["message"] = f"{block_name}をインベントリに持っていません"
                result["error"] = "item_not_in_inventory"
                self.bot.chat(result["message"])
                return result
                
            # 設置先のブロックをチェック
            target_block = self.bot.blockAt(target_dest)
            if target_block.name == block_name:
                result["message"] = f"{block_name}は既に座標({target_block.position})にあります"
                result["error"] = "block_already_exists"
                self.bot.chat(result["message"])
                return result
                
            # 設置可能な空間かチェック
            empty_blocks = ['air', 'water', 'lava', 'grass', 'short_grass', 'tall_grass', 'snow', 'dead_bush', 'fern']
            if target_block.name not in empty_blocks:
                result["message"] = f"座標({target_block.position})には既に{target_block.name}があります"
                
                # 破壊を試みる
                break_result = await self.break_block_at(x, y, z)
                if not break_result["success"]:
                    result["message"] = f"ブロックの設置場所に{target_block.name}があり、破壊できませんでした"
                    result["error"] = "space_occupied"
                    self.bot.chat(result["message"])
                    return result
                    
                # ブロックが破壊されるまで少し待機
                await asyncio.sleep(0.2)
                
            # 設置方向のマップを作成
            dir_map = {
            'top': Vec3(0, 1, 0),
            'bottom': Vec3(0, -1, 0),
            'north': Vec3(0, 0, -1),
            'south': Vec3(0, 0, 1),
            'east': Vec3(1, 0, 0),
            'west': Vec3(-1, 0, 0)
            }
        
            # 設置方向のリストを作成
            directions = []
            if place_on == 'side':
                # 側面への設置を優先
                directions.extend([dir_map['north'], dir_map['south'], dir_map['east'], dir_map['west']])
            elif place_on in dir_map:
                # 指定方向を優先
                directions.append(dir_map[place_on])
            else:
                # デフォルトは下面
                directions.append(dir_map['bottom'])
                result["message"] += f"\n不明な設置方向'{place_on}'が指定されました。デフォルトの'bottom'を使用します。"
                
            # 他の方向も追加（優先度は低い）
            for direction in dir_map.values():
                if not any(d.x == direction.x and d.y == direction.y and d.z == direction.z for d in directions):
                    directions.append(direction)
                    
            # 設置できるブロックを探す
            build_off_block = None
            face_vec = None
            
            for direction in directions:
                ref_pos = target_dest.plus(direction)
                ref_block = self.bot.blockAt(ref_pos)
                
                if ref_block and ref_block.name not in empty_blocks:
                    build_off_block = ref_block
                    # 方向を反転（設置面は反対側）
                    face_vec = Vec3(-direction.x, -direction.y, -direction.z)
                    break
                    
            # 設置できるブロックがない場合
            if not build_off_block:
                result["message"] = f"座標({target_dest})には設置できるブロックの面がありません"
                result["error"] = "no_adjacent_block"
                self.bot.chat(result["message"])
                return result
                
            # プレイヤーとブロックの位置関係をチェック
            player_pos = self.bot.entity.position
            player_pos_above = player_pos.plus(Vec3(0, 1, 0))
            
            # 一部のブロックは移動なしで設置可能
            dont_move_for = [
                'torch', 'redstone_torch', 'redstone_wire', 'lever', 'button', 
                'rail', 'detector_rail', 'powered_rail', 'activator_rail', 
                'tripwire_hook', 'tripwire', 'water_bucket'
            ]
            
            # ブロックの設置位置とプレイヤーが重なっていないか確認
            if block_name not in dont_move_for and (
                player_pos.distanceTo(target_block.position) < 1 or 
                player_pos_above.distanceTo(target_block.position) < 1
            ):
                # プレイヤーが設置位置と重なっている場合、少し離れる
                try:
                    if hasattr(self.pathfinder.goals, 'GoalNear') and hasattr(self.pathfinder.goals, 'GoalInvert'):
                        self.move_to_position(target_block.position.x, target_block.position.y, target_block.position.z, 2)
                except Exception as e:
                    result["message"] = f"設置位置から離れる際にエラーが発生しました: {str(e)}"
                    result["error"] = "movement_error"
                    self.bot.chat(result["message"])
                    return result
            
            # ブロックが遠すぎる場合は近づく
            if self.bot.entity.position.distanceTo(target_block.position) > 4.5:
                try:
                    if hasattr(self.pathfinder.goals, 'GoalNear'):
                        self.move_to_position(target_block.position.x, target_block.position.y, target_block.position.z, 4)
                except Exception as e:
                    result["message"] = f"ブロックに近づく際にエラーが発生しました: {str(e)}"
                    result["error"] = "movement_error"
                    self.bot.chat(result["message"])
                    return result
                    
            # ブロックを手に持つ
            self.bot.equip(block_item, 'hand')
            
            # 設置対象のブロックを見る
            self.bot.lookAt(build_off_block.position)
            
            # ブロックを設置
            try:
                self.bot.placeBlock(build_off_block, face_vec)
                result["message"] = f"{block_name}を座標({target_dest})に設置しました"
                result["success"] = True
                self.bot.chat(result["message"])
                
                # 設置完了を少し待つ
                await asyncio.sleep(0.2)
                return result
            except Exception as e:
                result["message"] = f"{block_name}の設置中にエラーが発生しました: {str(e)}"
                result["error"] = "block_placement_error"
                self.bot.chat(result["message"])
                return result
                
        except Exception as e:
            result["message"] = f"ブロック設置処理中に予期せぬエラーが発生しました: {str(e)}"
            result["error"] = "unexpected_error"
            self.bot.chat(result["message"])
            import traceback
            traceback.print_exc()
            return result
    
    async def equip(self, item_name):
        """
        指定されたアイテムを適切な装備スロットに装備します（道具や防具など）。
        
        Args:
            item_name (str): 装備するアイテムまたはブロックの名前
            
        Returns:
            dict: 結果を含む辞書
                - success (bool): 装備に成功した場合はTrue、失敗した場合はFalse
                - message (str): 結果メッセージ
                - item (str): 装備しようとしたアイテム名
        """
        result = {
            "success": False,
            "message": "",
            "item": item_name
        }
        
        try:
            # インベントリからアイテムを探す
            item = None
            for slot in self.bot.inventory.slots:
                if slot and slot.name == item_name:
                    item = slot
                    break
                    
            if not item:
                result["message"] = f"{item_name}を装備できません。インベントリにありません。"
                self.bot.chat(result["message"])
                return result
                
            # アイテムタイプに基づいて装備スロットを決定
            if "leggings" in item_name:
                self.bot.equip(item, "legs")
                slot_type = "脚"
            elif "boots" in item_name:
                self.bot.equip(item, "feet")
                slot_type = "足"
            elif "helmet" in item_name:
                self.bot.equip(item, "head")
                slot_type = "頭"
            elif "chestplate" in item_name or "elytra" in item_name:
                self.bot.equip(item, "torso")
                slot_type = "胴体"
            elif "shield" in item_name:
                self.bot.equip(item, "off-hand")
                slot_type = "オフハンド"
            else:
                self.bot.equip(item, "hand")
                slot_type = "メインハンド"
                
            result["success"] = True
            result["message"] = f"{item_name}を{slot_type}に装備しました。"
            self.bot.chat(result["message"])
            return result
            
        except Exception as e:
            result["message"] = f"{item_name}の装備中にエラーが発生しました: {str(e)}"
            self.bot.chat(result["message"])
            return result
            
    async def discard(self, item_name, num=-1):
        """
        指定されたアイテムを捨てます。
        
        Args:
            item_name (str): 捨てるアイテムまたはブロックの名前
            num (int): 捨てるアイテムの数。デフォルトは-1で、すべてのアイテムを捨てます。
            
        Returns:
            dict: 結果を含む辞書
                - success (bool): アイテムを捨てることに成功した場合はTrue、失敗した場合はFalse
                - message (str): 結果メッセージ
                - item (str): 捨てようとしたアイテム名
                - count (int): 捨てたアイテムの数
        """
        result = {
            "success": False,
            "message": "",
            "item": item_name,
            "count": 0
        }
        
        try:
            discarded = 0
            
            while True:
                # インベントリからアイテムを探す
                item = None
                for slot_item in self.bot.inventory.items():
                    if slot_item and slot_item.name == item_name:
                        item = slot_item
                        break
                
                if not item:
                    break
                
                # 捨てる数を計算
                to_discard = item.count if num == -1 else min(num - discarded, item.count)
                
                # アイテムを捨てる
                self.bot.toss(item.type, None, to_discard)
                discarded += to_discard
                
                # 指定した数だけ捨てたら終了
                if num != -1 and discarded >= num:
                    break
            
            if discarded == 0:
                result["message"] = f"{item_name}を捨てることができません。インベントリにありません。"
                self.bot.chat(result["message"])
                return result
            
            result["success"] = True
            result["count"] = discarded
            result["message"] = f"{discarded}個の{item_name}を捨てました。"
            self.bot.chat(result["message"])
            return result
            
        except Exception as e:
            result["message"] = f"{item_name}を捨てる際にエラーが発生しました: {str(e)}"
            self.bot.chat(result["message"])
            return result

    async def put_in_chest(self, item_name, num=-1):
        """
        指定されたアイテムを最も近いチェストに入れます。スタック数が１のツールなどは１つしか入れられません。その場合は、複数回実行してください

        Args:
            item_name (str): チェストに入れるアイテムまたはブロックの名前
            num (int): チェストに入れるアイテムの数。デフォルトは-1で、すべてのアイテムを入れます。
            
        Returns:
            dict: 結果を含む辞書
                - success (bool): アイテムをチェストに入れることに成功した場合はTrue、失敗した場合はFalse
                - message (str): 結果メッセージ
                - item (str): チェストに入れようとしたアイテム名
                - count (int): チェストに入れたアイテムの数
        """
        result = {
            "success": False,
            "message": "",
            "item": item_name,
            "count": 0
        }
        
        try:
            # 最も近いチェストを探す
            chest = await self.get_nearest_block("chest", 32)
            if not chest:
                result["message"] = "近くにチェストが見つかりませんでした。"
                self.bot.chat(result["message"])
                return result
                
            # インベントリからアイテムを探す
            item = None
            for slot_item in self.bot.inventory.items():
                if slot_item and slot_item.name == item_name:
                    item = slot_item
                    break
                    
            if not item:
                result["message"] = f"{item_name}をチェストに入れることができません。インベントリにありません。"
                self.bot.chat(result["message"])
                return result
                
            # チェストに入れる数を計算
            to_put = item.count if num == -1 else min(num, item.count)
            
            # チェストまで移動
            await self.move_to_position(chest.position.x, chest.position.y, chest.position.z, 2)
            
            # チェストを開く
            chest_container = self.bot.openContainer(chest)
            
            # アイテムをチェストに入れる
            chest_container.deposit(item.type, None, to_put)
            
            # チェストを閉じる
            chest_container.close()
            
            result["success"] = True
            result["count"] = to_put
            result["message"] = f"{to_put}個の{item_name}をチェストに入れました。"
            self.bot.chat(result["message"])
            return result
            
        except Exception as e:
            result["message"] = f"{item_name}をチェストに入れる際にエラーが発生しました: {str(e)}"
            self.bot.chat(result["message"])
            return result

    async def take_from_chest(self, item_name, num=-1):
        """
        指定されたアイテムを最も近いチェストから取り出します。
        
        Args:
            item_name (str): チェストから取り出すアイテムまたはブロックの名前
            num (int): チェストから取り出すアイテムの数。デフォルトは-1で、すべてのアイテムを取り出します。
            
        Returns:
            dict: 結果を含む辞書
                - success (bool): アイテムをチェストから取り出すことに成功した場合はTrue、失敗した場合はFalse
                - message (str): 結果メッセージ
                - item (str): チェストから取り出そうとしたアイテム名
                - count (int): チェストから取り出したアイテムの数
        """
        result = {
            "success": False,
            "message": "",
            "item": item_name,
            "count": 0
        }
        
        try:
            # 最も近いチェストを探す
            chest = await self.get_nearest_block("chest", 32)
            if not chest:
                result["message"] = "近くにチェストが見つかりませんでした。"
                self.bot.chat(result["message"])
                return result
                
            # チェストまで移動
            await self.move_to_position(chest.position.x, chest.position.y, chest.position.z, 2)
            
            # チェストを開く
            chest_container = self.bot.openContainer(chest)
            
            # チェスト内のアイテムを探す
            item = None
            for container_item in chest_container.containerItems():
                if container_item and container_item.name == item_name:
                    item = container_item
                    break
                    
            if not item:
                result["message"] = f"チェスト内に{item_name}が見つかりませんでした。"
                chest_container.close()
                self.bot.chat(result["message"])
                return result
                
            # 取り出す数を計算
            to_take = item.count if num == -1 else min(num, item.count)
            
            # アイテムをチェストから取り出す
            chest_container.withdraw(item.type, None, to_take)
            
            # チェストを閉じる
            chest_container.close()
            
            result["success"] = True
            result["count"] = to_take
            result["message"] = f"チェストから{to_take}個の{item_name}を取り出しました。"
            self.bot.chat(result["message"])
            return result
            
        except Exception as e:
            result["message"] = f"{item_name}をチェストから取り出す際にエラーが発生しました: {str(e)}"
            self.bot.chat(result["message"])
            return result

    async def view_chest(self,maxDistance=32):
        """
        近くにあるチェストに移動し、中身を表示します。複数チェストがある場合全てのチェストの中身を表示します。
        
        Returns:
            dict: 結果を含む辞書
                - success (bool): チェストを表示できた場合はTrue、失敗した場合はFalse
                - message (str): 結果メッセージ
                - result_list (list, optional): チェスト内のアイテムリスト（成功時のみ）

        Example:
            >>> view_chest()
            {
                'success': True, 
                'message': 'Found 2 chests.',
                'result_list':
                    [
                        {
                            'position': {'x': 1, 'y': -60, 'z': 4}, 
                            'items': [{'name': 'wooden_pickaxe', 'count': 1}, {'name': 'wooden_pickaxe', 'count': 1}, {'name': 'wooden_pickaxe', 'count': 1}, {'name': 'wooden_pickaxe', 'count': 1}]
                        }, 
                        {
                            'position': {'x': -2, 'y': -60, 'z': 0}, 
                            'items': 'チェストは空です。'
                        }
                    ]
            }
        """
        result = {
            "success": False,
            "message": ""
        }
        
        try:
            # 最も近いチェストを探す
            chest = self.bot.findBlocks({
                'matching':self.mcdata.blocksByName['chest'].id,
                'maxDistance': maxDistance,
                'count': 10
            })
            if not any(True for _ in chest):
                result["message"] = "近くにチェストが見つかりませんでした。"
                self.bot.chat(result["message"])
                return result
            
            result_list = []
            for chest_pos in chest:
                # チェストまで移動
                move_result = await self.move_to_position(chest_pos.x, chest_pos.y, chest_pos.z, 2)
                if not move_result["success"]:
                    result["message"] = f"チェストへの移動に失敗: {move_result.get('message', '不明なエラー')}"
                    self.bot.chat(result["message"])
                    return result
            
                # チェストを開く
                chest_block = self.bot.blockAt(chest_pos)
                chest_container = self.bot.openContainer(chest_block)
            
                # チェスト内のアイテムを取得
                items = chest_container.containerItems()
            
                # アイテムをリストに変換
                item_list = []
                result_dict = {}
                if items:
                    for item in items:
                        if item:  # Noneでないアイテムのみ追加
                            item_list.append({
                                "name": item.name,
                                "count": item.count
                            })
                if not item_list:
                    result_dict["position"] = {"x": chest_pos.x, "y": chest_pos.y, "z": chest_pos.z}
                    result_dict["items"] = "チェストは空です。"
                else:
                    result_dict["position"] = {"x": chest_pos.x, "y": chest_pos.y, "z": chest_pos.z}
                    result_dict["items"] = item_list
                result_list.append(result_dict)
                
                chest_container.close()
            
            result["success"] = True
            result["message"] = f"Found {len(result_list)} chests."
            result["result_list"] = result_list
            return result
            
        except Exception as e:
            result["message"] = f"チェストの表示中にエラーが発生しました: {str(e)}"
            self.bot.chat(result["message"])
            return result

    async def consume(self, item_name=""):
        """
        指定されたアイテムを1つ食べる/飲みます。
        満腹度が最大の場合は消費できません。
        
        Args:
            item_name (str): 食べる/飲むアイテムの名前。デフォルトは空文字列で、その場合は手に持っているアイテムを消費します。
        """
        result = {
            "success": False,
            "message": ""
        }
        
        try:
            # 満腹度チェック
            if hasattr(self.bot, 'food') and self.bot.food >= 20:
                result["message"] = "満腹度が最大のため、これ以上食べ物を消費できません。"
                self.bot.chat(result["message"])
                return result

            item = None
            name = item_name
            
            # アイテム名が指定されている場合はインベントリから探す
            if item_name:
                for inv_item in self.bot.inventory.items():
                    if inv_item.name == item_name:
                        item = inv_item
                        break
            
            # アイテムが見つからない場合
            if not item:
                result["message"] = f"{name if name else '指定されたアイテム'}を消費できません。インベントリにアイテムがありません。"
                self.bot.chat(result["message"])
                return result
                
            # アイテムを手に持つ
            self.bot.equip(item, 'hand')
            
            # アイテムを消費
            self.bot.consume()
            
            result["success"] = True
            result["item"] = item.name
            result["message"] = f"{item.name}を消費しました。"
            self.bot.chat(result["message"])
            return result
            
        except Exception as e:
            result["message"] = f"アイテム消費中にエラーが発生しました: {str(e)}"
            self.bot.chat(result["message"])
            return result

    async def go_to_nearest_block(self, block_name, min_distance=2, range=64):
        """
        指定されたタイプの最も近いブロックまで移動します。
        
        Args:
            block_name (str): 移動先のブロック名
            min_distance (int): ブロックから保つ距離。デフォルトは2
            range (int): ブロックを探す最大範囲。デフォルトは64
            
        Returns:
            dict: 結果を含む辞書
                - success (bool): ブロックまで移動できた場合はTrue、失敗した場合はFalse
                - message (str): 結果メッセージ
                - block_name (str): 探したブロック名
                - position (dict, optional): 見つかったブロックの位置 {x, y, z}（成功時のみ）
        """
        result = {
            "success": False,
            "message": "",
            "block_name": block_name
        }
        
        try:
            # 最大検索範囲の制限
            MAX_RANGE = 512
            if range > MAX_RANGE:
                range = MAX_RANGE
                self.bot.chat(f"最大検索範囲を{MAX_RANGE}ブロックに制限します。")
                
            # 最も近いブロックを探す
            block = await self.get_nearest_block(self._get_item_id(block_name), range)
            if not block:
                result["message"] = f"{range}ブロック以内に{block_name}が見つかりませんでした。"
                self.bot.chat(result["message"])
                return result
                
            # ブロックの位置を取得
            position = block.position
            result["position"] = {
                "x": position.x,
                "y": position.y,
                "z": position.z
            }
            
            # ブロックまで移動
            move_result = await self.move_to_position(position.x, position.y, position.z, min_distance)
            if not move_result["success"]:
                result["message"] = f"{block_name}への移動中にエラーが発生しました: {move_result['message']}"
                self.bot.chat(result["message"])
                return result
                
            result["success"] = True
            result["message"] = f"{block_name}(X:{position.x}, Y:{position.y}, Z:{position.z})に到達しました。"
            self.bot.chat(result["message"])
            return result
            
        except Exception as e:
            result["message"] = f"{block_name}への移動中に予期せぬエラーが発生しました: {str(e)}"
            self.bot.chat(result["message"])
            import traceback
            traceback.print_exc()
            return result

    async def go_to_nearest_entity(self, entity_type, min_distance=2, range=64):
        """
        指定されたタイプの最も近いエンティティまで移動します。
        
        Args:
            entity_type (str): 移動先のエンティティタイプ（例: "zombie", "sheep", "villager"など）
            min_distance (int): 移動後、エンティティと保つ距離。デフォルトは2
            range (int): エンティティを探す最大範囲。デフォルトは64
            
        Returns:
            dict: 結果を含む辞書
                - success (bool): エンティティまで移動できた場合はTrue、失敗した場合はFalse
                - message (str): 結果メッセージ
                - entity_type (str): 探したエンティティタイプ
                - position (dict, optional): エンティティの位置 {x, y, z}（成功時のみ）
                - distance (float, optional): 元の位置からエンティティまでの距離（成功時のみ）
        """
        result = {
            "success": False,
            "message": "",
            "entity_type": entity_type
        }
        
        try:
            # 指定されたタイプのエンティティを探す
            entity = self._get_nearby_entity_of_type(entity_type, range)
            if not entity:
                result["message"] = f"{range}ブロック以内に{entity_type}が見つかりませんでした。"
                self.bot.chat(result["message"])
                return result
                
            # エンティティの位置を取得
            position = entity.position
            result["position"] = {
                "x": position.x,
                "y": position.y,
                "z": position.z
            }
            
            # エンティティまでの距離を計算
            distance = self.bot.entity.position.distanceTo(position)
            result["distance"] = distance
            
            # エンティティが見つかったことを通知
            self.bot.chat(f"{entity_type}が{distance}ブロック先で見つかりました。")
            
            # エンティティまで移動
            move_result = await self.move_to_position(position.x, position.y, position.z, min_distance)
            if not move_result["success"]:
                result["message"] = f"{entity_type}への移動中にエラーが発生しました: {move_result['message']}"
                self.bot.chat(result["message"])
                return result
                
            result["success"] = True
            result["message"] = f"{entity_type}に到達しました。"
            self.bot.chat(result["message"])
            return result
            
        except Exception as e:
            result["message"] = f"{entity_type}への移動中に予期せぬエラーが発生しました: {str(e)}"
            self.bot.chat(result["message"])
            import traceback
            traceback.print_exc()
            return result

    async def go_to_bed(self):
        """
        最も近いベッドで寝ます。
        
        Returns:
            dict: 結果を含む辞書
                - success (bool): ベッドで寝ることができた場合はTrue、失敗した場合はFalse
                - message (str): 結果メッセージ
                - bed_position (dict, optional): ベッドの位置 {x, y, z}（成功時のみ）
        """
        result = {
            "success": False,
            "message": ""
        }
        
        try:
            # 時間と天候をチェック
            if not (self.bot.time.isNight or self.bot.isRaining):
                result["message"] = "まだ寝る時間ではありません。夜または雷雨の時のみ寝ることができます。"
                self.bot.chat(result["message"])
                return result
            
            # 近くのベッドを探す
            # isABedメソッドを使用してベッドを検索
            beds = self.bot.findBlocks({
                'matching': self.bot.isABed,
                'maxDistance': 32,
                'count': 1
            })
            
            if not beds or not any(True for _ in beds):
                result["message"] = "寝るためのベッドが32ブロック以内に見つかりませんでした。"
                self.bot.chat(result["message"])
                return result
                
            # ベッドの位置を取得
            bed_pos = beds[0]
            result["bed_position"] = {
                "x": bed_pos.x,
                "y": bed_pos.y,
                "z": bed_pos.z
            }
            
            # ベッドまで移動
            await self.move_to_position(bed_pos.x, bed_pos.y, bed_pos.z)
            
            # ベッドのブロックを取得
            bed = self.bot.blockAt(bed_pos)
            
            try:
                # ベッドで寝る
                await self.bot.sleep(bed)
                result["success"] = True
                result["message"] = "ベッドで寝ることに成功しました。"
                self.bot.chat(result["message"])
                
            except Exception as e:
                result["message"] = f"ベッドで寝る際にエラーが発生しました: {str(e)}"
                self.bot.chat(result["message"])
                
            return result
            
        except Exception as e:
            result["message"] = f"ベッドで寝る際にエラーが発生しました: {str(e)}"
            self.bot.chat(result["message"])
            import traceback
            traceback.print_exc()
            return result

    async def move_away(self, distance):
        """
        現在の位置から任意の方向に指定した距離だけ離れます。
        
        Args:
            distance (int): 移動する距離
            
        Returns:
            dict: 結果を含む辞書
                - success (bool): 移動に成功した場合はTrue、失敗した場合はFalse
                - message (str): 結果メッセージ
                - start_position (dict): 開始位置 {x, y, z}
                - end_position (dict, optional): 移動後の位置 {x, y, z}（成功時のみ）
        """
        result = {
            "success": False,
            "message": "",
            "start_position": {
                "x": self.bot.entity.position.x,
                "y": self.bot.entity.position.y,
                "z": self.bot.entity.position.z
            }
        }
        
        try:
            # 現在位置を取得
            current_pos = self.bot.entity.position
            
            # GoalNearとGoalInvertを使用して現在位置から離れるゴールを設定
            if hasattr(self.pathfinder.goals, 'GoalNear') and hasattr(self.pathfinder.goals, 'GoalInvert'):
                goal = self.pathfinder.goals.GoalNear(current_pos.x, current_pos.y, current_pos.z, distance)
                inverted_goal = self.pathfinder.goals.GoalInvert(goal)
                
                # パスファインダーの設定
                self.bot.pathfinder.setMovements(self.pathfinder.Movements(self.bot))
                
                # チートモードの場合はテレポート
                if hasattr(self.bot.modes, 'isOn') and self.bot.modes.isOn('cheat'):
                    try:
                        move = self.pathfinder.Movements(self.bot)
                        path = self.bot.pathfinder.getPathTo(move, inverted_goal, 10000)
                        
                        if path and path.path and len(path.path) > 0:
                            last_move = path.path[len(path.path) - 1]
                            
                            if last_move:
                                x = int(last_move.x)
                                y = int(last_move.y)
                                z = int(last_move.z)
                                
                                self.bot.chat(f"/tp @s {x} {y} {z}")
                                result["success"] = True
                                result["message"] = f"現在位置から{distance}ブロック離れた座標({x}, {y}, {z})にテレポートしました。"
                                result["end_position"] = {"x": x, "y": y, "z": z}
                                self.bot.chat(result["message"])
                                return result
                    except Exception as e:
                        print(f"チートモードでの移動計算エラー: {e}")
                        # 通常の移動を試みる
                
                # パスファインダーを使って移動
                self.bot.pathfinder.goto(inverted_goal)
                
                # 新しい位置を取得
                new_pos = self.bot.entity.position
                result["end_position"] = {
                    "x": new_pos.x,
                    "y": new_pos.y,
                    "z": new_pos.z
                }
                
                result["success"] = True
                result["message"] = f"現在位置から{distance}ブロック離れた座標({new_pos.x:.1f}, {new_pos.y:.1f}, {new_pos.z:.1f})に移動しました。"
                self.bot.chat(result["message"])
                return result
            else:
                result["message"] = "パスファインダーのゴール機能が利用できません。"
                self.bot.chat(result["message"])
                return result
                
        except Exception as e:
            result["message"] = f"移動中に予期せぬエラーが発生しました: {str(e)}"
            self.bot.chat(result["message"])
            import traceback
            traceback.print_exc()
            return result

    async def avoid_enemies(self, distance=16):
        """
        周囲の敵対的なエンティティから逃げます。
        近くの全ての敵対的エンティティから最も離れる場所探し移動します。目的地到着後停止します。
        
        Args:
            distance (int): 逃げる最大距離
            
        Returns:
            dict: 結果を含む辞書
        """
        result = {
            "success": False,
            "message": ""
        }
        
        # 近くの全てのエンティティを取得
        nearby_entities = self._get_nearby_entities(distance)
        
        # 敵対的なエンティティをフィルタリング
        hostile_entities = [entity for entity in nearby_entities if self._is_hostile(entity)]
        
        if not hostile_entities:
            result["message"] = "近くに敵対的なエンティティはいません。"
            self.bot.chat(result["message"])
            return result
            
        self.bot.chat(f"{len(hostile_entities)}体の敵対的なエンティティから逃げます。")
        
        # 現在のプレイヤーの位置
        player_pos = self.bot.entity.position
        
        # 各敵からの反発ベクトルを計算（各敵からプレイヤーを遠ざける方向）
        escape_vector = {'x': 0, 'y': 0, 'z': 0}
        
        for entity in hostile_entities:
            # エンティティからプレイヤーへの方向ベクトル
            dx = player_pos.x - entity.position.x
            dy = player_pos.y - entity.position.y
            dz = player_pos.z - entity.position.z
            
            # エンティティとの距離
            dist = (dx**2 + dy**2 + dz**2) ** 0.5
            
            if dist < 0.1:  # 極端に近い場合、少しランダムな方向に逃げる
                import random
                dx = random.uniform(-1, 1)
                dz = random.uniform(-1, 1)
                dist = (dx**2 + dz**2) ** 0.5
            
            # 距離の逆数を重みとして使用（近い敵からより強く逃げる）
            weight = 1.0 / (dist + 0.1)  # 0除算を防ぐ
            
            # 正規化（単位ベクトル化）して重み付け
            norm = (dx**2 + dz**2) ** 0.5  # 水平方向の距離
            if norm > 0:
                escape_vector['x'] += (dx / norm) * weight
                escape_vector['z'] += (dz / norm) * weight
        
        # 最終的な移動距離を計算（ベクトルの正規化）
        magnitude = (escape_vector['x']**2 + escape_vector['z']**2) ** 0.5
        if magnitude > 0:
            escape_vector['x'] /= magnitude
            escape_vector['z'] /= magnitude
        else:
            # 全方向から均等に敵がいる場合はランダムな方向に逃げる
            import random
            angle = random.uniform(0, 2 * 3.14159)
            escape_vector['x'] = math.cos(angle)
            escape_vector['z'] = math.sin(angle)
        
        # 最終的な目標位置を計算（現在位置 + 移動距離 * 方向ベクトル）
        target_x = player_pos.x + distance * escape_vector['x'] # 敵から離れる方向
        target_z = player_pos.z + distance * escape_vector['z'] # 敵から離れる方向
        
        # 目的地に移動
        self.bot.chat(f"x:{target_x:.1f}, z:{target_z:.1f}の方向に逃げます。")
        await self.move_to_position(target_x, player_pos.y, target_z, min_distance=2,canDig=False)
        
        result["success"] = True
        result["message"] = "敵対的なエンティティから逃げました。"
        self.bot.chat(result["message"])
        return result

    async def collect_block(self, block_name, num=1, exclude=None):
        """
        指定された名前のブロックを収集します。
        最も近くにある安全に採掘可能なブロックを探し、適切なツールを装備して収集を試みます。
        インベントリがいっぱいの場合や適切なツールがない場合などは失敗します。

        Args:
            block_name (str): 収集するブロックの名前 (例: "oak_log", "stone", "coal_ore")。
                            鉱石の場合、"coal" のように指定しても "coal_ore" や "deepslate_coal_ore" を探します。
                            "dirt" を指定すると "grass_block" も対象になります。
            num (int, optional): 収集する目標のブロック数。Defaults to 1.
            exclude (list[Vec3], optional): 収集対象から除外するブロックの座標 (Vec3オブジェクト) のリスト。
                                         特定の場所にあるブロックを無視したい場合に使用します。Defaults to None.

        Returns:
            dict: 収集結果の詳細を含む辞書。
                - success (bool): 1つ以上のブロック収集に成功した場合 True、そうでなければ False。
                - message (str): 処理結果を示すメッセージ。
                - collected (int): 実際に収集できたブロックの数。
                - block_name (str): 収集しようとした元のブロック名。
                - error (str, optional): エラーが発生した場合のエラーコード。
        Example:
            >> await skills.collect_block('cobblestone', num=11)
            {
                "success": True,
                "message": "11個のcobblestoneを収集しました。",
                "collected": 11,
                "block_name": "cobblestone"
            }
            >> await skills.collect_block('Jungle Log', num=11)
            {
                'success': False,
                'message': '近くにJungle Logが見つかりません。',
                'collected': 0,
                'block_name': 'Jungle Log',
                'error': 'no_blocks_found'
            }
        """
        result = {
            "success": False,
            "message": "",
            "collected": 0,
            "block_name": block_name
        }
        print(f"{block_name}のブロックを取得します。")
        if num < 1:
            result["message"] = f"無効な収集数量: {num}"
            result["error"] = "invalid_number"
            print(result["message"])
            return result
        
        # 同等のブロックタイプをリストに追加
        blocktypes = [block_name]
        
        # 特殊処理: 鉱石ブロックの対応を追加
        ores = ['coal', 'diamond', 'emerald', 'iron', 'gold', 'lapis_lazuli', 'redstone']
        if block_name in ores:
            blocktypes.append(f"{block_name}_ore")
        # 深層岩鉱石の対応
        if block_name.endswith('ore'):
            blocktypes.append(f"deepslate_{block_name}")
        # dirtの特殊処理
        if block_name == 'dirt':
            blocktypes.append('grass_block')

        collected = 0
        
        for i in range(num):
            blocks = []
            for btype in blocktypes:
                found_block = await self.get_nearest_block(btype, 64)
                await asyncio.sleep(0.1)
                if found_block:
                    blocks.append(found_block)
            
            # 除外位置のフィルタリング
            if exclude and blocks:
                blocks = [block for block in blocks if not any(
                    block.position.x == pos.x and 
                    block.position.y == pos.y and 
                    block.position.z == pos.z 
                    for pos in exclude
                )]
            # 安全に採掘可能なブロックのフィルタリング
            movements = self.bot.pathfinder.movements
            movements.dontMineUnderFallingBlock = False
            blocks = [block for block in blocks if movements.safeToBreak(block)]
            if not blocks:
                if collected == 0:
                    result["message"] = f"近くに{block_name}が見つかりません。"
                else:
                    result["message"] = f"これ以上{block_name}が見つかりません。"
                result["error"] = "no_blocks_found"
                break
                
            block = blocks[0]
            block_pos = block.position
            # 適切なツールを装備
            self.bot.tool.equipForBlock(block)
            if self.bot.heldItem:
                held_item_id = self.bot.heldItem.type
            else:
                held_item_id = None
            if not block.canHarvest(held_item_id):
                self.bot.chat(f"{str(block_name)}を採掘するための適切なツールがありません。")
                result["message"] = f"{block_name}を採掘するための適切なツールがありません。"
                result["error"] = "no_suitable_tool"
                print(result["message"])
                return result
            try:
                move_to_result = await self.move_to_position(block_pos.x, block_pos.y, block_pos.z, min_distance=2)
                if move_to_result["success"]:
                    self.bot.collectBlock.collect(block)
                    collected += 1
                    await self.auto_light()
                else:
                    result["message"] = f"{block_name}の収集に失敗: {move_to_result['message']}"
                    result["error"] = "move_to_failed"
                    print(result["message"])
                    return result
            except Exception as e:
                if str(e) == 'NoChests':
                    result["message"] = f"{block_name}の収集に失敗: インベントリが一杯で、保管場所がありません。"
                    result["error"] = "inventory_full"
                    print(result["message"])
                    break
                else:
                    result["message"] = f"{block_name}の収集に失敗: {str(e)}"
                    result["error"] = "collection_failed"
                    print(result["message"])
                    continue
                    
        result["collected"] = collected
        result["success"] = collected > 0
        if not result["message"]:
            result["message"] = f"{block_name}を{collected}個収集しました。"
        
        print(result)
        return result
        
    async def should_place_torch(self):
        """
        松明を設置すべきかどうかを周辺にある松明の有無およびインベントリに松明があるかどうかの基づいて判断します。
        
        Returns:
            bool: 松明を設置すべき場合はTrue、そうでない場合はFalse
        """
        pos = self.bot.entity.position
        
        # 近くの松明を探す
        nearest_torch =await self.get_nearest_block('torch', 6)
        if not nearest_torch:
            nearest_torch = await self.get_nearest_block('wall_torch', 6)
            
        # 近くに松明がない場合
        if not nearest_torch:
            # 現在位置のブロックを確認
            block = self.bot.blockAt(pos)
            
            # インベントリに松明があるかチェック
            has_torch = False
            if hasattr(self.bot, 'inventory') and hasattr(self.bot.inventory, 'items'):
                for item in self.bot.inventory.items():
                    if item and hasattr(item, 'name') and item.name == 'torch':
                        has_torch = True
                        break
                    
            # 現在位置が空気で、松明を持っている場合に設置可能
            return has_torch and block and hasattr(block, 'name') and block.name == 'air'
            
        return False
        
    async def auto_light(self):
        """
        周りに松明がない場合、インベントリに松明がある場合、現在位置が空気である場合に松明を設置します。
        
        Returns:
            bool: 松明を設置した場合はTrue、そうでない場合はFalse
        """
        try:
            if await self.should_place_torch():
                pos = self.bot.entity.position
                Vec3 = require('vec3')
                # 足元に松明を設置
                floor_pos = Vec3(
                    round(pos.x),
                    round(pos.y) - 1,  # 足元
                    round(pos.z)
                )
                
                # 松明を設置
                result = await self.place_block('torch', floor_pos.x, floor_pos.y + 1, floor_pos.z, 'bottom')
                
                if result:
                    # 最後に松明を設置した位置を記録
                    self._last_torch_pos = pos.clone()
                    return True
            return False
        except Exception as e:
            print(f"松明設置エラー: {e}")
            return False
            
    def get_all_registry_blocks(self):
        """
        レジストリに登録されているすべてのブロック名を取得します。
        デバッグ目的で使用します。
        
        Returns:
            list: ブロック名のリスト
        """
        block_names = []
        try:
            if hasattr(self.bot.registry, 'blocksByName'):
                for block_name in self.bot.registry.blocksByName:
                    block_names.append(block_name)
                    
            return sorted(block_names)
        except Exception as e:
            print(f"ブロック名取得エラー: {e}")
            return []
        
    async def move_to_position(self, x, y, z, min_distance=2,
                               canDig=True,
                               canPlaceOn=True,
                               allow1by1towers=False,
                               dontcreateflow=True,
                               dontMineUnderFaillingBlock=True,
                               dontMoveUnderLiquid=True,
                               onlyCheckPath=False,
                               move_timeout=60): # タイムアウト引数を追加
        """
        指定された位置に移動します。
        現在位置と目標位置が十分に近い場合（min_distance以内）は移動をスキップします。
        移動中にスタックを検出した場合は、一時的な目標地点に移動して解消を試みます。
        パスを取得できない場合は、目標位置に到達できる経路を生成できませんでしたというメッセージを返します。
        dontMoveUnderLiquidがTrueの場合、移動先が液体ブロックの場合、エラーを返します。
        指定時間内に移動が完了しない場合はタイムアウトします。

        Args:
            x (float): 移動先のX座標
            y (float): 移動先のY座標
            z (float): 移動先のZ座標
            min_distance (int): 目標位置からの最小距離。デフォルトは2
            canDig (bool): 移動の障害となるブロックを破壊するかどうか。デフォルトはTrue
            canPlaceOn (bool): 移動時にブロックの設置を許可するかどうか。デフォルトはTrue
            allow1by1towers (bool): 1x1の塔を作って登ることを許可するかどうか。デフォルトはFalse
            dontcreateflow (bool):  移動の障害となる液体ブロックに接触するブロックを掘らないかどうか。デフォルトはTrue
            dontMineUnderFaillingBlock (bool):砂などの落下ブロックの下で掘るのを許可するか。デフォルトはTrue
            dontMoveUnderLiquid (bool):移動先として指定された座標が、液体ブロックの場合、エラーを返すかどうか。デフォルトはTrue
            onlyCheckPath (bool): 移動先に移動可能かどうかをチェックする。デフォルトはFalse
            move_timeout (int): 移動のタイムアウト時間（秒）。デフォルトは60

        Returns:
            dict: 移動結果を含む辞書
                - success (bool): 移動に成功した場合はTrue、失敗した場合はFalse
                - error (str): 移動に失敗した場合のエラーコード(path_not_found, path_timeout, move_timeout, liquid_block, unexpected_error, move_failed)
                - message (str): 移動結果のメッセージ
                - position (dict): 移動後の座標 (例: {"x": 10, "y": 20, "z": 30})
        """
        if not onlyCheckPath:
            print(f"{x}, {y}, {z}に移動します。")
        # 現在位置と目標位置を取得
        current_pos = self.bot.entity.position

        result = {
            "success": False,
            "error": "",
            "message": "",
            "position": {
                "x": current_pos.x,
                "y": current_pos.y,
                "z": current_pos.z
            }
        }

        # 現在位置と目標位置の距離を計算
        distance_to_target = ((current_pos.x - x) ** 2 +
                              (current_pos.y - y) ** 2 +
                              (current_pos.z - z) ** 2) ** 0.5
        # 既に目標位置に十分近い場合は移動をスキップ
        if distance_to_target <= min_distance:
            result["success"] = True
            result["message"] = f"既に目標位置 {x}, {y}, {z} の近く（{distance_to_target:.2f}ブロック）にいます。移動をスキップします。"
            # positionを更新
            result["position"] = { "x": current_pos.x, "y": current_pos.y, "z": current_pos.z }
            print(result["message"])
            return result
        if dontMoveUnderLiquid:
            Vec3 = require('vec3')
            target_block = self.bot.blockAt(Vec3(x, y, z))
            if target_block and (target_block.name == 'water' or target_block.name == 'lava'):
                result["message"] = f"目標位置 {x}, {y}, {z} は液体ブロックです。溺れる・焼け死ぬ可能性があるため、移動を中止します。"
                result["error"] = "liquid_block"
                print(result["message"])
                return result

        try:
            # 目標位置を設定
            goal = self.pathfinder.goals.GoalNear(x, y, z, min_distance)
            # パスファインダーの動きを設定
            movements = self.pathfinder.Movements(self.bot)
            movements.canDig = canDig
            movements.dontCreateFlow = dontcreateflow
            movements.dontMineUnderFaillingBlock = dontMineUnderFaillingBlock
            movements.canPlaceOn = canPlaceOn
            movements.allow1by1towers = allow1by1towers
            self.bot.pathfinder.setMovements(movements)
            # パスを取得
            path = self.bot.pathfinder.getPathTo(movements,goal)
            if path.status == "error":
                result["message"] = f"目標位置に到達できる経路を生成できませんでした。目的地が水中・溶岩にあるか、現在の装備では採掘出来ないブロック・空間に阻まれています"
                result["error"] = "path_not_found"
                self.bot.chat(result["message"])
                return result
            elif path.status == "timeout":
                result["message"] = f"パスの生成がタイムアウトしました。目標位置が遠すぎる可能性があります"
                result["error"] = "path_timeout"
                self.bot.chat(result["message"])
                return result
            if onlyCheckPath:
                result["success"] = True
                result["message"] = f"目標位置 {x}, {y}, {z} に移動可能です。"
                return result
            # 目標に向かう
            self.bot.pathfinder.setGoal(goal)
            await asyncio.sleep(0.5)

            last_position = None
            stuck_time = 0
            temp_free_space = None
            move_start_time = asyncio.get_event_loop().time() # 移動開始時間を記録
            while self.bot.pathfinder.isMoving():
                # --- タイムアウトチェック ---
                current_time = asyncio.get_event_loop().time()
                if (current_time - move_start_time) > move_timeout:
                    print(f"移動がタイムアウトしました ({move_timeout}秒)。")
                    self.bot.pathfinder.setGoal(None) # 目的地をリセット
                    await asyncio.sleep(0.1) # ゴールリセットの反映を待つ
                    result["success"] = False
                    result["message"] = f"移動がタイムアウトしました ({move_timeout}秒)。"
                    result["error"] = "move_timeout"
                    # 現在位置を記録
                    current_pos_timeout = await self.get_bot_position()
                    result["position"] = { "x": current_pos_timeout[0], "y": current_pos_timeout[1], "z": current_pos_timeout[2] }
                    return result
                # --- ここまで追加 ---
                
                mining = self.bot.pathfinder.isMining()
                building = self.bot.pathfinder.isBuilding()
                current_position = self.bot.entity.position
                # スタック検出ロジック
                if not mining and not building:
                    if last_position and (
                        abs(current_position.x - last_position.x) < 0.01 and
                        abs(current_position.y - last_position.y) < 0.01 and
                        abs(current_position.z - last_position.z) < 0.01
                    ):
                        stuck_time += 1
                    else:
                        stuck_time = 0

                    # 2秒以上同じ位置でスタックしている場合
                    if stuck_time >= 2:
                        self.bot.chat("スタックを検出しました。解消を試みます。")
                        free_space = None
                        search_distance = 100
                        while free_space is None and search_distance < 500: # 無限ループ防止
                            free_space = await self.get_nearest_free_space(X_size=1,Y_size=2,Z_size=1,distance=search_distance)
                            if free_space:
                                break
                            search_distance += 100

                        if free_space is None:
                            self.bot.chat("近くに一時退避できるスペースが見つかりません。移動を中断します。")
                            self.bot.pathfinder.setGoal(None) # 目的地リセット
                            await asyncio.sleep(0.1)
                            result["success"] = False
                            result["message"] = "スタック解消中に退避スペースが見つからず、移動を中断しました。"
                            result["error"] = "stuck_no_space"
                            current_pos_stuck = await self.get_bot_position()
                            result["position"] = { "x": current_pos_stuck[0], "y": current_pos_stuck[1], "z": current_pos_stuck[2] }
                            return result

                        if temp_free_space and temp_free_space.x == free_space.x and temp_free_space.y == free_space.y and temp_free_space.z == free_space.z:
                            # 一時的な移動で解消出来なければワープ (これはBotの能力に依存、通常は推奨されない)
                            # self.bot.chat(f"/tp bot {free_space.x} {free_space.y} {free_space.z}")
                            self.bot.chat("一時退避を試みましたがスタックが解消できませんでした。移動を中断します。")
                            self.bot.pathfinder.setGoal(None)
                            await asyncio.sleep(0.1)
                            result["success"] = False
                            result["message"] = "スタック解消に失敗しました。移動を中断します。"
                            result["error"] = "stuck_unresolved"
                            current_pos_stuck_fail = await self.get_bot_position()
                            result["position"] = { "x": current_pos_stuck_fail[0], "y": current_pos_stuck_fail[1], "z": current_pos_stuck_fail[2] }
                            return result
                        else:
                            # 一時的な目標地点に移動
                            temp_goal = self.pathfinder.goals.GoalNear(free_space.x, free_space.y, free_space.z, 0)
                            self.bot.pathfinder.setGoal(temp_goal)
                            temp_free_space = free_space
                            self.bot.chat(f"一時的に {free_space.x:.1f}, {free_space.y:.1f}, {free_space.z:.1f} へ移動します。")
                            await asyncio.sleep(2) # 一時目標への移動を待つ

                        # 元の目標地点に再設定
                        self.bot.pathfinder.setGoal(goal)
                        self.bot.chat("元の目標への移動を再開します。")
                        await asyncio.sleep(0.5)
                        stuck_time = 0
                        move_start_time = asyncio.get_event_loop().time() # スタック解消後、タイマーリセット

                last_position = current_position
                await asyncio.sleep(0.5) # ループのインターバル
            # 移動完了後、パスファインダーのゴールをリセット
            self.bot.pathfinder.setGoal(None)
            # --- 移動完了後の処理 ---
            bot_x, bot_y, bot_z = await self.get_bot_position()
            # 目標位置との距離を計算 (インデント修正)
            final_distance = ((bot_x - x) ** 2 + (bot_y - y) ** 2 + (bot_z - z) ** 2) ** 0.5
            if final_distance <= min_distance:
                result["success"] = True
                result["message"] = f"目標位置 {x}, {y}, {z} の {min_distance} ブロック以内に到達しました (距離: {final_distance:.2f})。"
            else:
                # isMoving()がFalseでも距離が遠い場合 (パスの終点が目標から遠いなど)
                result["success"] = False
                result["message"] = f"移動は停止しましたが、目標位置 {x}, {y}, {z} に到達できませんでした。現在の位置は {bot_x:.1f}, {bot_y:.1f}, {bot_z:.1f} (目標までの距離: {final_distance:.2f}) です。"
                result["error"] = "move_failed"
            result["position"] = {
                "x": bot_x,
                "y": bot_y,
                "z": bot_z
            }
            print(result["message"])

        except Exception as e:
            result["message"] = f"移動中に予期せぬエラーが発生しました: {str(e)}"
            self.bot.chat(result["message"])
            import traceback
            traceback.print_exc()
            result["error"] = "unexpected_error"
            # エラー発生時の位置を記録
            try:
                error_pos = await self.get_bot_position()
                result["position"] = { "x": error_pos[0], "y": error_pos[1], "z": error_pos[2] }
            except: # get_bot_positionも失敗する可能性
                 result["position"] = {"x": None, "y": None, "z": None}


        return result
        
    async def smelt_item(self, item_name, num=1):
        """
        32ブロック以内にある「かまど」または、インベントリに「かまど」がある場合、「かまど」にアイテムを入れて精錬します。燃料として石炭、木炭、木材を使用します。
        精錬が完了するまで待機し、完了したアイテムを回収します。
        
        Args:
            item_name (str): 精錬するアイテム名（例: "raw_iron", "raw_copper", "beef"など）
            num (int): 精錬するアイテムの数。デフォルトは1
            
        Returns:
            dict: 結果を含む辞書
                - success (bool): 精錬に成功した場合はTrue、失敗した場合はFalse
                - message (str): 結果メッセージ
                - smelted (int): 精錬したアイテムの数
                - item_name (str): 精錬したアイテム名
                - error (str, optional): エラーがある場合のエラーコード
        """
        self.bot.chat(f"{item_name}を精錬します。")
        result = {
            "success": False,
            "message": "",
            "smelted": 0,
            "item_name": item_name,
        }
        
        # 精錬可能なアイテムか確認
        is_smeltable = self._is_smeltable(item_name)
        if not is_smeltable:
            result["message"] = f"{item_name}は精錬できません。「raw_」で始まる生の鉱石や食材を指定してください。"
            result["error"] = "not_smeltable"
            self.bot.chat(result["message"])
            return result
            
        # かまどを探す
        placed_furnace = False
        furnace_block = await self.get_nearest_block('furnace', 32)
        if not furnace_block:
            # かまどを持っているか確認
            if (await self.get_inventory_counts()).get('furnace', 0) > 0:
                # かまどを設置
                pos = await self.get_nearest_free_space(X_size=1,Z_size=1,distance=15)
                place_result = await self.place_block('furnace', pos.x, pos.y, pos.z)
                await asyncio.sleep(1)
                if place_result["success"]:
                    furnace_block = await self.get_nearest_block('furnace', 32)
                    placed_furnace = True
                else:
                    result["message"] = "かまどの設置に失敗しました"
                    result["error"] = "furnace_placement_failed"
                    self.bot.chat(result["message"])
                    return result
            else:
                result["message"] = f"近くにかまどがなく、インベントリにもかまどがありません"
                result["error"] = "no_furnace"
                self.bot.chat(result["message"])
                return result
                
        # かまどまで移動
        if self.bot.entity.position.distanceTo(furnace_block.position) > 4:
            await self.move_to_position(
                furnace_block.position.x, 
                furnace_block.position.y, 
                furnace_block.position.z, 
                4
            )
            
        # かまどを開く
        try:
            # かまどを見る
            self.bot.lookAt(furnace_block.position)
            
            # かまどを開く
            furnace = self.bot.openFurnace(furnace_block)
            
            # 既に精錬中のアイテムがあるか確認
            input_item = furnace.inputItem()
            if input_item and input_item.type and input_item.count > 0:
                if self._get_item_name(input_item.type) != item_name:
                    result["message"] = f"かまどは既に{self._get_item_name(input_item.type)}を精錬中です"
                    result["error"] = "already_smelting"
                    furnace.close()
                    
                    # 設置したかまどを回収
                    if placed_furnace:
                        await self.collect_block('furnace', 1)
                        
                    self.bot.chat(result["message"])
                    return result
                    
            # 精錬するアイテムを持っているか確認
            inv_counts = await self.get_inventory_counts()
            if not inv_counts.get(item_name, 0) or inv_counts.get(item_name, 0) < num:
                result["message"] = f"精錬するための{item_name}が足りません"
                result["error"] = "insufficient_items"
                furnace.close()
                
                # 設置したかまどを回収
                if placed_furnace:
                    await self.collect_block('furnace', 1)
                    
                self.bot.chat(result["message"])
                return result
                
            # 燃料を確認・投入
            if not furnace.fuelItem() or furnace.fuelItem().count <= 0:
                fuel = self._get_smelting_fuel()
                if not fuel:
                    result["message"] = f"{item_name}を精錬するための燃料（石炭、木炭、木材など）がありません"
                    result["error"] = "no_fuel"
                    furnace.close()
                    
                    # 設置したかまどを回収
                    if placed_furnace:
                        await self.collect_block('furnace', 1)
                        
                    self.bot.chat(result["message"])
                    print(result)
                    return result
                    
                # 燃料を投入
                furnace.putFuel(fuel.type, None, fuel.count)
                self.bot.chat(f"かまどに{fuel.count}個の{fuel.name}を燃料として投入しました")
                print(f"かまどに{fuel.count}個の{fuel.name}を燃料として投入しました")
                
            # 精錬するアイテムをかまどに入れる
            item_id = self._get_item_id(item_name)
            furnace.putInput(item_id, None, num)
            
            # 精錬が完了するまで待機して結果を収集
            total_smelted = 0
            collected_last = True
            smelted_item = None
            
            # 少し待機して精錬が始まるのを待つ
            await asyncio.sleep(0.2)
            
            while total_smelted < num:
                # 10秒ごとに確認
                await asyncio.sleep(10)
                
                # 結果を確認
                collected = False
                if furnace.outputItem():
                    smelted_item = furnace.takeOutput()
                    if smelted_item:
                        total_smelted += smelted_item.count
                        collected = True
                        
                # 何も取得できなかった場合
                if not collected and not collected_last:
                    break  # 前回も今回も何も取得できなかった場合は終了
                    
                collected_last = collected
                
            # かまどを閉じる
            furnace.close()
            
            # 設置したかまどを回収
            if placed_furnace:
                await self.collect_block('furnace', 1)
                
            # 結果を設定
            if total_smelted == 0:
                result["message"] = f"{item_name}の精錬に失敗しました"
                result["error"] = "smelting_failed"
                self.bot.chat(result["message"])
                print(result)
                return result
                
            if total_smelted < num:
                result["message"] = f"{num}個中{total_smelted}個の{item_name}を精錬しました"
                result["success"] = True
                result["smelted"] = total_smelted
                
                if smelted_item:
                    result["smelted_item_name"] = self._get_item_name(smelted_item.type)
                    
                self.bot.chat(result["message"])
                print(result)
                return result
                
            result["message"] = f"{item_name}を{total_smelted}個精錬しました"
            if smelted_item:
                result["smelted_item_name"] = self._get_item_name(smelted_item.type)
                result["message"] = f"{item_name}を精錬し、{total_smelted}個の{self._get_item_name(smelted_item.type)}を取得しました"
                
            result["success"] = True
            result["smelted"] = total_smelted
            self.bot.chat(result["message"])
            print(result)
            return result
            
        except Exception as e:
            result["message"] = f"かまど操作中にエラーが発生しました: {str(e)}"
            result["error"] = "furnace_error"
            
            import traceback
            traceback.print_exc()
            print(result)
            self.bot.chat(result["message"])
            
            # 設置したかまどを回収
            if placed_furnace:
                try:
                    await self.collect_block('furnace', 1)
                except:
                    pass
                    
            return result
    
    async def clear_nearest_furnace(self):
        """
        最も近いかまどを見つけ、中のアイテムをすべて取り出します。
        
        Returns:
            dict: 結果を含む辞書
                - success (bool): 操作に成功した場合はTrue、失敗した場合はFalse
                - message (str): 結果メッセージ
                - items (list): 回収したアイテムのリスト
        """
        self.bot.chat("近くのかまどの中のアイテムを取り出します")
        print("近くのかまどの中のアイテムを取り出します")
        result = {
            "success": False,
            "message": "",
            "items": []
        }
        
        try:
            # 最も近いかまどを見つける
            furnace_block = await self.get_nearest_block('furnace', 32)
            if not furnace_block:
                result["message"] = "近くにかまどが見つかりません"
                result["error"] = "no_furnace"
                return result
                
            # かまどまでの距離を確認
            if self.bot.entity.position.distanceTo(furnace_block.position) > 4:
                move_result = await self.move_to_position(
                    furnace_block.position.x,
                    furnace_block.position.y,
                    furnace_block.position.z,
                    2
                )
                if not move_result["success"]:
                    result["message"] = "かまどに到達できませんでした"
                    result["error"] = "cannot_reach"
                    return result
            
            # かまどを開く
            furnace = self.bot.openFurnace(furnace_block)
            
            # アイテムを取り出す
            smelted_item = None
            input_item = None 
            fuel_item = None
            
            if furnace.outputItem():
                smelted_item = furnace.takeOutput()
                if smelted_item:
                    result["items"].append({
                        "name": self._get_item_name(smelted_item.type),
                        "count": smelted_item.count
                    })
                    
            if furnace.inputItem():
                input_item = furnace.takeInput()
                if input_item:
                    result["items"].append({
                        "name": self._get_item_name(input_item.type),
                        "count": input_item.count
                    })
                    
            if furnace.fuelItem():
                fuel_item = furnace.takeFuel()
                if fuel_item:
                    result["items"].append({
                        "name": self._get_item_name(fuel_item.type),
                        "count": fuel_item.count
                    })
                    
            # かまどを閉じる
            furnace.close()
            
            # アイテムを名前でグループ化して合計を計算
            item_totals = {}
            
            for item in result["items"]:
                name = item["name"]
                count = item["count"]
                item_totals[name] = item_totals.get(name, 0) + count
                
            # 合計を新しいitemsリストに変換
            grouped_items = []
            for name, count in item_totals.items():
                grouped_items.append({
                    "name": name,
                    "count": count
                })
                
            # 結果を更新
            result["items"] = grouped_items
            
            # 結果テキストを生成
            text = ""
            for item in grouped_items:
                text += f"{item['count']}個の{item['name']}、"
            text = text.rstrip("、")
            if text=="" :
                result["message"] = "かまどから回収を行いましたが、かまどは空でした"
            else:
                result["message"] = f"かまどから{text}を回収しました"
            result["success"] = True
            
            return result
            
        except Exception as e:
            result["message"] = f"かまどのクリア中にエラーが発生しました: {str(e)}"
            import traceback
            traceback.print_exc()
            return result
        
    async def attack_nearest(self, mob_type, kill=True,pickup_item=True):
        """
        指定したタイプのモブを攻撃します。
        
        Args:
            mob_type: 攻撃するモブのタイプ
            kill: モブが死ぬまで攻撃し続けるかどうか（デフォルトはTrue）
            pickup_item: モブが死んだ時にドロップアイテムを拾うかどうか（デフォルトはTrue）
        Returns:
            dict: 結果を含む辞書
                - success (bool): 攻撃に成功した場合はTrue、失敗した場合はFalse 
                - message (str): 結果メッセージ
                - mob_type (str): 攻撃したモブのタイプ
        """
        self.bot.chat(f"{mob_type}を攻撃します。")
        print(f"{mob_type}を攻撃します。")
        result = {
            "success": False,
            "message": "",
            "mob_type": mob_type
        }
        
        # 近くのエンティティを取得
        nearby_entities = self._get_nearby_entities(24)
        # 指定されたmob_typeと一致するエンティティを検索
        mob = None
        for entity in nearby_entities:
            if hasattr(entity, 'name') and entity.name == mob_type:
                mob = entity
                break
        
        if mob and hasattr(mob, 'position') and mob.position:
            attack_result = await self.attack_entity(mob, kill,pickup_item)
            result.update(attack_result)
            result["mob_type"] = mob_type
            return result
        
        result["message"] = f'{mob_type}が見つかりませんでした。'
        self.bot.chat(result["message"])
        print(result)
        return result

    async def attack_entity(self, entity, kill=True,pickup_item=True):
        """
        指定したエンティティを攻撃します。
        
        Args:
            entity: 攻撃するエンティティ
            kill: エンティティが死ぬまで攻撃し続けるかどうか（デフォルトはTrue）
            pickup_item: エンティティが死んだ時にドロップアイテムを拾うかどうか（デフォルトはTrue）
        Returns:
            dict: 結果を含む辞書
                - success (bool): 攻撃に成功した場合はTrue、失敗した場合はFalse
                - message (str): 結果メッセージ
                - entity_name (str): 攻撃したエンティティの名前
                - killed (bool, optional): エンティティを倒したかどうか
        """
        self.bot.chat(f"{entity.name}を攻撃します。")
        print(f"{entity.name}を攻撃します。")
        result = {
            "success": False,
            "message": "",
            "entity_name": entity.name if hasattr(entity, 'name') else "不明なエンティティ"
        }
        
        # エンティティの存在確認
        if not entity or not hasattr(entity, 'position') or not entity.position:
            result["message"] = "攻撃対象のエンティティが無効です"
            result["error"] = "invalid_entity"
            self.bot.chat(result["message"])
            print(result)
            return result
        
        # 最高攻撃力の武器を装備
        wepon = await self._equip_highest_attack()
        if not wepon:
            result["message"] = "武器になるものがインベントリにありません。"
            result["error"] = "no_weapon"
            self.bot.chat(result["message"])
            print(result)
            return result
        
        # エンティティの位置を保存
        position = entity.position
        
        if not kill:
            # エンティティが遠すぎる場合は近づく
            try:
                if self.bot.entity.position.distanceTo(position) > 5:
                    await self.move_to_position(position.x, position.y, position.z)
            except Exception as e:
                result["message"] = f"エンティティへの移動中にエラーが発生しました: {str(e)}"
                result["error"] = "movement_error"
                self.bot.chat(result["message"])
                print(result)
                return result
                
            # 一度だけ攻撃
            try:
                self.bot.attack(entity)
                result["success"] = True
                result["message"] = f"{entity.name}を1度攻撃しました"
                result["killed"] = False
                self.bot.chat(result["message"])
                print(result)
                return result
            except Exception as e:
                result["message"] = f"攻撃中にエラーが発生しました: {str(e)}"
                result["error"] = "attack_error"
                self.bot.chat(result["message"])
                print(result)
                return result
        else:
            # PVPモジュールを使用
            self.bot.pvp.attack(entity)
            
            # エンティティが死ぬまで待機
            while self._is_entity_nearby(entity, 24):
                await asyncio.sleep(1)
                if hasattr(self.bot, 'interrupt_code') and self.bot.interrupt_code:
                    self.bot.pvp.stop()
                    result["message"] = "攻撃が中断されました"
                    self.bot.chat(result["message"])
                    print(result)
                    return result
            self.bot.pvp.stop()
            
            result["success"] = True
            result["message"] = f"{entity.name}を倒しました"
            result["killed"] = True
            self.bot.chat(result["message"])
            print(result)
            # 周囲のアイテムを拾う
            if pickup_item:
                pickup_result = await self.pickup_nearby_items()
                result["message"] += " "+ pickup_result["message"]
                self.bot.chat(result["message"])
                print(result)
            return result

    async def defend_self(self, range=9):
        """
        周囲の敵対的なモブから自身を守ります。
        敵対的なモブがいなくなるまで攻撃し続けます。
        もし武器を装備していない場合は、敵から逃げます。
        Args:
            range: モブを探す範囲。デフォルトは9
            
        Returns:
            dict: 結果を含む辞書
                - success (bool): 防衛に成功した場合はTrue、敵がいない場合はFalse
                - message (str): 結果メッセージ
                - enemies_killed (int): 倒した敵の数
        """
        result = {
            "success": False,
            "message": "",
            "enemies_killed": 0
        }
        
        attacked = False
        enemies_killed = 0
        wepon = await self._equip_highest_attack()
        enemy = self._get_nearest_hostile_entity(range)
        if not wepon:
            self.bot.chat("武器になるものがインベントリにありません。敵から逃げます。")
            result["message"] = await self.avoid_enemies()
            result["error"] = "no_weapon"
            self.bot.chat(result["message"])
            print(result)
            return result
        while enemy:
            # 敵との距離に応じた行動
            enemy_distance = self.bot.entity.position.distanceTo(enemy.position)
            
            # クリーパーとファントム以外の敵が遠い場合は接近
            if enemy_distance >= 4 and enemy.name != 'creeper' and enemy.name != 'phantom':
                try:
                    self.bot.pathfinder.setMovements(self.pathfinder.Movements(self.bot))
                    await self.bot.pathfinder.goto(self.pathfinder.goals.GoalFollow(enemy, 3.5), True)
                except Exception:
                    # エンティティが死んでいる場合などはエラーを無視
                    pass
                    
            # 敵が近すぎる場合は距離を取る
            if enemy_distance <= 2:
                try:
                    self.bot.pathfinder.setMovements(self.pathfinder.Movements(self.bot))
                    inverted_goal = self.pathfinder.goals.GoalInvert(self.pathfinder.goals.GoalFollow(enemy, 2))
                    await self.bot.pathfinder.goto(inverted_goal, True)
                except Exception:
                    # エンティティが死んでいる場合などはエラーを無視
                    pass
            
            # 攻撃開始
            has_pvp = hasattr(self.bot, 'pvp') and self.bot.pvp is not None
            
            self.bot.pvp.attack(enemy)
                
            attacked = True
            
            # 少し待機
            await asyncio.sleep(0.5)
            
            # 次の敵を探す
            previous_enemy = enemy
            enemy = self._get_nearest_hostile_entity(range)
            
            # 前の敵がいなくなった場合はカウント
            if enemy != previous_enemy and not self._is_entity_nearby(previous_enemy, range):
                enemies_killed += 1
            
            if hasattr(self.bot, 'interrupt_code') and self.bot.interrupt_code:
                if has_pvp:
                    self.bot.pvp.stop()
                result["message"] = "防衛が中断されました"
                self.bot.chat(result["message"])
                print(result)
                return result
        
        # PVP攻撃を停止
        if hasattr(self.bot, 'pvp') and self.bot.pvp is not None:
            self.bot.pvp.stop()
        
        if attacked:
            result["success"] = True
            result["message"] = f"自己防衛に成功しました。{enemies_killed}体の敵を倒しました。"
            result["enemies_killed"] = enemies_killed
        else:
            result["message"] = "近くに敵対的なモブがいません。"
        
        self.bot.chat(result["message"])
        print(result)
        return result
        
    async def pickup_nearby_items(self):
        """
        周囲のドロップアイテムを拾います。
        
        Returns:
            dict: 結果を含む辞書
                - success (bool): アイテムを拾った場合はTrue
                - message (str): 結果メッセージ
                - picked_up (int): 拾ったアイテムの数
        """
        result = {
            "success": False,
            "message": ""
        }
        
        distance = 8
        
        # 最も近いアイテムを取得する関数
        def get_nearest_item():
            nearest_item = None
            min_distance = float('inf')
            
            # bot.entities はエンティティの辞書やリストと仮定
            for entity_id in self.bot.entities:
                entity = self.bot.entities[entity_id]
                if hasattr(entity, 'name') and entity.name == 'item':
                    # 距離計算
                    dx = self.bot.entity.position.x - entity.position.x
                    dy = self.bot.entity.position.y - entity.position.y
                    dz = self.bot.entity.position.z - entity.position.z
                    current_distance = (dx*dx + dy*dy + dz*dz) ** 0.5
                    
                    if current_distance < distance and current_distance < min_distance:
                        min_distance = current_distance
                        nearest_item = entity
            return nearest_item

        # 最も近いアイテムを取得
        nearest_item = get_nearest_item()
        item_list = []
        if nearest_item:
            while nearest_item:
                # アイテムに近づく
                if hasattr(self.bot.pathfinder, 'setMovements') and hasattr(self.pathfinder, 'Movements') and hasattr(self.pathfinder.goals, 'GoalFollow'):
                    await self.move_to_position(nearest_item.position.x, nearest_item.position.y, nearest_item.position.z, 0.8)
                # アイテムIDを取得
                item_id = self._get_item_id_from_entity(nearest_item)
                item_name = self._get_item_name(item_id)
                item_list.append(item_name)
                # 少し待機してアイテムが拾われるのを待つ
                await asyncio.sleep(0.2)
                

                # 前のアイテムを保存
                prev_item = nearest_item
                
                # 新しい最寄りのアイテムを取得
                nearest_item = get_nearest_item()
                # 同じアイテムが最も近い場合は終了（拾えなかった）
                if prev_item == nearest_item:
                    break
                    
            result["success"] = True
            item_str = ", ".join(item_list)
            result["message"] = f"{item_str}を拾いました。"
            self.bot.chat(result["message"])
            print(result)
            return result
        else:
            result["message"] = "ドロップアイテムはありません。"
            self.bot.chat(result["message"])
            print(result)
            return result
        
    async def break_block_at(self, x, y, z):
        """
        指定された座標のブロックを破壊します。現在装備しているアイテムを使用します。
        
        Args:
            x (float): 破壊するブロックのX座標
            y (float): 破壊するブロックのY座標
            z (float): 破壊するブロックのZ座標
            
        Returns:
            dict: 結果を含む辞書
                - success (bool): 破壊に成功した場合はTrue、失敗した場合はFalse
                - message (str): 結果メッセージ
                - position (dict): 破壊を試みた位置 {x, y, z}
                - block_name (str, optional): 破壊したブロックの名前
                - error (str, optional): エラーがある場合のエラーコード
        """
        self.bot.chat(f"{x}, {y}, {z}のブロックを破壊します。")
        print(f"{x}, {y}, {z}のブロックを破壊します。")
        result = {
            "success": False,
            "message": "",
            "position": {"x": x, "y": y, "z": z}
        }
        
        # 座標の検証
        if x is None or y is None or z is None:
            result["message"] = "破壊するブロックの座標が無効です"
            result["error"] = "invalid_coordinates"
            self.bot.chat(result["message"])
            print(result)
            return result
            
        # Vec3オブジェクトを作成
        Vec3 = require('vec3')
        block_pos = Vec3(x, y, z)
        
        # ブロックを取得
        block = self.bot.blockAt(block_pos)
        if not block:
            result["message"] = f"座標({x}, {y}, {z})にブロックが見つかりません"
            result["error"] = "no_block_found"
            self.bot.chat(result["message"])
            print(result)
            return result
            
        result["block_name"] = block.name
        
        # 空気、水、溶岩の場合はスキップ
        if block.name in ['air', 'water', 'lava']:
            result["message"] = f"座標({x}, {y}, {z})は{block.name}なので破壊をスキップします"
            self.bot.chat(result["message"])
            print(result)
            return result
            
        # ブロックまでの距離を確認
        if self.bot.entity.position.distanceTo(block.position) > 4.5:
            try:
                # パスファインダーの設定
                if hasattr(self.pathfinder, 'Movements') and hasattr(self.pathfinder.goals, 'GoalNear'):
                    await self.move_to_position(x, y, z, 4,canPlaceOn=False,allow1by1towers=False)
            except Exception as e:
                result["message"] = f"ブロックへの移動中にエラーが発生しました: {str(e)}"
                result["error"] = "movement_error"
                self.bot.chat(result["message"])
                print(result)
                return result

        # クリエイティブモードでない場合は適切なツールを装備
        if self.bot.game.gameMode != 'creative':
            try:
                # 適切なツールを装備
                await self.bot.tool.equipForBlock(block)
                
                # 適切なツールを持っているか確認
                item_id = None
                if self.bot.heldItem:
                    item_id = self.bot.heldItem.type
                            
                # ブロックを採掘できるか確認
                if hasattr(block, 'canHarvest') and not block.canHarvest(item_id):
                    result["message"] = f"{block.name}を採掘するための適切なツールを持っていません"
                    result["error"] = "no_suitable_tool"
                    self.bot.chat(result["message"])
                    print(result)
                    return result
            except Exception as e:
                result["message"] = f"ツール装備中にエラーが発生しました: {str(e)}"
                result["error"] = "tool_equip_error"
                self.bot.chat(result["message"])
                print(result)
                return result
                
        # ブロックを破壊
        try:
            await self.bot.dig(block, True)  # 第2引数をTrueにすることで採掘が完了するまで待機
            result["message"] = f"{block.name}を座標({x:.1f}, {y:.1f}, {z:.1f})で破壊しました"
            result["success"] = True
            self.bot.chat(result["message"])
            print(result)
            return result
        except Exception as e:
            result["message"] = f"ブロック破壊中にエラーが発生しました: {str(e)}"
            result["error"] = "dig_error"
            self.bot.chat(result["message"])
            print(result)
            return result
        
    async def use_door(self, door_pos=None):
        """
        指定された位置にあるドア・フェンスゲートを使用します。位置が指定されていない場合、最も近いドア・フェンスゲートを使用します。
        なお、ドアにインタラクトしても開かないiron_door,iron_trapdoorは使用できません。
        
        Args:
            door_pos (Vec3, optional): 使用するドアの位置。Noneの場合は最も近いドアを使用します。
            
        Returns:
            dict: 結果を含む辞書
                - success (bool): ドアの使用に成功した場合はTrue、失敗した場合はFalse
                - message (str): 結果メッセージ
                - door_position (dict, optional): 使用したドアの位置 {x, y, z}（成功時のみ）
        """
        self.bot.chat(f"{door_pos}のドアを使用します。")
        print(f"{door_pos}のドアを使用します。")
        result = {
            "success": False,
            "message": ""
        }
        
        try:
            Vec3 = require('vec3')
            
            # ドアの位置が指定されていない場合、最も近いドアを探す
            if not door_pos:
                door_types = [
                    'oak_door', 'spruce_door', 'birch_door', 'jungle_door', 
                    'acacia_door', 'dark_oak_door', 'mangrove_door', 
                    'crimson_door', 'warped_door',

                    'oak_fence_gate', 'spruce_fence_gate', 'birch_fence_gate', 'jungle_fence_gate',
                    'acacia_fence_gate', 'dark_oak_fence_gate', 'mangrove_fence_gate',
                    'crimson_fence_gate', 'warped_fence_gate'
                ]
                # トラップドアはハシゴ対応必要なため未実装
                trapdoor_types = [
                    'oak_trapdoor', 'spruce_trapdoor', 'birch_trapdoor', 'jungle_trapdoor',
                    'acacia_trapdoor', 'dark_oak_trapdoor', 'mangrove_trapdoor'
                ]
                
                for door_type in door_types:
                    door_block = await self.get_nearest_block(door_type, 16)
                    if door_block:
                        door_pos = door_block.position
                        break
            else:
                # 既存の座標をVec3オブジェクトに変換
                door_pos = Vec3(door_pos.x, door_pos.y, door_pos.z)
                
            # ドアが見つからない場合
            if not door_pos:
                result["message"] = "使用できるドアが見つかりませんでした。"
                self.bot.chat(result["message"])
                print(result)
                return result
                
            # 結果にドアの位置を記録
            result["door_position"] = {
                "x": door_pos.x,
                "y": door_pos.y,
                "z": door_pos.z
            }
            
            # ドアに近づく
            await self.move_to_position(door_pos.x, door_pos.y, door_pos.z, 1,canDig=False)
                    
            # ドアブロックを取得
            door_block = self.bot.blockAt(door_pos)
            
            # ドアを見る
            self.bot.lookAt(door_pos)
            
            # ドアが閉まっている場合は開ける
            if not door_block._properties.open:
                self.bot.activateBlock(door_block)
                
            # 前進
            self.bot.setControlState("forward", True)
            await asyncio.sleep(0.6)
            self.bot.setControlState("forward", False)
            
            # ドアを閉じる
            self.bot.activateBlock(door_block)
            
            result["success"] = True
            result["message"] = f"座標({door_pos.x}, {door_pos.y}, {door_pos.z})のドアを通過し、座標({self.bot.entity.position.x:.1f}, {self.bot.entity.position.y:.1f}, {self.bot.entity.position.z:.1f})に移動しました。"
            self.bot.chat(result["message"])
            print(result)
            return result
            
        except Exception as e:
            result["message"] = f"ドアの使用中に予期せぬエラーが発生しました: {str(e)}"
            self.bot.chat(result["message"])
            print(result)
            import traceback
            traceback.print_exc()
            return result        
        
    async def till_and_sow(self, x, y, z, seed_type=None):
        """
        指定された座標の地面を耕し、指定された種を植えます。
        
        Args:
            x (float): 耕す地点のX座標
            y (float): 耕す地点のY座標
            z (float): 耕す地点のZ座標
            seed_type (str, optional): 植える種の種類。指定しない場合は耕すだけで種は植えません。
            
        Returns:
            dict: 結果を含む辞書
                - success (bool): 地面を耕すことに成功した場合はTrue、失敗した場合はFalse
                - message (str): 結果メッセージ
                - position (dict): 耕した位置 {x, y, z}
                - tilled (bool): 地面を耕したかどうか
                - planted (bool, optional): 種を植えたかどうか（seed_typeが指定された場合）
                - seed_type (str, optional): 植えた種の種類（seed_typeが指定された場合）
        """
        self.bot.chat(f"座標({x}, {y}, {z})の地面を耕し、{seed_type}を植えます。")
        print(f"座標({x}, {y}, {z})の地面を耕し、{seed_type}を植えます。")
        result = {
            "success": False,
            "message": "",
            "position": {"x": x, "y": y, "z": z},
            "tilled": False
        }
        
        try:
            Vec3 = require('vec3')
            
            # 座標を整数に丸める
            x = round(x)
            y = round(y)
            z = round(z)
            result["position"] = {"x": x, "y": y, "z": z}
            
            # 対象のブロックを取得
            block = self.bot.blockAt(Vec3(x, y, z))
            
            # 対象のブロックが耕せるかチェック
            if block.name not in ['grass_block', 'dirt', 'farmland']:
                result["message"] = f"{block.name}は耕せません。土または草ブロックである必要があります。"
                self.bot.chat(result["message"])
                print(result)
                return result
                
            # 上のブロックがあるかチェック
            above = self.bot.blockAt(Vec3(x, y+1, z))
            if above.name != 'air':
                result["message"] = f"ブロックの上に{above.name}があるため耕せません。"
                self.bot.chat(result["message"])
                print(result)
                return result
            
            # クワを探して装備
            hoe = None
            for item in self.bot.inventory.items():
                if 'hoe' in item.name:
                    hoe = item
                    break
            if not hoe:
                result["message"] = "クワを持っていないため耕せません。"
                self.bot.chat(result["message"])
                print(result)
                return result
            else:
                self.bot.equip(hoe, 'hand')
                    
            # ブロックまでの距離が遠い場合は近づく
            if self.bot.entity.position.distanceTo(block.position) > 4.5:
                pos = block.position
                move_result = await self.move_to_position(pos.x, pos.y, pos.z, 4)
                if not move_result["success"]:
                    result["message"] = move_result["message"]
                    self.bot.chat(result["message"])
                    print(result)
                    return result
            
            # 既に農地でない場合は耕す
            if block.name != 'farmland':
                
                # ブロックを耕す
                self.bot.activateBlock(block)
                
                result["tilled"] = True
                self.bot.chat(f"BOTは、座標({x}, {y}, {z})を耕しました。")
                print(result)
            else:
                result["tilled"] = True
                
            # 種を植える
            if seed_type:
                # 「seed」で終わるが「seeds」で終わらない場合、「s」を追加
                if seed_type.endswith('seed') and not seed_type.endswith('seeds'):
                    seed_type += 's'  # 一般的な間違いを修正
                    
                # 種を探す
                seeds = None
                for item in self.bot.inventory.items():
                    if item.name == seed_type:
                        seeds = item
                        break
                if not seeds:
                    result["message"] = f"{seed_type}を持っていないため植えられません。" + \
                                       (f"座標({x}, {y}, {z})は耕しました。" if result["tilled"] else "")
                    self.bot.chat(result["message"])
                    print(result)
                    
                    # 耕せたならある程度は成功
                    if result["tilled"]:
                        result["success"] = True
                    return result
                
                # 種を装備
                self.bot.equip(seeds, 'hand')
                
                # 種を植える（農地の上に設置）
                # 底面に対して設置するので、Vec3(0, -1, 0)を使用
                self.bot.placeBlock(block, Vec3(0, -1, 0))
                
                result["planted"] = True
                result["seed_type"] = seed_type
                self.bot.chat(f"座標({x}, {y}, {z})に{seed_type}を植えました。")
                print(f"座標({x}, {y}, {z})に{seed_type}を植えました。")
            
            result["success"] = True
            
            if seed_type and result["planted"]:
                result["message"] = f"座標({x}, {y}, {z})を耕し、{seed_type}を植えました。"
            else:
                result["message"] = f"座標({x}, {y}, {z})を耕しました。"
            print(result)
            self.bot.chat(result["message"])
            return result
            
        except Exception as e:
            already_tilled = "tilled" in result and result["tilled"]
            result["message"] = f"耕し・種まき中に予期せぬエラーが発生しました: {str(e)}" + \
                               (f"座標({x}, {y}, {z})は耕すことができました。" if already_tilled else "")
            
            # 耕すだけはできた場合は部分的に成功
            if already_tilled:
                result["success"] = True
                
            self.bot.chat(result["message"])
            print(result)
            import traceback
            traceback.print_exc()
            return result

    def get_item_crafting_recipes(self, item_name):
        """
        アイテムのクラフトレシピを取得します
        
        Args:
            item_name (str): アイテム名
            
        Returns:
            list: レシピのリスト。各レシピは[材料辞書, 結果辞書]の形式

        Example:
            >>> recipes = get_item_crafting_recipes("crafting_table")
            [[{'oak_planks': 4}, {'craftedCount': 1}], [{'spruce_planks': 4}, {'craftedCount': 1}]...]
        """
        self.bot.chat(f"{item_name}のクラフトレシピを取得します。")
        item_id = self.mcdata.itemsByName[item_name].id
        if item_id not in self.mcdata.recipes:
            return None
            
        recipes = []
        for r in self.mcdata.recipes[item_id]:
            recipe = {}
            ingredients = []
            if hasattr(r, 'ingredients') and r.ingredients:
                ingredients = r.ingredients
            elif hasattr(r, 'inShape') and r.inShape:
                ingredients = [item for sublist in r.inShape for item in sublist if item]
                
            for ingredient in ingredients:
                if not ingredient:
                    continue
                ingredient_name = self.mcdata.items[ingredient].name
                if ingredient_name not in recipe:
                    recipe[ingredient_name] = 0
                recipe[ingredient_name] += 1
                
            recipes.append([
                recipe,
                {"craftedCount": r.result.count}
            ])
            
        return recipes

    async def collect_liquid(self, liquid_type='water', max_distance=16):
        """
        指定された範囲内の水または溶岩をバケツで汲み上げます。このメソッドの実行にはbucketが必要です。

        Args:
            liquid_type (str): 汲み上げる液体の種類。'water'または'lava'を指定。デフォルトは'water'。
            max_distance (int): 探索する最大距離。デフォルトは16。
            
        Returns:
            dict: 結果を含む辞書
                - success (bool): 液体を汲み上げることに成功した場合はTrue、失敗した場合はFalse
                - message (str): 結果メッセージ
                - position (dict, optional): 汲み上げた液体の位置 {x, y, z}
                - liquid_type (str): 汲み上げた液体の種類
        """
        result = {
            "success": False,
            "message": "",
            "liquid_type": liquid_type
        }
        
        try:
            # 液体の種類を確認
            if liquid_type not in ['water', 'lava']:
                result["message"] = f"無効な液体タイプです: {liquid_type}。'water'または'lava'を指定してください。"
                self.bot.chat(result["message"])
                print(result)
                return result
            
            # バケツを探す
            bucket = None
            bucket_count = 0
            for item in self.bot.inventory.items():
                if item.name == 'bucket':
                    bucket = item
                elif item.name == f'{liquid_type}_bucket':
                    bucket_count += 1
            bucket_count += 1
            
            if not bucket:
                result["message"] = "バケツを持っていないため液体を汲み上げられません。"
                self.bot.chat(result["message"])
                print(result)
                return result
            
            # 指定された液体ブロックを探す
            block_id = self.mcdata.blocksByName[liquid_type].id
            blocks = self.bot.findBlocks({
                'matching': block_id,
                'maxDistance': max_distance,
                'count': 10
            })
            for block in blocks:
                block_info = self.bot.blockAt(block)
                if block_info.metadata == 0:
                    liquid_block = block_info
                    break
            
            if not liquid_block:
                result["message"] = f"範囲内に{liquid_type}が見つかりませんでした。"
                self.bot.chat(result["message"])
                print(result)
                return result
            
            # ブロックまでの距離が遠い場合は近づく
            if self.bot.entity.position.distanceTo(liquid_block.position) > 2:
                pos = liquid_block.position
                move_result = await self.move_to_position(pos.x, pos.y, pos.z, 2)
                if not move_result["success"]:
                    result["message"] = move_result["message"]
                    self.bot.chat(result["message"])
                    print(result)
                    return result
            
            # バケツを装備
            self.bot.equip(bucket, 'hand')

            # botが液体ブロックを見る
            self.bot.lookAt(liquid_block.position)
            
            # バケツを使って液体を汲み上げる
            self.bot.activateBlock(liquid_block)
            self.bot.activateItem()
            
            # 少し待機して操作が完了するのを待つ
            await asyncio.sleep(1)

            # バケツを非アクティブ化
            self.bot.deactivateItem()

            # 結果を設定
            result["success"] = True
            result["position"] = {
                "x": liquid_block.position.x,
                "y": liquid_block.position.y,
                "z": liquid_block.position.z
            }
            
            # 正しい液体を汲み上げたかチェック（インベントリを確認）
            has_filled_bucket = False
            
            for item in self.bot.inventory.items():
                
                if item.name == f"{liquid_type}_bucket":
                    bucket_count -= 1
                    if bucket_count == 0:
                        has_filled_bucket = True
                        break
            
            if has_filled_bucket:
                result["message"] = f"座標({liquid_block.position.x}, {liquid_block.position.y}, {liquid_block.position.z})の{liquid_type}を{bucket.name}で汲み上げました。"
            else:
                result["success"] = False
                result["message"] = f"{liquid_type}の汲み上げに失敗しました。"
            
            self.bot.chat(result["message"])
            print(result)
            return result
            
        except Exception as e:
            result["message"] = f"液体の汲み上げ中に予期せぬエラーが発生しました: {str(e)}"
            self.bot.chat(result["message"])
            print(result)
            import traceback
            traceback.print_exc()
            return result

    async def place_liquid(self, x, y, z, liquid_type='water'):
        """
        指定された座標に液体（水または溶岩）をバケツから配置します。このメソッドの実行にはater_bucketまたはlava_bucketが必要です。
        
        Args:
            x (float): 液体を配置するX座標
            y (float): 液体を配置するY座標
            z (float): 液体を配置するZ座標
            liquid_type (str): 配置する液体の種類。'water'または'lava'を指定。デフォルトは'water'。
            
        Returns:
            dict: 結果を含む辞書
                - success (bool): 液体の配置に成功した場合はTrue、失敗した場合はFalse
                - message (str): 結果メッセージ
                - position (dict): 液体を配置した位置 {x, y, z}
                - liquid_type (str): 配置した液体の種類
        """
        self.bot.chat(f"{liquid_type}を座標({x}, {y}, {z})に配置します。")
        print(f"{liquid_type}を座標({x}, {y}, {z})に配置します。")
        result = {
            "success": False,
            "message": "",
            "position": {"x": x, "y": y, "z": z},
            "liquid_type": liquid_type
        }
        
        try:
            # 液体の種類を確認
            if liquid_type not in ['water', 'lava']:
                result["message"] = f"無効な液体タイプです: {liquid_type}。'water'または'lava'を指定してください。"
                self.bot.chat(result["message"])
                print(result)
                return result
            
            # 座標を整数に丸める
            x = round(x)
            y = round(y)
            z = round(z)
            result["position"] = {"x": x, "y": y, "z": z}
            
            # 液体入りバケツを探す
            filled_bucket = None
            
            for item in self.bot.inventory.items():
                if item.name == f"{liquid_type}_bucket":
                    filled_bucket = item
            
            if not filled_bucket:
                result["message"] = f"{liquid_type}_bucketを持っていないため液体を配置できません。"
                self.bot.chat(result["message"])
                print(result)
                return result
            
            # 対象のブロックを取得
            Vec3 = require('vec3')
            target_position = Vec3(x, y, z)
            target_block = self.bot.blockAt(target_position)
            
            # 配置先が空気または他の配置可能なブロックかを確認
            if target_block.name != 'air' and target_block.name != 'cave_air':
                result["message"] = f"座標({x}, {y}, {z})には既に{target_block.name}があるため液体を配置できません。"
                self.bot.chat(result["message"])
                print(result)
                return result
            
            # ブロックまでの距離が遠い場合は近づく
            if self.bot.entity.position.distanceTo(target_position) > 2:
                move_result = await self.move_to_position(x, y, z, 2)
                if not move_result["success"]:
                    result["message"] = move_result["message"]
                    self.bot.chat(result["message"])
                    print(result)
                    return result
            
            # 液体入りバケツを装備
            self.bot.equip(filled_bucket, 'hand')
            
            # 対象ブロックを見る
            self.bot.lookAt(target_position)
            
            # バケツを使って液体を配置
            self.bot.activateBlock(target_block)
            self.bot.activateItem()
            
            # 少し待機して操作が完了するのを待つ
            await asyncio.sleep(1)
            
            # バケツを非アクティブ化
            self.bot.deactivateItem()
            
            # 配置されたブロックを確認
            new_block = self.bot.blockAt(target_position)
            is_correct_liquid = new_block and new_block.name == liquid_type
            
            if is_correct_liquid:
                result["success"] = True
                result["message"] = f"座標({x}, {y}, {z})に{liquid_type}を{filled_bucket.name}から配置しました。"
            else:
                result["success"] = False
                result["message"] = f"座標({x}, {y}, {z})への{liquid_type}の配置に失敗しました。"
            
            self.bot.chat(result["message"])
            print(result)
            return result
            
        except Exception as e:
            result["message"] = f"液体の配置中に予期せぬエラーが発生しました: {str(e)}"
            self.bot.chat(result["message"])
            print(result)
            import traceback
            traceback.print_exc()
            return result

    def _make_item(self, item_name, count=1):
        """
        指定された名前とカウントでアイテムオブジェクトを作成します。
        クリエイティブモードでのアイテム追加に使用します。
        注意:クリエイティブモードのみで動作します
        
        Args:
            item_name (str): アイテム名
            count (int): アイテム数
            
        Returns:
            Object: アイテムオブジェクト
        """
        try:
            if hasattr(self.mcdata, 'makeItem'):
                return self.mcdata.makeItem(item_name, count)
            elif hasattr(self.mcdata, 'itemsByName') and item_name in self.mcdata.itemsByName:
                item_id = self.mcdata.itemsByName[item_name].id
                return {
                    'type': item_id,
                    'count': count,
                    'metadata': 0
                }
        except Exception as e:
            print(f"アイテム作成エラー: {e}")
            
        # 基本的なオブジェクトを返す
        return {
            'name': item_name,
            'count': count
        }
    
            
    async def _equip_highest_attack(self):
        """
        最も攻撃力の高い武器を装備します。
        
        Returns:
            bool: 武器を装備した場合はTrue、適切な武器がない場合はFalse
        """
        # 剣と斧を探す（ただしツルハシは除く）
        weapons = []
        for item in self.bot.inventory.items():
            if 'sword' in item.name or ('axe' in item.name and 'pickaxe' not in item.name):
                weapons.append(item)
                
        # 武器がない場合はツルハシやシャベルを探す
        if not weapons:
            for item in self.bot.inventory.items():
                if 'pickaxe' in item.name or 'shovel' in item.name:
                    weapons.append(item)
                    
        # 武器がない場合は終了
        if not weapons:
            return False
            
        # 攻撃力でソート
        try:
            # attackDamageプロパティが利用できる場合
            weapons.sort(key=lambda item: getattr(item, 'attackDamage', 0), reverse=True)
        except:
            # 攻撃力の情報がない場合は材質と種類でソート
            material_order = ['netherite', 'diamond', 'iron', 'stone', 'golden', 'wooden']
            weapon_type_order = ['sword', 'axe', 'pickaxe', 'shovel']
            
            def get_attack_score(item):
                # 材質スコア
                material_score = 0
                for i, material in enumerate(material_order):
                    if material in item.name:
                        material_score = len(material_order) - i
                        break
                
                # 武器タイプスコア
                type_score = 0
                for i, weapon_type in enumerate(weapon_type_order):
                    if weapon_type in item.name:
                        type_score = len(weapon_type_order) - i
                        break
                        
                return material_score * 10 + type_score
                
            weapons.sort(key=get_attack_score, reverse=True)
            
        # 最高の武器を装備
        best_weapon = weapons[0]
        self.bot.equip(best_weapon, 'hand')
        return True
        
    def _get_nearby_entity_of_type(self, entity_type, max_distance=24):
        """
        指定された種類の最も近いエンティティを取得します。
        
        Args:
            entity_type (str): エンティティの種類
            max_distance (int): 検索する最大距離
            
        Returns:
            Entity: 最も近いエンティティ、見つからない場合はNone
        """
        try:
            entities = self._get_nearby_entities(max_distance)
            for entity in entities:
                if hasattr(entity, 'name') and entity.name == entity_type:
                    return entity
        except Exception as e:
            print(f"エンティティ検索エラー: {e}")
            
        return None
        
    def _get_nearest_hostile_entity(self, max_distance=24):
        """
        指定した距離以内で最も近い敵対的なエンティティを取得します。
        
        Args:
            max_distance (int): 検索する最大距離。デフォルトは24
            
        Returns:
            Entity or None: 最も近い敵対的なエンティティ。見つからない場合はNone
        """
        def calculate_distance(pos1, pos2):
            """2点間のユークリッド距離を計算"""
            return ((pos1.x - pos2.x) ** 2 + 
                   (pos1.y - pos2.y) ** 2 + 
                   (pos1.z - pos2.z) ** 2) ** 0.5

        # 敵対的なエンティティをフィルタリング
        hostile_entities = [
            entity for entity in self._get_nearby_entities(max_distance)
            if self._is_hostile(entity)
        ]
        
        if not hostile_entities:
            return None
            
        # 距離でソート
        hostile_entities.sort(
            key=lambda e: calculate_distance(self.bot.entity.position, e.position)
        )
        
        return hostile_entities[0] if hostile_entities else None
        
    def _get_nearby_entities(self, max_distance=24):
        """
        指定した距離以内にある全てのエンティティを取得し、距離順にソートして返します。
        
        Args:
            max_distance (int): 検索する最大距離。デフォルトは24
            
        Returns:
            list: 距離順にソートされた近くのエンティティのリスト
        """
        if not self.bot or not self.bot.entity or not hasattr(self.bot.entity, 'position'):
            return []
            
        def calculate_distance(pos1, pos2):
            """2点間のユークリッド距離を計算"""
            return ((pos1.x - pos2.x) ** 2 + 
                   (pos1.y - pos2.y) ** 2 + 
                   (pos1.z - pos2.z) ** 2) ** 0.5
            
        nearby_entities = []
        # JavaScriptのオブジェクトとして実装されているentitiesをキーで反復処理
        for entity_id in self.bot.entities:
            entity = self.bot.entities[entity_id]
            if not entity or not hasattr(entity, 'id'):  # エンティティがNoneの場合はスキップ
                continue
                
            if entity.id == self.bot.entity.id:  # 自分自身は除外
                continue
                
            if hasattr(entity, 'position') and entity.position:
                distance = calculate_distance(self.bot.entity.position, entity.position)
                if distance <= max_distance:
                    nearby_entities.append(entity)
                
        # 距離でソート
        nearby_entities.sort(
            key=lambda e: calculate_distance(self.bot.entity.position, e.position)
        )
        
        return nearby_entities
        
    def _is_entity_nearby(self, entity, max_distance=24):
        """
        特定のエンティティが近くにいるか確認します。
        
        Args:
            entity: 確認するエンティティ
            max_distance (int): 検索する最大距離
            
        Returns:
            bool: エンティティが近くにいる場合はTrue
        """
        # エンティティが有効かチェック
        if not entity or not hasattr(entity, 'id'):
            return False
            
        entities = self._get_nearby_entities(max_distance)
        for e in entities:
            if hasattr(e, 'id') and e.id == entity.id:
                return True
        return False
    
    def _is_hostile(self, entity):
        """
        エンティティが敵対的かどうかを判断します。
        
        Args:
            entity: 判断するエンティティ
            
        Returns:
            bool: 敵対的な場合はTrue
        """
        hostile_mobs = [
            'zombie', 'skeleton', 'creeper', 'spider', 'enderman', 
            'witch', 'slime', 'silverfish', 'cave_spider', 'ghast',
            'zombie_pigman', 'blaze', 'magma_cube', 'wither_skeleton',
            'guardian', 'elder_guardian', 'shulker', 'husk', 'stray',
            'phantom', 'drowned', 'pillager', 'ravager', 'vex',
            'evoker', 'vindicator', 'hoglin', 'zoglin', 'piglin_brute'
        ]
        
        try:
            return entity.name in hostile_mobs
        except:
            return False
        
    def _is_smeltable(self, item_name):
        """
        アイテムが精錬可能かどうかを判断します。
        
        Args:
            item_name (str): 判断するアイテム名
            
        Returns:
            bool: 精錬可能な場合はTrue
        """
        # 精錬可能なアイテムのリスト
        smeltable_items = [
            # 鉱石
            'raw_iron', 'raw_gold', 'raw_copper', 
            'iron_ore', 'gold_ore', 'copper_ore',
            'ancient_debris', 'netherite_scrap',
            # 食材
            'beef', 'chicken', 'cod', 'salmon', 'porkchop', 'potato', 'rabbit', 'mutton',
            # その他
            'sand', 'cobblestone', 'clay', 'clay_ball', 'cactus'
        ]
        
        # 「raw_」で始まるアイテムは基本的に精錬可能と判断
        if item_name.startswith('raw_'):
            return True
            
        return item_name in smeltable_items
        
    def _get_smelting_fuel(self):
        """
        インベントリから精錬に使用できる燃料を探します。
        
        Returns:
            Object: 燃料アイテムオブジェクト、見つからない場合はNone
        """
        # 燃料として使用できるアイテムを優先順に探す
        fuel_types = ['coal', 'charcoal', 'coal_block', 'lava_bucket', 'blaze_rod', 'oak_planks', 'spruce_planks', 
                     'birch_planks', 'jungle_planks', 'acacia_planks', 'dark_oak_planks', 
                     'oak_log', 'spruce_log', 'birch_log', 'jungle_log', 'acacia_log', 'dark_oak_log']
                     
        for fuel_type in fuel_types:
            for item in self.bot.inventory.items():
                if item.name == fuel_type:
                    return item
                    
        return None
        
    def _get_item_name(self, item_id):
        """
        アイテムIDから対応するアイテム名を取得します。
        
        Args:
            item_id (int): アイテムのID
            
        Returns:
            str: アイテム名。IDが見つからない場合はNone
        """
        item = self.mcdata.items[item_id]
        
        if item:
            return item.name
        return None
        
    def _get_item_id(self, item_name):
        """
        アイテム名からアイテムIDを取得します。
        
        Args:
            item_name (str): アイテム名
            
        Returns:
            int: アイテムID
        """
        try:
            if hasattr(self.mcdata, 'itemsByName') and item_name in self.mcdata.itemsByName:
                return self.mcdata.itemsByName[item_name].id
            elif hasattr(self.bot.registry, 'itemsByName') and item_name in self.bot.registry.itemsByName:
                return self.bot.registry.itemsByName[item_name].id
        except:
            pass
            
        # アイテムが見つからない場合はエラー
        return None
    
    def _get_item_id_from_entity(self, entity):
        """
        エンティティからアイテムIDを取得します。
        
        Args:
            entity: エンティティオブジェクト
            
        Returns:
            int: アイテムID
        """
        # metadata の8番目の要素（インデックス7）にitemIdが含まれている
        if entity and hasattr(entity, 'metadata'):
            metadata_item = entity.metadata[8]
            return metadata_item.itemId
        
        # 取得できない場合はNoneを返す
        return None

    async def handle_connection_error(self, timeout=30):
        """
        API通信上の問題が発生した場合に、ボットの再接続を試みます。
        APIが応答しない、タイムアウトする場合に使用します。

        Args:
            timeout (int): 再接続試行のタイムアウト時間（秒）。デフォルトは30秒。

        Returns:
            dict: 再接続の結果
                - success (bool): 再接続に成功した場合はTrue
                - message (str): 結果メッセージ
        """
        self.bot.chat("通信エラーが発生したため、サーバーへの再接続を試みます...")
        result = {
            "success": False,
            "message": ""
        }
        try:
            # discovery インスタンスの reconnect_bot メソッドを呼び出す
            # reconnect_bot は bool を返すように変更されているはず
            reconnect_success = await self.discovery.reconnect_bot(timeout=timeout)

            if reconnect_success:
                result["success"] = True
                result["message"] = "サーバーへの再接続に成功しました。"
                self.bot.chat(result["message"])
                # 再接続後、Skillsクラス内の参照を更新する必要があるかもしれない
                self.bot = self.discovery.bot
                self.mcdata = self.discovery.mcdata
                self.pathfinder = self.discovery.pathfinder
                self.movements = self.discovery.movements
                self.mineflayer = self.discovery.mineflayer
                print("Skillsクラス内の参照を更新しました。")
            else:
                result["message"] = f"サーバーへの再接続に失敗しました（タイムアウト: {timeout}秒）。サーバーの状態を確認してください。"
                # botインスタンスがNoneになっている可能性があるのでチャットは避ける
                print(result["message"])

        except Exception as e:
            result["message"] = f"再接続処理中に予期せぬエラーが発生しました: {str(e)}"
            print(f"再接続エラー: {result['message']}")
            import traceback
            traceback.print_exc()

        return result

    async def create_nether_portal(self, check_space_only=False):
        """
        黒曜石を使ってネザーゲートを設置し、火打石と打ち金で起動します。
        最小構成（10個の黒曜石、角なし）で設置します。

        Args:
            check_space_only (bool): Trueの場合、設置可能なスペースがあるかだけを確認し、実際には設置しない。

        Returns:
            dict: 結果を含む辞書
                - success (bool): ゲートの設置と起動に成功した場合はTrue
                - message (str): 結果メッセージ
                - portal_base_pos (dict, optional): 設置したゲートの基準座標 {x, y, z}
                - error (str, optional): エラーコード (insufficient_materials, no_space, placement_failed, activation_failed, verification_failed)
        """
        self.bot.chat("ネザーゲートの作成を開始します。")
        result = {
            "success": False,
            "message": "",
        }
        Vec3 = require('vec3')

        # --- 1. 材料チェック ---
        inventory = await self.get_inventory_counts()
        obsidian_count = inventory.get('obsidian', 0)
        flint_and_steel_count = inventory.get('flint_and_steel', 0)

        if obsidian_count < 10:
            result["message"] = f"ネザーゲートの作成に必要な黒曜石が足りません (必要: 10, 所持: {obsidian_count})"
            result["error"] = "insufficient_materials"
            self.bot.chat(result["message"])
            print(result)
            return result
        if flint_and_steel_count < 1 and not check_space_only:
            result["message"] = "ネザーゲートの起動に必要な火打石と打ち金がありません"
            result["error"] = "insufficient_materials"
            self.bot.chat(result["message"])
            print(result)
            return result

        # --- 2. スペース検索 (高さ5, 幅4, 深さ1) ---
        portal_width = 4
        portal_height = 5
        search_distance = 15
        base_pos = None
        orientation = 'z' # 'x' or 'z'

        base_pos = await self.get_nearest_free_space(portal_width, portal_height,1, search_distance)

        if not base_pos:
            result["message"] = f"ネザーゲートを設置するための十分なスペース (高さ{portal_height}, 幅{portal_width}) が見つかりませんでした。"
            result["error"] = "no_space"
            self.bot.chat(result["message"])
            print(result)
            return result

        result["portal_base_pos"] = {"x": base_pos.x, "y": base_pos.y, "z": base_pos.z}

        if check_space_only:
            result["success"] = True
            result["message"] = f"ネザーゲート設置可能なスペースが見つかりました。座標: ({base_pos.x}, {base_pos.y}, {base_pos.z}), 向き: {orientation}軸方向"
            self.bot.chat(result["message"])
            print(result)
            return result

        # スペースに移動
        move_result = await self.move_to_position(base_pos.x, base_pos.y, base_pos.z, 2)
        if not move_result["success"]:
            result["message"] = f"ネザーゲート設置スペースへの移動に失敗しました: {move_result.get('message', '不明')}"
            result["error"] = "movement_failed"
            self.bot.chat(result["message"])
            print(result)
            return result

        # --- 3. ネザーゲートフレーム設置 (10個の黒曜石) ---
        portal_frame_coords = []
        # 底辺 (y=0)
        portal_frame_coords.append(base_pos.offset(0, 0, 0))
        portal_frame_coords.append(base_pos.offset(1, 0, 0))
        portal_frame_coords.append(base_pos.offset(2, 0, 0))
        portal_frame_coords.append(base_pos.offset(3, 0, 0))
        # 柱 (x=0)
        portal_frame_coords.append(base_pos.offset(0, 1, 0))
        portal_frame_coords.append(base_pos.offset(0, 2, 0))
        portal_frame_coords.append(base_pos.offset(0, 3, 0))
        portal_frame_coords.append(base_pos.offset(3, 1, 0))
        portal_frame_coords.append(base_pos.offset(3, 2, 0))
        portal_frame_coords.append(base_pos.offset(3, 3, 0))
        # 上辺 (y=4)
        portal_frame_coords.append(base_pos.offset(0, 4, 0))
        portal_frame_coords.append(base_pos.offset(1, 4, 0))
        portal_frame_coords.append(base_pos.offset(2, 4, 0))
        portal_frame_coords.append(base_pos.offset(3, 4, 0))

        self.bot.chat("ネザーゲートフレームの設置を開始します...")
        placed_count = 0
        for coord in portal_frame_coords:
            place_result = await self.place_block('obsidian', coord.x, coord.y, coord.z)
            if place_result["success"]:
                placed_count += 1
                await asyncio.sleep(0.1) # 設置の間隔を少し空ける
            else:
                # 設置失敗時の処理（すでにブロックがある場合などは許容するかもしれない）
                block_at_coord = self.bot.blockAt(coord)
                if block_at_coord and block_at_coord.name == 'obsidian':
                    self.bot.chat(f"座標 ({coord.x}, {coord.y}, {coord.z}) には既に黒曜石があります。スキップします。")
                    placed_count += 1 # 既に存在する場合もカウント
                    continue
                else:
                    result["message"] = f"ネザーゲートフレームの設置中にエラーが発生しました ({coord.x}, {coord.y}, {coord.z})。理由: {place_result.get('message', '不明')}"
                    result["error"] = "placement_failed"
                    self.bot.chat(result["message"])
                    print(result)
                    # TODO: 設置したブロックを撤去する処理を追加するか検討
                    return result

        if placed_count < 10:
             # このケースは上のエラーハンドリングでカバーされるはずだが念のため
             result["message"] = "ネザーゲートフレームの設置に失敗しました。必要な数の黒曜石を設置できませんでした。"
             result["error"] = "placement_failed"
             self.bot.chat(result["message"])
             print(result)
             return result

        self.bot.chat("ネザーゲートフレームの設置が完了しました。")

        # --- 4. ネザーゲート起動 ---
        self.bot.chat("ネザーゲートの起動を試みます...")

        # 火打石と打ち金を装備
        equip_result = await self.equip('flint_and_steel')
        if not equip_result["success"]:
             result["message"] = "火打石と打ち金の装備に失敗しました。"
             result["error"] = "activation_failed"
             self.bot.chat(result["message"])
             print(result)
             return result

        # 起動ターゲットブロック (フレーム下部の内側の黒曜石)
        activation_target_coord = None
        portal_check_coord = None # ポータル生成確認用座標
        if orientation == 'z':
            activation_target_coord = base_pos.offset(1, 0, 0) # 底辺の左側
            portal_check_coord = base_pos.offset(1, 1, 0) # ゲート内部の左下
        elif orientation == 'x':
            activation_target_coord = base_pos.offset(0, 0, 1) # 底辺の手前側
            portal_check_coord = base_pos.offset(0, 1, 1) # ゲート内部の手前下

        activation_target_block = self.bot.blockAt(activation_target_coord)
        if not activation_target_block or activation_target_block.name != 'obsidian':
            result["message"] = f"ゲート起動のターゲットブロック (黒曜石) が見つかりません ({activation_target_coord.x}, {activation_target_coord.y}, {activation_target_coord.z})"
            result["error"] = "activation_failed"
            self.bot.chat(result["message"])
            print(result)
            return result

        # ターゲットブロックに近づく (必要であれば)
        if self.bot.entity.position.distanceTo(activation_target_coord) > 4.5:
             move_result = await self.move_to_position(activation_target_coord.x, activation_target_coord.y, activation_target_coord.z, 3)
             if not move_result["success"]:
                 result["message"] = f"ゲート起動位置への移動に失敗: {move_result.get('message', '不明')}"
                 result["error"] = "activation_failed"
                 self.bot.chat(result["message"])
                 print(result)
                 return result

        # ターゲットブロックを見る
        self.bot.lookAt(activation_target_coord.offset(0.5, 0.5, 0.5), True) # ブロックの中心を見る

        # 火打石と打ち金を使用 (activateBlock ではなく activateItem かもしれない)
        # Mineflayerの activateBlock はブロック自体にインタラクトする。火打石はブロックに対して使う
        try:
            # どの面に対して使用するかを指定 (ここでは上面を仮定 Vec3(0, 1, 0))
            # activateBlockの第二引数は referenceBlock, 第三引数は faceVector
            # faceVector はターゲットブロックのどの面をクリックするかを指定
            # フレーム底の黒曜石の上面をクリックしてゲートを生成する
            self.bot.activateBlock(activation_target_block, Vec3(0, 1, 0))
            self.bot.chat(f"座標 ({activation_target_block.position.x}, {activation_target_block.position.y}, {activation_target_block.position.z}) の黒曜石に火打石を使用しました。")
            await asyncio.sleep(1.0) # ポータル生成待機
        except Exception as e:
            result["message"] = f"火打石と打ち金の使用中にエラーが発生しました: {str(e)}"
            result["error"] = "activation_failed"
            self.bot.chat(result["message"])
            print(result)
            import traceback
            traceback.print_exc()
            return result

        # --- 5. 起動確認 ---
        portal_block = self.bot.blockAt(portal_check_coord)
        if portal_block and portal_block.name == 'nether_portal':
            result["success"] = True
            result["message"] = f"ネザーゲートが座標 ({base_pos.x}, {base_pos.y}, {base_pos.z}) に正常に作成・起動されました。"
            self.bot.chat(result["message"])
            print(result)
        else:
            result["message"] = f"ネザーゲートの起動に失敗しました。ポータルブロックが生成されませんでした。確認座標: ({portal_check_coord.x}, {portal_check_coord.y}, {portal_check_coord.z}), 実際のブロック: {portal_block.name if portal_block else 'None'}"
            result["error"] = "verification_failed"
            self.bot.chat(result["message"])
            print(result)
        return result