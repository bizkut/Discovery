from javascript import require, On, Once, AsyncTask, once, off
import asyncio
import os

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
        
    def get_inventory_counts(self):
        """
        ボットのインベントリ内の各アイテムの数を辞書形式で返します。

        Returns:
            dict: キーがアイテム名、値がその数量の辞書
            
        Example:
            >>> get_inventory_counts()
            {'birch_planks': 1, 'dirt': 1}
        """
        inventory_counts = {}
        
        # インベントリ内の全アイテムをループ
        for item in self.bot.inventory.items():
            # アイテム名が既に辞書にある場合は数を加算、なければ新規追加
            if item.name in inventory_counts:
                inventory_counts[item.name] += item.count
            else:
                inventory_counts[item.name] = item.count
                
        return inventory_counts
    
    def get_nearest_block(self, block_type, max_distance=64):
        """
        指定されたブロックタイプの最も近いブロックを返します。
        
        Args:
            block_type (str): 探すブロックタイプ
            max_distance (int): 探索する最大距離
            
        Returns:
            Block: 最も近いブロック、見つからない場合はNone
        
        Example:
            >>> get_nearest_block('oak_log')
            Block {
                type: 40,
                metadata: 2,
                light: 0,
                skyLight: 15,
                biome: {
                    color: 0,
                    height: null,
                    name: '',
                    rainfall: 0,
                    temperature: 0,
                    id: 8
                },
                position: Vec3 { x: 18, y: 77, z: 11 },
                stateId: 119,
                computedStates: {},
                name: 'oak_log',
                hardness: 2,
                displayName: 'Oak Log',
                shapes: [ [ 0, 0, 0, 1, 1, 1 ] ],
                boundingBox: 'block',
                transparent: false,
                diggable: true,
                material: 'mineable/axe',
                harvestTools: undefined,
                drops: [ 104 ],
                _properties: { axis: 'z' },
                isWaterlogged: undefined,
                entity: undefined,
                painting: undefined
                }
                Block {
                type: 40,
                metadata: 2,
                light: 0,
                skyLight: 15,
                biome: {
                    color: 0,
                    height: null,
                    name: '',
                    rainfall: 0,
                    temperature: 0,
                    id: 8
                },
                position: Vec3 { x: 18, y: 77, z: 11 },
                stateId: 119,
                computedStates: {},
                name: 'oak_log',
                hardness: 2,
                displayName: 'Oak Log',
                shapes: [ [ 0, 0, 0, 1, 1, 1 ] ],
                boundingBox: 'block',
                transparent: false,
                diggable: true,
                material: 'mineable/axe',
                harvestTools: undefined,
                drops: [ 104 ],
                _properties: { axis: 'z' },
                isWaterlogged: undefined,
                entity: undefined,
                painting: undefined
                }
        """
        try:
            # ブロックのIDを取得
            block_id = None
            if hasattr(self.bot.registry, 'blocksByName') and block_type in self.bot.registry.blocksByName:
                block_id = self.bot.registry.blocksByName[block_type].id
            else:
                print(f"ブロック '{block_type}' がレジストリに見つかりません")

            # matchingパラメータを適切に設定
            matching = None
            if block_id is not None:
                matching = block_id
            else:
                # 直接ブロック名を使う（フォールバック）
                matching = block_type
                
            # ブロックを検索
            block = self.bot.findBlock({
                'point': self.bot.entity.position,
                'matching': matching,
                'maxDistance': max_distance
            })
            
            # 結果を返す
            if block:
                return block
            return None
            
        except Exception as e:
            print(f"ブロック検索中にエラーが発生しました: {str(e)}")
            import traceback
            traceback.print_exc()
            return None
    
    def get_nearest_free_space(self, size=1, distance=8, y_offset=0):
        """
        指定されたサイズの空きスペース（上部が空気で下部が固体ブロック）を見つけます。
        
        Args:
            size (int): 探す空きスペースの（size × size）サイズ。デフォルトは1。
            distance (int): 探索する最大距離。デフォルトは8。
            y_offset (int): 見つかった空きスペースに適用するY座標オフセット。デフォルトは0。
            
        Returns:
            Vec3: 見つかった空きスペースの南西角の座標。見つからない場合はボットの足元の座標を返します。
        
        Example:
            >>> free_space = skills.get_nearest_free_space(2, 10)
            >>> print(f"見つかった空きスペース: x={free_space.x}, y={free_space.y}, z={free_space.z}")
        """
        try:
            Vec3 = require('vec3')
        
            # 空気ブロックを検索
            empty_pos = self.bot.findBlocks({
                'matching': lambda block: block and block.name == 'air',
                'maxDistance': distance,
                'count': 1000
            })
            
            # 各空気ブロックについて、指定されたサイズの空きスペースを確認
            for pos in empty_pos:
                empty = True
                for x_offset in range(size):
                    for z_offset in range(size):
                        # 上部のブロックが空気であることを確認
                        top = self.bot.blockAt(Vec3(
                            pos.x + x_offset,
                            pos.y,
                            pos.z + z_offset
                        ))
                        
                        # 下部のブロックが掘れる固体ブロックであることを確認
                        bottom = self.bot.blockAt(Vec3(
                            pos.x + x_offset,
                            pos.y - 1,
                            pos.z + z_offset
                        ))
                        
                        # 条件チェック（Proxyオブジェクトにlen()が使えないため修正）
                        if (not top or top.name != 'air' or 
                            not bottom or not hasattr(bottom, 'drops') or not bottom.drops or not bottom.diggable):
                            empty = False
                            break
                    
                    if not empty:
                        break
                
                # 適切なスペースが見つかった場合は、そのポジションを返す
                if empty:
                    result = Vec3(pos.x, pos.y + y_offset, pos.z)
                return result
            
            # 適切なスペースが見つからなかった場合は、デフォルトとしてボットの足元の座標を返す
            position = self.bot.entity.position
            return Vec3(int(position.x), int(position.y) + y_offset, int(position.z))
            
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
        
    async def craft_recipe(self, item_name, num=1):
        """
        指定されたアイテムをレシピから作成します。
        
        このメソッドは以下の処理を行います：
        1. 指定されたアイテムのレシピを検索します
        2. 必要に応じてクラフティングテーブルを探すか設置します
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
        
        エラーコード:
            - recipe_not_found: レシピが見つからない
            - crafting_table_required: クラフティングテーブルが必要だが所持していない
            - insufficient_materials: 材料が不足している
            - movement_failed: クラフティングテーブルまで移動できない
            - crafting_error: クラフト実行中にエラー発生
            - unexpected_error: その他の予期せぬエラー
        
        使用例:
            ```python
            # 棒を4本作成
            result = await skills.craft_recipe("stick", 4)
            if result["success"]:
                print(f"作成成功: {result['message']}")
            else:
                print(f"作成失敗: {result['message']}")
                print(f"エラー: {result.get('error', 'unknown')}")
            
            # クラフティングテーブルを作成
            result = await skills.craft_recipe("crafting_table")
            ```
        """
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
            crafting_table = None
            crafting_table_range = 32

            # クラフティングテーブルが必要な場合
            if not recipes or not any(True for _ in recipes):  # Proxyオブジェクトの空チェック
                recipes = self.bot.recipesFor(item_id, None, num, True)
                if not recipes:
                    error_msg = f"{item_name}のレシピが見つかりません"
                    self.bot.chat(error_msg)
                    result["message"] = error_msg
                    result["error"] = "recipe_not_found"
                    return result
                    
                # クラフティングテーブルを探す
                crafting_table = self.get_nearest_block('crafting_table', crafting_table_range)
                if not crafting_table:
                    # インベントリにクラフティングテーブルがあるか確認
                    if self.get_inventory_counts().get('crafting_table', 0) > 0:
                        # クラフティングテーブルを設置
                        pos = self.get_nearest_free_space(1,6)
                        await self.place_block('crafting_table', pos.x, pos.y, pos.z)
                        crafting_table = self.get_nearest_block('crafting_table', crafting_table_range)
                        if crafting_table:
                            recipes = self.bot.recipesFor(item_id, None, 1, crafting_table)
                            placed_table = True
                            print(f"作業台設置後レシピ:{recipes}")
                    else:
                        error_msg = f"{item_name}の作成には作業台が必要ですが、周辺32ブロック以内に作業台が見つからず、インベントリにも作業台がないため作成できません"
                        self.bot.chat(error_msg)
                        result["message"] = error_msg
                        result["error"] = "crafting_table_required"
                        return result
                else:
                    # 近くに作業台がある場合は、レシピを取得
                    recipes = self.bot.recipesFor(item_id, None, 1, crafting_table)
            
            if not recipes or not any(True for _ in recipes):
                # 材料不足の場合、必要な材料を調べる
                required_materials = []
                # レシピから必要な材料を取得
                recipe_data = self.get_item_crafting_recipes(item_name)
                if recipe_data and recipe_data[0]:
                    recipe_dict = recipe_data[0][0]
                    required_materials = [f"{key}: {value}" for key, value in recipe_dict.items()]
                else:
                    required_materials.append("レシピが見つかりません")
                    
                error_msg = f"{item_name}を作成するための材料が不足しています"
                if required_materials:
                    error_msg += f"。必要な材料: {', '.join(required_materials)}"
                    
                self.bot.chat(error_msg)
                result["message"] = error_msg
                result["error"] = "insufficient_materials"
                
                if placed_table:
                    await self.collect_block('crafting_table', 1)
                return result
                
            # クラフティングテーブルまで移動
            if crafting_table and self.bot.entity.position.distanceTo(crafting_table.position) > 4:
                move_result = await self.move_to_position(crafting_table.position.x, crafting_table.position.y, crafting_table.position.z)
                if not move_result:
                    error_msg = "クラフティングテーブルまで移動できません"
                    self.bot.chat(error_msg)
                    result["message"] = error_msg
                    result["error"] = "movement_failed"
                    return result
                
            recipe = recipes[0]
            try:

                # レシピの有効性チェック
                if not recipe or not hasattr(recipe, 'result'):
                    error_msg = f"{item_name}の有効なレシピが見つかりません"
                    self.bot.chat(error_msg)
                    result["message"] = error_msg
                    result["error"] = "invalid_recipe"
                    return result

                # クラフト実行
                self.bot.craft(recipe, num, crafting_table)
                success_msg = f"{item_name}を{num}個作成しました"
                self.bot.chat(success_msg)
                
                # 設置したクラフティングテーブルを回収
                if placed_table:
                    await self.collect_block('crafting_table', 1)
                
                result["success"] = True
                result["message"] = success_msg
                return result
                
            except Exception as e:
                error_msg = f"クラフト中にエラーが発生しました: {str(e)}"
                self.bot.chat(error_msg)
                result["message"] = error_msg
                result["error"] = "crafting_error"
                result["exception"] = str(e)
                
                if placed_table:
                    await self.collect_block('crafting_table', 1)
                return result
                
        except Exception as e:
            error_msg = f"予期せぬエラーが発生しました: {str(e)}"
            self.bot.chat(error_msg)
            result["message"] = error_msg
            result["error"] = "unexpected_error"
            result["exception"] = str(e)
            import traceback
            traceback.print_exc()
            return result
        
    async def place_block(self, block_type, x, y, z, place_on='bottom', dont_cheat=False):
        """
        指定された座標にブロックを設置します。隣接するブロックから設置します。
        設置場所にブロックがある場合や、設置できる場所がない場合は失敗します。
        
        Args:
            block_type (str): 設置するブロックタイプ
            x (float): 設置するX座標
            y (float): 設置するY座標
            z (float): 設置するZ座標
            place_on (str): 優先的に設置する面の方向。'top', 'bottom', 'north', 'south', 'east', 'west', 'side'から選択。デフォルトは'bottom'
            dont_cheat (bool): チートモードでも通常の方法でブロックを設置するかどうか。デフォルトはFalse
            
        Returns:
            dict: 結果を含む辞書
                - success (bool): 設置に成功した場合はTrue、失敗した場合はFalse
                - message (str): 結果メッセージ
                - position (dict): 設置を試みた位置 {x, y, z}
                - block_type (str): 設置しようとしたブロックタイプ
                - error (str, optional): エラーがある場合のエラーコード
                
        Example:
            >>> result = await skills.place_block("oak_planks", 100, 64, 100)
            >>> if result["success"]:
            >>>     print(f"成功: {result['message']}")
            >>> else:
            >>>     print(f"失敗: {result['message']}")
        """
        result = {
            "success": False,
            "message": "",
            "position": {"x": x, "y": y, "z": z},
            "block_type": block_type
        }
        
        # ブロックIDの検証
        try:
            block_id = None
            
            # ブロック名からIDを取得
            block_id = self._get_item_id(block_type)
    
            if block_id is None:
                result["message"] = f"無効なブロックタイプです: {block_type}"
                result["error"] = "invalid_block_type"
                self.bot.chat(result["message"])
                return result
        except Exception as e:
            result["message"] = f"ブロックタイプの検証中にエラーが発生しました: {str(e)}"
            result["error"] = "block_validation_error"
            self.bot.chat(result["message"])
            return result
            
        # Vec3オブジェクトを作成
        Vec3 = require('vec3')
        target_dest = Vec3(int(x), int(y), int(z))
        
        # チートモードでの処理
        if hasattr(self.bot.modes, 'isOn') and self.bot.modes.isOn('cheat') and not dont_cheat:
            # インベントリ制限がある場合はチェック
            if hasattr(self.bot, 'restrict_to_inventory') and self.bot.restrict_to_inventory:
                has_block = False
                for item in self.bot.inventory.items():
                    if item.name == block_type:
                        has_block = True
                        break
                        
                if not has_block:
                    result["message"] = f"{block_type}をインベントリに持っていないため設置できません"
                    result["error"] = "item_not_in_inventory"
                    self.bot.chat(result["message"])
                    return result
            
            try:
                # 向きを反転
                face_dict = {
                    'north': 'south',
                    'south': 'north',
                    'east': 'west',
                    'west': 'east',
                    'top': 'bottom',
                    'bottom': 'top'
                }
                
                face = face_dict.get(place_on, place_on)
                block_command = block_type
                
                # 特殊なブロックの処理
                if 'torch' in block_type and place_on != 'bottom':
                    # 松明を壁に設置する場合
                    block_command = block_type.replace('torch', 'wall_torch')
                    if place_on != 'side' and place_on != 'top':
                        block_command += f"[facing={face}]"
                        
                elif block_type.endswith('button') or block_type == 'lever':
                    # ボタンやレバーの設置
                    if place_on == 'top':
                        block_command += "[face=ceiling]"
                    elif place_on == 'bottom':
                        block_command += "[face=floor]"
                    else:
                        block_command += f"[facing={face}]"
                        
                elif block_type in ['ladder', 'repeater', 'comparator']:
                    # はしご、リピーター、コンパレーター
                    block_command += f"[facing={face}]"
                    
                elif 'stairs' in block_type:
                    # 階段
                    block_command += f"[facing={face}]"
                
                # setblockコマンドを実行
                command = f'/setblock {int(x)} {int(y)} {int(z)} {block_command}'
                self.bot.chat(command)
                
                # ドアや特殊ブロックの追加処理
                if 'door' in block_type:
                    self.bot.chat(f'/setblock {int(x)} {int(y)+1} {int(z)} {block_type}[half=upper]')
                elif 'bed' in block_type:
                    self.bot.chat(f'/setblock {int(x)} {int(y)} {int(z)-1} {block_type}[part=head]')
                    
                result["message"] = f"/setblockを使用して{block_type}を座標({target_dest})に設置しました"
                result["success"] = True
                self.bot.chat(result["message"])
                return result
                
            except Exception as e:
                result["message"] = f"チートモードでのブロック設置中にエラーが発生しました: {str(e)}"
                result["error"] = "cheat_mode_error"
                self.bot.chat(result["message"])
                return result
                
        # 通常の設置処理
        try:
            # アイテム名の修正（一部のブロックは設置時に名前が変わる）
            item_name = block_type
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
                    print(f"クリエイティブモードでのアイテム取得エラー: {e}")
            
            # ブロックがない場合は失敗
            if not block_item:
                result["message"] = f"{block_type}をインベントリに持っていません"
                result["error"] = "item_not_in_inventory"
                self.bot.chat(result["message"])
                return result
                
            # 設置先のブロックをチェック
            target_block = self.bot.blockAt(target_dest)
            if target_block.name == block_type:
                result["message"] = f"{block_type}は既に座標({target_block.position})にあります"
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
            if block_type not in dont_move_for and (
                player_pos.distanceTo(target_block.position) < 1 or 
                player_pos_above.distanceTo(target_block.position) < 1
            ):
                # プレイヤーが設置位置と重なっている場合、少し離れる
                try:
                    if hasattr(self.pathfinder.goals, 'GoalNear') and hasattr(self.pathfinder.goals, 'GoalInvert'):
                        goal = self.pathfinder.goals.GoalNear(target_block.position.x, target_block.position.y, target_block.position.z, 2)
                        inverted_goal = self.pathfinder.goals.GoalInvert(goal)
                        self.bot.pathfinder.setMovements(self.pathfinder.Movements(self.bot))
                        self.bot.pathfinder.goto(inverted_goal)
                except Exception as e:
                    result["message"] = f"設置位置から離れる際にエラーが発生しました: {str(e)}"
                    result["error"] = "movement_error"
                    self.bot.chat(result["message"])
                    return result
            
            # ブロックが遠すぎる場合は近づく
            if self.bot.entity.position.distanceTo(target_block.position) > 4.5:
                try:
                    if hasattr(self.pathfinder.goals, 'GoalNear'):
                        movements = self.pathfinder.Movements(self.bot)
                        self.bot.pathfinder.setMovements(movements)
                        self.bot.pathfinder.goto(self.pathfinder.goals.GoalNear(
                            target_block.position.x, 
                            target_block.position.y, 
                            target_block.position.z, 
                            4
                        ))
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
                result["message"] = f"{block_type}を座標({target_dest})に設置しました"
                result["success"] = True
                self.bot.chat(result["message"])
                
                # 設置完了を少し待つ
                await asyncio.sleep(0.2)
                return result
            except Exception as e:
                    result["message"] = f"{block_type}の設置中にエラーが発生しました: {str(e)}"
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
                
        Example:
            >>> result = await skills.equip("iron_pickaxe")
            >>> if result["success"]:
            >>>     print(f"成功: {result['message']}")
            >>> else:
            >>>     print(f"失敗: {result['message']}")
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
                
        Example:
            >>> result = await skills.discard("dirt", 10)
            >>> if result["success"]:
            >>>     print(f"成功: {result['message']}")
            >>> else:
            >>>     print(f"失敗: {result['message']}")
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
                
        Example:
            >>> result = await skills.put_in_chest("stone", 64)
            >>> if result["success"]:
            >>>     print(f"成功: {result['message']}")
            >>> else:
            >>>     print(f"失敗: {result['message']}")
        """
        result = {
            "success": False,
            "message": "",
            "item": item_name,
            "count": 0
        }
        
        try:
            # 最も近いチェストを探す
            chest = self.get_nearest_block("chest", 32)
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
                
        Example:
            >>> result = await skills.take_from_chest("oak_log")
            >>> if result["success"]:
            >>>     print(f"成功: {result['message']}")
            >>> else:
            >>>     print(f"失敗: {result['message']}")
        """
        result = {
            "success": False,
            "message": "",
            "item": item_name,
            "count": 0
        }
        
        try:
            # 最も近いチェストを探す
            chest = self.get_nearest_block("chest", 32)
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

    async def view_chest(self):
        """
        最も近いチェストの中身を表示します。
        
        Returns:
            dict: 結果を含む辞書
                - success (bool): チェストを表示できた場合はTrue、失敗した場合はFalse
                - message (str): 結果メッセージ
                - items (list, optional): チェスト内のアイテムリスト（成功時のみ）
                
        Example:
            >>> result = await skills.view_chest()
            >>> if result["success"]:
            >>>     print(f"成功: {result['message']}")
            >>>     if "items" in result:
            >>>         for item in result["items"]:
            >>>             print(f"{item['count']}個の{item['name']}")
            >>> else:
            >>>     print(f"失敗: {result['message']}")
        """
        result = {
            "success": False,
            "message": ""
        }
        
        try:
            # 最も近いチェストを探す
            chest = self.get_nearest_block("chest", 32)
            if not chest:
                result["message"] = "近くにチェストが見つかりませんでした。"
                self.bot.chat(result["message"])
                return result
                
            # チェストまで移動
            await self.move_to_position(chest.position.x, chest.position.y, chest.position.z, 2)
            
            # チェストを開く
            chest_container = self.bot.openContainer(chest)
            
            # チェスト内のアイテムを取得
            items = chest_container.containerItems()
            
            # アイテムをリストに変換
            item_list = []
            if items:
                for item in items:
                    if item:  # Noneでないアイテムのみ追加
                        item_list.append({
                            "name": item.name,
                            "count": item.count
                        })
            
            # 結果を生成
            if not item_list:
                result["message"] = "チェストは空です。"
                self.bot.chat(result["message"])
            else:
                # アイテムリストをテキストに変換
                items_text = []
                for item in item_list:
                    items_text.append(f"{item['name']} x {item['count']}")
                
                result["message"] = f"チェストの中身: {', '.join(items_text)}"
                result["items"] = item_list
                print_data = "チェストには以下のアイテムが含まれています:\n"
                for item in item_list:
                    print_data += f"{item['name']} x {item['count']}\n"
                self.bot.chat(print_data)
            
            # チェストを閉じる
            chest_container.close()
            
            result["success"] = True
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
            
        Returns:
            dict: 結果を含む辞書
                - success (bool): アイテムを消費できた場合はTrue、失敗した場合はFalse
                - message (str): 結果メッセージ
                - item (str, optional): 消費したアイテム名（成功時のみ）
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

    async def go_to_nearest_block(self, block_type, min_distance=2, range=64):
        """
        指定されたタイプの最も近いブロックまで移動します。
        
        Args:
            block_type (str): 移動先のブロックタイプ
            min_distance (int): ブロックから保つ距離。デフォルトは2
            range (int): ブロックを探す最大範囲。デフォルトは64
            
        Returns:
            dict: 結果を含む辞書
                - success (bool): ブロックまで移動できた場合はTrue、失敗した場合はFalse
                - message (str): 結果メッセージ
                - block_type (str): 探したブロックタイプ
                - position (dict, optional): 見つかったブロックの位置 {x, y, z}（成功時のみ）
                
        Example:
            >>> result = await skills.go_to_nearest_block("oak_log")
            >>> if result["success"]:
            >>>     print(f"成功: {result['message']}")
            >>> else:
            >>>     print(f"失敗: {result['message']}")
        """
        result = {
            "success": False,
            "message": "",
            "block_type": block_type
        }
        
        try:
            # 最大検索範囲の制限
            MAX_RANGE = 512
            if range > MAX_RANGE:
                range = MAX_RANGE
                self.bot.chat(f"最大検索範囲を{MAX_RANGE}ブロックに制限します。")
                
            # 最も近いブロックを探す
            block = self.get_nearest_block(block_type, range)
            if not block:
                result["message"] = f"{range}ブロック以内に{block_type}が見つかりませんでした。"
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
                result["message"] = f"{block_type}への移動中にエラーが発生しました: {move_result['message']}"
                self.bot.chat(result["message"])
                return result
                
            result["success"] = True
            result["message"] = f"{block_type}(X:{position.x}, Y:{position.y}, Z:{position.z})に到達しました。"
            self.bot.chat(result["message"])
            return result
            
        except Exception as e:
            result["message"] = f"{block_type}への移動中に予期せぬエラーが発生しました: {str(e)}"
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
                
        Example:
            >>> result = await skills.go_to_nearest_entity("villager")
            >>> if result["success"]:
            >>>     print(f"成功: {result['message']}")
            >>> else:
            >>>     print(f"失敗: {result['message']}")
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
                
        Example:
            >>> result = await skills.go_to_bed()
            >>> if result["success"]:
            >>>     print(f"成功: {result['message']}")
            >>> else:
            >>>     print(f"失敗: {result['message']}")
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
                
        Example:
            >>> result = await skills.move_away(8)
            >>> if result["success"]:
            >>>     print(f"成功: {result['message']}")
            >>> else:
            >>>     print(f"失敗: {result['message']}")
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
                        path = await self.bot.pathfinder.getPathTo(move, inverted_goal, 10000)
                        
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
                await self.bot.pathfinder.goto(inverted_goal)
                
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

    async def move_away_from_entity(self, entity, distance=16):
        """
        指定されたエンティティから離れます。
        
        Args:
            entity: 離れるべきエンティティ
            distance (int): エンティティから離れる距離。デフォルトは16
            
        Returns:
            dict: 結果を含む辞書
                - success (bool): 移動に成功した場合はTrue、失敗した場合はFalse
                - message (str): 結果メッセージ
                - entity_name (str): エンティティの名前
                - start_position (dict): 開始位置 {x, y, z}
                - end_position (dict, optional): 移動後の位置 {x, y, z}（成功時のみ）
                
        Example:
            >>> entity = bot._get_nearby_entity_of_type("zombie", 24)
            >>> if entity:
            >>>     result = await skills.move_away_from_entity(entity)
            >>>     if result["success"]:
            >>>         print(f"成功: {result['message']}")
            >>>     else:
            >>>         print(f"失敗: {result['message']}")
        """
        result = {
            "success": False,
            "message": "",
            "entity_name": entity.name if hasattr(entity, 'name') else "不明なエンティティ",
            "start_position": {
                "x": self.bot.entity.position.x,
                "y": self.bot.entity.position.y,
                "z": self.bot.entity.position.z
            }
        }
        
        try:
            # エンティティの名前を取得
            entity_name = entity.name if hasattr(entity, 'name') else "不明なエンティティ"
            
            # GoalFollowとGoalInvertを使用してエンティティから離れるゴールを設定
            if hasattr(self.pathfinder.goals, 'GoalFollow') and hasattr(self.pathfinder.goals, 'GoalInvert'):
                # エンティティを追跡するゴールを設定
                goal = self.pathfinder.goals.GoalFollow(entity, distance)
                # ゴールを反転して、エンティティから離れるようにする
                inverted_goal = self.pathfinder.goals.GoalInvert(goal)
                
                # パスファインダーの設定
                self.bot.pathfinder.setMovements(self.pathfinder.Movements(self.bot))
                
                # エンティティから離れる方向に移動
                await self.bot.pathfinder.goto(inverted_goal)
                
                # 新しい位置を取得
                new_pos = self.bot.entity.position
                result["end_position"] = {
                    "x": new_pos.x,
                    "y": new_pos.y,
                    "z": new_pos.z
                }
                
                # エンティティとの現在の距離を計算
                current_distance = self.bot.entity.position.distanceTo(entity.position)
                
                result["success"] = True
                result["message"] = f"{entity_name}から{distance}ブロック離れるように移動しました。現在の距離: {current_distance:.1f}ブロック"
                self.bot.chat(result["message"])
                return result
            else:
                result["message"] = "パスファインダーのゴール機能が利用できません。"
                self.bot.chat(result["message"])
                return result
                
        except Exception as e:
            result["message"] = f"{result['entity_name']}から離れる移動中に予期せぬエラーが発生しました: {str(e)}"
            self.bot.chat(result["message"])
            import traceback
            traceback.print_exc()
            return result

    async def avoid_enemies(self, distance=16):
        """
        周囲の敵対的なモブから指定した距離だけ離れます。
        
        Args:
            distance (int): モブから離れる距離。デフォルトは16
            
        Returns:
            dict: 結果を含む辞書
                - success (bool): 移動に成功した場合はTrue、失敗した場合はFalse
                - message (str): 結果メッセージ
                - enemies_avoided (int): 回避した敵の数
                - start_position (dict): 開始位置 {x, y, z}
                - end_position (dict, optional): 最終移動位置 {x, y, z}（成功時のみ）
                
        Example:
            >>> result = await skills.avoid_enemies(8)
            >>> if result["success"]:
            >>>     print(f"成功: {result['message']}")
            >>> else:
            >>>     print(f"失敗: {result['message']}")
        """
        result = {
            "success": False,
            "message": "",
            "enemies_avoided": 0,
            "start_position": {
                "x": self.bot.entity.position.x,
                "y": self.bot.entity.position.y,
                "z": self.bot.entity.position.z
            }
        }
        
        try:
            # 自己防衛モードを一時停止（ダメージによる割り込みを防ぐ）
            if hasattr(self.bot.modes, 'pause'):
                self.bot.modes.pause('self_preservation')
            
            # 敵対的なモブを見つける
            enemy = self._get_nearest_hostile_entity(distance)
            enemies_avoided = 0
            
            while enemy:
                enemies_avoided += 1
                
                # GoalFollowとGoalInvertを使用してエンティティから離れるゴールを設定
                if hasattr(self.pathfinder.goals, 'GoalFollow') and hasattr(self.pathfinder.goals, 'GoalInvert'):
                    # エンティティを追跡するゴールを設定（少し余分に離れる）
                    follow = self.pathfinder.goals.GoalFollow(enemy, distance + 1)
                    # ゴールを反転して、エンティティから離れるようにする
                    inverted_goal = self.pathfinder.goals.GoalInvert(follow)
                    
                    # パスファインダーの設定
                    self.bot.pathfinder.setMovements(self.pathfinder.Movements(self.bot))
                    self.bot.pathfinder.setGoal(inverted_goal, True)
                    
                    # 少し待機して移動を続行
                    await asyncio.sleep(0.5)
                    
                    # 再度最も近い敵対的なモブを確認
                    enemy = self._get_nearest_hostile_entity(distance)
                    
                    # 中断コードがある場合は停止
                    if hasattr(self.bot, 'interrupt_code') and self.bot.interrupt_code:
                        break
                    
                    # エンティティが近すぎる場合は攻撃（3ブロック以内）
                    if enemy and self.bot.entity.position.distanceTo(enemy.position) < 3:
                        attack_result = await self.attack_entity(enemy, kill=False)
                        # 攻撃に失敗した場合でも続行
                else:
                    result["message"] = "パスファインダーのゴール機能が利用できません。"
                    self.bot.chat(result["message"])
                    return result
            
            # パスファインダーを停止
            self.bot.pathfinder.stop()
            
            # 結果を設定
            result["enemies_avoided"] = enemies_avoided
            result["end_position"] = {
                "x": self.bot.entity.position.x,
                "y": self.bot.entity.position.y,
                "z": self.bot.entity.position.z
            }
            
            if enemies_avoided > 0:
                result["success"] = True
                result["message"] = f"{enemies_avoided}体の敵対的モブから{distance}ブロック離れました。"
            else:
                result["message"] = f"{distance}ブロック以内に敵対的モブが見つかりませんでした。"
                
            self.bot.chat(result["message"])
            return result
                
        except Exception as e:
            result["message"] = f"敵対的モブからの回避中に予期せぬエラーが発生しました: {str(e)}"
            self.bot.chat(result["message"])
            import traceback
            traceback.print_exc()
            return result

    async def collect_block(self, block_type, num=1, exclude=None):
        """
        指定されたタイプのブロックを収集します。
        
        Args:
            block_type (str): 収集するブロックのタイプ
            num (int): 収集するブロックの数。デフォルトは1
            exclude (list, optional): 除外するブロックの位置のリスト
            
        Returns:
            dict: 結果を含む辞書
                - success (bool): 収集に成功した場合はTrue、失敗した場合はFalse
                - message (str): 結果メッセージ
                - collected (int): 収集したブロックの数
                - block_type (str): 収集しようとしたブロックタイプ
                - error (str, optional): エラーがある場合のエラーコード
        """
        result = {
            "success": False,
            "message": "",
            "collected": 0,
            "block_type": block_type
        }
        
        if num < 1:
            result["message"] = f"無効な収集数量: {num}"
            result["error"] = "invalid_number"
            self.bot.chat(result["message"])
            return result
            
        # 同等のブロックタイプをリストに追加
        blocktypes = [block_type]
        
        # 特殊処理: 鉱石ブロックの対応を追加
        ores = ['coal', 'diamond', 'emerald', 'iron', 'gold', 'lapis_lazuli', 'redstone']
        if block_type in ores:
            blocktypes.append(f"{block_type}_ore")
        
        # 深層岩鉱石の対応
        if block_type.endswith('ore'):
            blocktypes.append(f"deepslate_{block_type}")
            
        # dirtの特殊処理
        if block_type == 'dirt':
            blocktypes.append('grass_block')
            
        collected = 0
        
        for i in range(num):
            blocks = []
            for btype in blocktypes:
                found_block = self.get_nearest_block(btype, 64)
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
                    result["message"] = f"近くに{block_type}が見つかりません。"
                else:
                    result["message"] = f"これ以上{block_type}が見つかりません。"
                result["error"] = "no_blocks_found"
                break
                
            block = blocks[0]
            
            # 適切なツールを装備
            self.bot.tool.equipForBlock(block)
            if self.bot.heldItem:
                held_item_id = self.bot.heldItem.type
            else:
                held_item_id = None
            if not block.canHarvest(held_item_id):
                result["message"] = f"{block_type}を採掘するための適切なツールがありません。"
                result["error"] = "no_suitable_tool"
                return result
                
            try:
                self.bot.collectBlock.collect(block)
                collected += 1
                await self.auto_light()
            except Exception as e:
                if str(e) == 'NoChests':
                    result["message"] = f"{block_type}の収集に失敗: インベントリが一杯で、保管場所がありません。"
                    result["error"] = "inventory_full"
                    break
                else:
                    result["message"] = f"{block_type}の収集に失敗: {str(e)}"
                    result["error"] = "collection_failed"
                    continue
                    
        result["collected"] = collected
        result["success"] = collected > 0
        if not result["message"]:
            result["message"] = f"{block_type}を{collected}個収集しました。"
        
        self.bot.chat(result["message"])
        return result
        
    def should_place_torch(self):
        """
        トーチを設置すべきかどうかを判断します。
        暗い場所にいる場合やブロックの明るさが一定以下の場合にトーチを設置します。
        
        Returns:
            bool: トーチを設置すべき場合はTrue
        """
        try:
            # インベントリにトーチがあるか確認
            inventory = self.get_inventory_counts()
            if inventory.get('torch', 0) <= 0:
                return False
                
            # 現在位置の明るさを確認（可能であれば）
            current_pos = self.bot.entity.position
            pos_block = self.bot.blockAt(current_pos)
            
            # 明るさの閾値（元のJavaScriptコード参考）
            # 地下か夜間で、明るさが低い場合にトーチを設置
            is_underground = current_pos.y < 60
            is_dark = False
            
            # 明るさの情報が取得できる場合
            if hasattr(pos_block, 'light') and pos_block.light is not None:
                is_dark = pos_block.light < 8
            elif hasattr(pos_block, 'skyLight') and pos_block.skyLight is not None:
                is_dark = pos_block.skyLight < 8
                
            # 30分のトーチ間隔を保つ（位置ベース）
            last_torch_pos = getattr(self, '_last_torch_pos', None)
            if last_torch_pos:
                torch_distance = current_pos.distanceTo(last_torch_pos)
                if torch_distance < 8:  # 8ブロック以内にトーチがある
                    return False
                    
            return is_underground and is_dark
        except Exception as e:
            print(f"トーチ設置判定エラー: {e}")
            return False
            
    async def auto_light(self):
        """
        必要に応じて現在位置にトーチを設置します。
        
        Returns:
            bool: トーチを設置した場合はTrue、そうでない場合はFalse
        """
        try:
            if self.should_place_torch():
                pos = self.bot.entity.position
                Vec3 = require('vec3')
                # 足元にトーチを設置
                floor_pos = Vec3(
                    round(pos.x),
                    round(pos.y) - 1,  # 足元
                    round(pos.z)
                )
                
                # トーチを設置
                result = await self.place_block('torch', floor_pos.x, floor_pos.y + 1, floor_pos.z, 'bottom', True)
                
                if result:
                    # 最後にトーチを設置した位置を記録
                    self._last_torch_pos = pos.clone()
                    return True
            return False
        except Exception as e:
            print(f"トーチ設置エラー: {e}")
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
        
    async def move_to_position(self, x, y, z, min_distance=2):
        """
        指定された位置まで移動します。
        
        Args:
            x (float): X座標
            y (float): Y座標
            z (float): Z座標
            min_distance (int): 目標位置からの最小距離
            
        Returns:
            dict: 結果を含む辞書
                - success (bool): 移動に成功した場合はTrue、失敗した場合はFalse
                - message (str): 結果メッセージ
                - position (dict): 到達した位置 {x, y, z}
                - error (str, optional): エラーがある場合のエラーコード
            
        Example:
            >>> result = await skills.move_to_position(100, 64, 100)
            >>> if result["success"]:
            >>>     print(f"成功: {result['message']}")
            >>> else:
            >>>     print(f"失敗: {result['message']}")
        """
        result = {
            "success": False,
            "message": "",
            "position": {"x": x, "y": y, "z": z}
        }
        
        if x is None or y is None or z is None:
            result["message"] = f"移動先の座標が不完全です：x:{x} y:{y} z:{z}"
            result["error"] = "invalid_coordinates"
            self.bot.chat(result["message"])
            return result
                
        # チートモードの場合はテレポート
        if hasattr(self.bot.modes, 'isOn') and self.bot.modes.isOn('cheat'):
            self.bot.chat(f"/tp @s {x} {y} {z}")
            result["message"] = f"{x}, {y}, {z}にテレポートしました"
            result["success"] = True
            self.bot.chat(result["message"])
            return result
            
        # パスファインダーを使用して移動
        Goal = self.pathfinder.goals
        try:
            # パスファインダーの設定
            self.bot.pathfinder.setMovements(self.pathfinder.Movements(self.bot))
            goal = Goal.GoalNear(x, y, z, min_distance)
            
            # 移動実行
            self.bot.pathfinder.goto(goal)
            
            # 現在位置を取得して結果に設定
            current_pos = self.bot.entity.position
            result["position"] = {
                "x": current_pos.x,
                "y": current_pos.y,
                "z": current_pos.z
            }
            
            result["message"] = f"{x}, {y}, {z}に到着しました"
            result["success"] = True
            return result
            
        except Exception as e:
            result["message"] = f"移動中にエラーが発生しました: {str(e)}"
            result["error"] = "movement_error"
            self.bot.chat(result["message"])
            print(f"移動エラー: {e}")
            import traceback
            traceback.print_exc()
            return result
        
    async def smelt_item(self, item_name, num=1):
        """
        かまどにアイテムを入れて精錬します。燃料として石炭を使用します。
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
            
        エラーコード:
            - not_smeltable: 精錬できないアイテム
            - no_furnace: かまどがない
            - already_smelting: 既に別のアイテムを精錬中
            - insufficient_items: 精錬するアイテムが足りない
            - no_fuel: 燃料がない
            - furnace_error: かまど操作中のエラー
            
        Example:
            >>> result = await skills.smelt_item("raw_iron", 5)
            >>> if result["success"]:
            >>>     print(f"成功: {result['message']}")
            >>> else:
            >>>     print(f"失敗: {result['message']}")
        """
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
        furnace_block = self.get_nearest_block('furnace', 32)
        if not furnace_block:
            # かまどを持っているか確認
            if self.get_inventory_counts().get('furnace', 0) > 0:
                # かまどを設置
                pos = self.get_nearest_free_space(1)
                place_result = await self.place_block('furnace', pos.x, pos.y, pos.z)
                if place_result:
                    furnace_block = self.get_nearest_block('furnace', 32)
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
            await self.bot.lookAt(furnace_block.position)
            
            # かまどを開く
            furnace = await self.bot.openFurnace(furnace_block)
            
            # 既に精錬中のアイテムがあるか確認
            input_item = furnace.inputItem()
            if input_item and input_item.type and input_item.count > 0:
                if self._get_item_name(input_item.type) != item_name:
                    result["message"] = f"かまどは既に{self._get_item_name(input_item.type)}を精錬中です"
                    result["error"] = "already_smelting"
                    await furnace.close()
                    
                    # 設置したかまどを回収
                    if placed_furnace:
                        await self.collect_block('furnace', 1)
                        
                    self.bot.chat(result["message"])
                    return result
                    
            # 精錬するアイテムを持っているか確認
            inv_counts = self.get_inventory_counts()
            if not inv_counts.get(item_name, 0) or inv_counts.get(item_name, 0) < num:
                result["message"] = f"精錬するための{item_name}が足りません"
                result["error"] = "insufficient_items"
                await furnace.close()
                
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
                    await furnace.close()
                    
                    # 設置したかまどを回収
                    if placed_furnace:
                        await self.collect_block('furnace', 1)
                        
                    self.bot.chat(result["message"])
                    return result
                    
                # 燃料の必要数を計算（1つの石炭で8個精錬可能）
                fuel_needed = (num + 7) // 8  # 切り上げ除算
                
                if fuel.count < fuel_needed:
                    result["message"] = f"{num}個の{item_name}を精錬するには{fuel_needed}個の{fuel.name}が必要ですが、{fuel.count}個しかありません"
                    result["error"] = "insufficient_fuel"
                    await furnace.close()
                    
                    # 設置したかまどを回収
                    if placed_furnace:
                        await self.collect_block('furnace', 1)
                        
                    self.bot.chat(result["message"])
                    return result
                    
                # 燃料を投入
                await furnace.putFuel(fuel.type, None, fuel_needed)
                self.bot.chat(f"かまどに{fuel_needed}個の{fuel.name}を燃料として投入しました")
                
            # 精錬するアイテムをかまどに入れる
            item_id = self._get_item_id(item_name)
            await furnace.putInput(item_id, None, num)
            
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
                    smelted_item = await furnace.takeOutput()
                    if smelted_item:
                        total_smelted += smelted_item.count
                        collected = True
                        
                # 何も取得できなかった場合
                if not collected and not collected_last:
                    break  # 前回も今回も何も取得できなかった場合は終了
                    
                collected_last = collected
                
            # かまどを閉じる
            await furnace.close()
            
            # 設置したかまどを回収
            if placed_furnace:
                await self.collect_block('furnace', 1)
                
            # 結果を設定
            if total_smelted == 0:
                result["message"] = f"{item_name}の精錬に失敗しました"
                result["error"] = "smelting_failed"
                self.bot.chat(result["message"])
                return result
                
            if total_smelted < num:
                result["message"] = f"{num}個中{total_smelted}個の{item_name}を精錬しました"
                result["success"] = True
                result["smelted"] = total_smelted
                
                if smelted_item:
                    result["smelted_item_name"] = self._get_item_name(smelted_item.type)
                    
                self.bot.chat(result["message"])
                return result
                
            result["message"] = f"{item_name}を{total_smelted}個精錬しました"
            if smelted_item:
                result["smelted_item_name"] = self._get_item_name(smelted_item.type)
                result["message"] = f"{item_name}を精錬し、{total_smelted}個の{self._get_item_name(smelted_item.type)}を取得しました"
                
            result["success"] = True
            result["smelted"] = total_smelted
            self.bot.chat(result["message"])
            return result
            
        except Exception as e:
            result["message"] = f"かまど操作中にエラーが発生しました: {str(e)}"
            result["error"] = "furnace_error"
            
            import traceback
            traceback.print_exc()
            
            self.bot.chat(result["message"])
            
            # 設置したかまどを回収
            if placed_furnace:
                try:
                    await self.collect_block('furnace', 1)
                except:
                    pass
                    
            return result
            
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
        アイテムIDからアイテム名を取得します。
        
        Args:
            item_id: アイテムID
            
        Returns:
            str: アイテム名
        """
        try:
            if hasattr(self.mcdata, 'items'):
                for item in self.mcdata.items:
                    if item.id == item_id:
                        return item.name
            elif hasattr(self.bot.registry, 'itemsByType'):
                item = self.bot.registry.itemsByType[item_id]
                if item:
                    return item.name
        except:
            pass
            
        return f"unknown_item_{item_id}"
        
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
        
    async def clear_nearest_furnace(self):
        """
        最も近いかまどからすべてのアイテムを取り出します。
        
        Returns:
            dict: 結果を含む辞書
                - success (bool): 成功した場合はTrue
                - message (str): 結果メッセージ
                - error (str, optional): エラーがある場合のエラーコード
                - items (dict, optional): 取り出したアイテムの情報
        """
        result = {
            "success": False,
            "message": "",
            "items": {}
        }
        
        # かまどを探す
        furnace_block = self.get_nearest_block('furnace', 32)
        if not furnace_block:
            result["message"] = "近くにかまどがありません"
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
            
        try:
            # かまどを開く
            furnace = await self.bot.openFurnace(furnace_block)
            
            # アイテムを取り出す
            smelted_item = None
            input_item = None
            fuel_item = None
            
            if furnace.outputItem():
                smelted_item = await furnace.takeOutput()
                if smelted_item:
                    result["items"]["output"] = {
                        "name": self._get_item_name(smelted_item.type),
                        "count": smelted_item.count
                    }
                    
            if furnace.inputItem():
                input_item = await furnace.takeInput()
                if input_item:
                    result["items"]["input"] = {
                        "name": self._get_item_name(input_item.type),
                        "count": input_item.count
                    }
                    
            if furnace.fuelItem():
                fuel_item = await furnace.takeFuel()
                if fuel_item:
                    result["items"]["fuel"] = {
                        "name": self._get_item_name(fuel_item.type),
                        "count": fuel_item.count
                    }
                    
            # かまどを閉じる
            await furnace.close()
            
            # 結果メッセージを作成
            smelted_desc = f"{smelted_item.count}個の{self._get_item_name(smelted_item.type)}" if smelted_item else "0個の精錬済みアイテム"
            input_desc = f"{input_item.count}個の{self._get_item_name(input_item.type)}" if input_item else "0個の材料"
            fuel_desc = f"{fuel_item.count}個の{self._get_item_name(fuel_item.type)}" if fuel_item else "0個の燃料"
            
            result["message"] = f"かまどから{smelted_desc}、{input_desc}、{fuel_desc}を回収しました"
            result["success"] = True
            
            self.bot.chat(result["message"])
            return result
            
        except Exception as e:
            result["message"] = f"かまど操作中にエラーが発生しました: {str(e)}"
            result["error"] = "furnace_error"
            
            import traceback
            traceback.print_exc()
            
            self.bot.chat(result["message"])
            return result
        
    async def attack_nearest(self, mob_type, kill=True):
        """
        指定されたタイプのモブに攻撃します。
        
        Args:
            mob_type (str): 攻撃するモブのタイプ（例: "zombie", "skeleton"など）
            kill (bool): モブを倒すまで攻撃し続けるかどうか。デフォルトはTrue
            
        Returns:
            dict: 結果を含む辞書
                - success (bool): 攻撃に成功した場合はTrue、失敗した場合はFalse
                - message (str): 結果メッセージ
                - mob_type (str): 攻撃しようとしたモブのタイプ
                - killed (bool, optional): モブを倒したかどうか
                - error (str, optional): エラーがある場合のエラーコード
            
        Example:
            >>> result = await skills.attack_nearest("zombie")
            >>> if result["success"]:
            >>>     print(f"成功: {result['message']}")
            >>> else:
            >>>     print(f"失敗: {result['message']}")
        """
        result = {
            "success": False,
            "message": "",
            "mob_type": mob_type
        }
        
        # 自己防衛モードを一時停止
        if hasattr(self.bot.modes, 'pause'):
            self.bot.modes.pause('cowardice')
            
            # 水中モブの場合、溺れ防止も無効化
            if mob_type in ['drowned', 'cod', 'salmon', 'tropical_fish', 'squid']:
                self.bot.modes.pause('self_preservation')
                
        # モブを探す
        mob = self._get_nearby_entity_of_type(mob_type, 24)
        
        if not mob:
            result["message"] = f"近くに{mob_type}が見つかりません"
            result["error"] = "mob_not_found"
            self.bot.chat(result["message"])
            return result
            
        # モブを攻撃
        attack_result = await self.attack_entity(mob, kill)
        result.update(attack_result)
        result["mob_type"] = mob_type
        
        return result
        
    async def attack_entity(self, entity, kill=True):
        """
        指定されたエンティティを攻撃します。
        
        Args:
            entity: 攻撃するエンティティ
            kill (bool): エンティティを倒すまで攻撃し続けるかどうか。デフォルトはTrue
            
        Returns:
            dict: 結果を含む辞書
                - success (bool): 攻撃に成功した場合はTrue、失敗した場合はFalse
                - message (str): 結果メッセージ
                - entity_name (str): 攻撃したエンティティの名前
                - killed (bool, optional): エンティティを倒したかどうか
                - error (str, optional): エラーがある場合のエラーコード
            
        Example:
            >>> entity = bot.nearbyEntities[0]
            >>> result = await skills.attack_entity(entity)
        """
        result = {
            "success": False,
            "message": "",
            "entity_name": entity.name if hasattr(entity, 'name') else "不明なエンティティ"
        }
        
        # 最高攻撃力の武器を装備
        await self._equip_highest_attack()
        
        position = entity.position
        
        if not kill:
            # エンティティが遠すぎる場合は近づく
            if self.bot.entity.position.distanceTo(position) > 5:
                move_result = await self.move_to_position(position.x, position.y, position.z)
                if not move_result["success"]:
                    result["message"] = f"{entity.name}への移動に失敗しました: {move_result['message']}"
                    result["error"] = "movement_failed"
                    self.bot.chat(result["message"])
                    return result
                    
            # 一度だけ攻撃
            try:
                await self.bot.attack(entity)
                result["message"] = f"{entity.name}を攻撃しました"
                result["success"] = True
                result["killed"] = False
                self.bot.chat(result["message"])
                return result
            except Exception as e:
                result["message"] = f"{entity.name}の攻撃中にエラーが発生しました: {str(e)}"
                result["error"] = "attack_error"
                self.bot.chat(result["message"])
                return result
        else:
            # エンティティを倒すまで攻撃
            try:
                # PVPモジュールを使用して攻撃
                if hasattr(self.bot, 'pvp'):
                    self.bot.pvp.attack(entity)
                    
                    # エンティティが死ぬまで待機
                    while self._is_entity_nearby(entity, 24):
                        await asyncio.sleep(1)
                    
                    # PVP攻撃を停止
                    self.bot.pvp.stop()
                    
                    result["message"] = f"{entity.name}を倒しました"
                    result["success"] = True
                    result["killed"] = True
                    self.bot.chat(result["message"])
                    
                    # 周囲のアイテムを拾う
                    await self.pickup_nearby_items()
                    return result
                else:
                    # PVPモジュールがない場合は通常攻撃を繰り返す
                    while self._is_entity_nearby(entity, 24):
                        if self.bot.entity.position.distanceTo(entity.position) > 3:
                            await self.move_to_position(entity.position.x, entity.position.y, entity.position.z, 2)
                        
                        try:
                            await self.bot.attack(entity)
                        except:
                            pass
                            
                        await asyncio.sleep(0.5)
                    
                    result["message"] = f"{entity.name}を倒しました"
                    result["success"] = True
                    result["killed"] = True
                    self.bot.chat(result["message"])
                    
                    # 周囲のアイテムを拾う
                    await self.pickup_nearby_items()
                    return result
            except Exception as e:
                result["message"] = f"{entity.name}の攻撃中にエラーが発生しました: {str(e)}"
                result["error"] = "attack_error"
                self.bot.chat(result["message"])
                return result
                
    async def defend_self(self, range=9):
        """
        周囲の敵対的なモブからプレイヤーを守ります。
        近くに敵対的なモブがいる限り、それらを倒し続けます。
        
        Args:
            range (int): モブを探す範囲。デフォルトは9
            
        Returns:
            dict: 結果を含む辞書
                - success (bool): 防衛に成功した場合はTrue、敵がいない場合はFalse
                - message (str): 結果メッセージ
                - enemies_killed (int): 倒した敵の数
                - error (str, optional): エラーがある場合のエラーコード
                
        Example:
            >>> result = await skills.defend_self()
        """
        result = {
            "success": False,
            "message": "",
            "enemies_killed": 0
        }
        
        # 自己防衛と臆病モードを一時停止
        if hasattr(self.bot.modes, 'pause'):
            self.bot.modes.pause('self_defense')
            self.bot.modes.pause('cowardice')
            
        attacked = False
        enemies_killed = 0
        
        # 近くの敵対的なモブを探す
        enemy = self._get_nearest_hostile_entity(range)
        
        while enemy:
            attacked = True
            
            # 最高攻撃力の武器を装備
            await self._equip_highest_attack()
            
            # 敵との距離に応じた行動
            enemy_distance = self.bot.entity.position.distanceTo(enemy.position)
            
            # クリーパーとファントム以外の敵が遠い場合は接近
            if enemy_distance >= 4 and enemy.name != 'creeper' and enemy.name != 'phantom':
                try:
                    if hasattr(self.bot.pathfinder, 'setMovements') and hasattr(self.pathfinder, 'Movements') and hasattr(self.pathfinder.goals, 'GoalFollow'):
                        self.bot.pathfinder.setMovements(self.pathfinder.Movements(self.bot))
                        await self.bot.pathfinder.goto(self.pathfinder.goals.GoalFollow(enemy, 3.5), True)
                except Exception as e:
                    # エンティティが死んでいる場合などはエラーを無視
                    pass
                    
            # 敵が近すぎる場合は距離を取る
            if enemy_distance <= 2:
                try:
                    if hasattr(self.bot.pathfinder, 'setMovements') and hasattr(self.pathfinder, 'Movements') and hasattr(self.pathfinder.goals, 'GoalInvert') and hasattr(self.pathfinder.goals, 'GoalFollow'):
                        self.bot.pathfinder.setMovements(self.pathfinder.Movements(self.bot))
                        inverted_goal = self.pathfinder.goals.GoalInvert(self.pathfinder.goals.GoalFollow(enemy, 2))
                        await self.bot.pathfinder.goto(inverted_goal, True)
                except Exception as e:
                    # エンティティが死んでいる場合などはエラーを無視
                    pass
                    
            # PVPモジュールを使用して攻撃
            if hasattr(self.bot, 'pvp'):
                self.bot.pvp.attack(enemy)
                
            # 少し待機
            await asyncio.sleep(0.5)
            
            # 敵の状態を確認
            previous_enemy = enemy
            enemy = self._get_nearest_hostile_entity(range)
            
            # 前の敵がいなくなった場合はカウント
            if enemy != previous_enemy and not self._is_entity_nearby(previous_enemy, range):
                enemies_killed += 1
                
        # PVP攻撃を停止
        if hasattr(self.bot, 'pvp'):
            self.bot.pvp.stop()
            
        # 結果を設定
        if attacked:
            result["message"] = f"自己防衛に成功しました。{enemies_killed}体の敵を倒しました。"
            result["success"] = True
            result["enemies_killed"] = enemies_killed
        else:
            result["message"] = "近くに敵対的なモブがいません。"
            result["success"] = False
            result["enemies_killed"] = 0
            
        self.bot.chat(result["message"])
        return result
        
    async def pickup_nearby_items(self):
        """
        周囲のドロップアイテムを拾います。
        
        Returns:
            dict: 結果を含む辞書
                - success (bool): アイテムを拾った場合はTrue
                - message (str): 結果メッセージ
                - picked_up (int): 拾ったアイテムの数
                
        Example:
            >>> result = await skills.pickup_nearby_items()
        """
        result = {
            "success": False,
            "message": "",
            "picked_up": 0
        }
        
        distance = 8
        picked_up = 0
        
        # 最も近いアイテムを取得する関数
        def get_nearest_item():
            return self.bot.nearestEntity(
                lambda entity: entity.name == 'item' and 
                self.bot.entity.position.distanceTo(entity.position) < distance
            )
            
        # 最も近いアイテムを取得
        nearest_item = get_nearest_item()
        
        while nearest_item:
            # アイテムに近づく
            if hasattr(self.bot.pathfinder, 'setMovements') and hasattr(self.pathfinder, 'Movements') and hasattr(self.pathfinder.goals, 'GoalFollow'):
                self.bot.pathfinder.setMovements(self.pathfinder.Movements(self.bot))
                await self.bot.pathfinder.goto(self.pathfinder.goals.GoalFollow(nearest_item, 0.8), True)
                
            # 少し待機してアイテムが拾われるのを待つ
            await asyncio.sleep(0.2)
            
            # 前のアイテムを保存
            prev_item = nearest_item
            
            # 新しい最寄りのアイテムを取得
            nearest_item = get_nearest_item()
            
            # 同じアイテムが最も近い場合は終了（拾えなかった）
            if prev_item == nearest_item:
                break
                    
            picked_up += 1
            
        result["picked_up"] = picked_up
        result["success"] = picked_up > 0
        result["message"] = f"{picked_up}個のアイテムを拾いました。"
        self.bot.chat(result["message"])
        return result
        
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
        await self.bot.equip(best_weapon, 'hand')
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
        最も近い敵対的なエンティティを取得します。
        
        Args:
            max_distance (int): 検索する最大距離
            
        Returns:
            Entity: 最も近い敵対的なエンティティ、見つからない場合はNone
        """
        try:
            entities = self._get_nearby_entities(max_distance)
            hostile_entities = []
            
            for entity in entities:
                if self._is_hostile(entity):
                    hostile_entities.append(entity)
                    
            if hostile_entities:
                # プレイヤーからの距離でソート
                hostile_entities.sort(
                    key=lambda e: self.bot.entity.position.distanceTo(e.position)
                )
                return hostile_entities[0]
        except Exception as e:
            print(f"敵対的エンティティ検索エラー: {e}")
            
        return None
        
    def _get_nearby_entities(self, max_distance=24):
        """
        指定した範囲内のすべてのエンティティを取得します。
        
        Args:
            max_distance (int): 検索する最大距離。デフォルトは24
            
        Returns:
            list: 範囲内のエンティティのリスト
        """
        entities = []
        
        # JavaScriptのentitiesプロパティにアクセス
        bot_entities = getattr(self.bot, 'entities', None)
        if bot_entities:
            # JavaScriptオブジェクトの各プロパティを反復処理
            for entity_id in bot_entities:
                entity = bot_entities[entity_id]
                # エンティティが有効で、プレイヤーとの距離が範囲内の場合のみ追加
                if (entity and 
                    hasattr(entity, 'position') and 
                    hasattr(self.bot.entity, 'position') and
                    self.bot.entity.position.distanceTo(entity.position) <= max_distance):
                    entities.append(entity)
                    
        return entities
        
    def _is_entity_nearby(self, entity, max_distance=24):
        """
        特定のエンティティが近くにいるか確認します。
        
        Args:
            entity: 確認するエンティティ
            max_distance (int): 検索する最大距離
            
        Returns:
            bool: エンティティが近くにいる場合はTrue
        """
        try:
            entities = self._get_nearby_entities(max_distance)
            for e in entities:
                if e.id == entity.id:
                    return True
        except:
            pass
            
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
                
        Example:
            >>> result = await skills.break_block_at(100, 64, 100)
            >>> if result["success"]:
            >>>     print(f"成功: {result['message']}")
            >>> else:
            >>>     print(f"失敗: {result['message']}")
        """
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
            return result
            
        result["block_name"] = block.name
        
        # 空気、水、溶岩の場合はスキップ
        if block.name in ['air', 'water', 'lava']:
            result["message"] = f"座標({x}, {y}, {z})は{block.name}なので破壊をスキップします"
            self.bot.chat(result["message"])
            return result
            
        # チートモードの場合は/setblockを使用
        if hasattr(self.bot.modes, 'isOn') and self.bot.modes.isOn('cheat'):
            try:
                # /setblockコマンドで空気に置き換え
                command = f'/setblock {int(x)} {int(y)} {int(z)} air'
                self.bot.chat(command)
                result["message"] = f"/setblockを使用して{block.name}を座標({x}, {y}, {z})で破壊しました"
                result["success"] = True
                self.bot.chat(result["message"])
                return result
            except Exception as e:
                result["message"] = f"チートモードでのブロック破壊中にエラーが発生しました: {str(e)}"
                result["error"] = "cheat_mode_error"
                self.bot.chat(result["message"])
                return result
            
        # ブロックまでの距離を確認
        if self.bot.entity.position.distanceTo(block.position) > 4.5:
            try:
                # パスファインダーの設定
                if hasattr(self.pathfinder, 'Movements') and hasattr(self.pathfinder.goals, 'GoalNear'):
                    movements = self.pathfinder.Movements(self.bot)
                    # 1x1のタワーを作らない、ブロック設置を許可しない
                    movements.canPlaceOn = False
                    movements.allow1by1towers = False
                    self.bot.pathfinder.setMovements(movements)
                    await self.bot.pathfinder.goto(self.pathfinder.goals.GoalNear(x, y, z, 4))
            except Exception as e:
                result["message"] = f"ブロックへの移動中にエラーが発生しました: {str(e)}"
                result["error"] = "movement_error"
                self.bot.chat(result["message"])
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
                    return result
            except Exception as e:
                result["message"] = f"ツール装備中にエラーが発生しました: {str(e)}"
                result["error"] = "tool_equip_error"
                self.bot.chat(result["message"])
                return result
                
        # ブロックを破壊
        try:
            await self.bot.dig(block, True)  # 第2引数をTrueにすることで採掘が完了するまで待機
            result["message"] = f"{block.name}を座標({x:.1f}, {y:.1f}, {z:.1f})で破壊しました"
            result["success"] = True
            self.bot.chat(result["message"])
            return result
        except Exception as e:
            result["message"] = f"ブロック破壊中にエラーが発生しました: {str(e)}"
            result["error"] = "dig_error"
            self.bot.chat(result["message"])
            return result
        
    async def use_door(self, door_pos=None):
        """
        指定された位置にあるドアを使用します。位置が指定されていない場合、最も近いドアを使用します。
        
        Args:
            door_pos (Vec3, optional): 使用するドアの位置。Noneの場合は最も近いドアを使用します。
            
        Returns:
            dict: 結果を含む辞書
                - success (bool): ドアの使用に成功した場合はTrue、失敗した場合はFalse
                - message (str): 結果メッセージ
                - position (dict, optional): 使用したドアの位置 {x, y, z}（成功時のみ）
                
        Example:
            >>> result = await skills.use_door()
            >>> if result["success"]:
            >>>     print(f"成功: {result['message']}")
            >>> else:
            >>>     print(f"失敗: {result['message']}")
        """
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
                    'cherry_door', 'bamboo_door', 'crimson_door', 'warped_door'
                ]
                
                for door_type in door_types:
                    door_block = self.get_nearest_block(door_type, 16)
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
                return result
                
            # 結果にドアの位置を記録
            result["position"] = {
                "x": door_pos.x,
                "y": door_pos.y,
                "z": door_pos.z
            }
            
            # ドアに近づく
            if hasattr(self.pathfinder.goals, 'GoalNear'):
                self.bot.pathfinder.setGoal(self.pathfinder.goals.GoalNear(
                    door_pos.x, door_pos.y, door_pos.z, 1
                ))
                
                # 移動に少し時間を与える
                await asyncio.sleep(1)
                
                # 移動が完了するまで待機
                while self.bot.pathfinder.isMoving():
                    await asyncio.sleep(0.1)
                    
            # ドアブロックを取得
            door_block = self.bot.blockAt(door_pos)
            
            # ドアを見る
            await self.bot.lookAt(door_pos)
            
            # ドアが閉まっている場合は開ける
            if hasattr(door_block, '_properties') and not door_block._properties.get('open', False):
                await self.bot.activateBlock(door_block)
                
            # 前進
            self.bot.setControlState("forward", True)
            await asyncio.sleep(0.6)
            self.bot.setControlState("forward", False)
            
            # ドアを閉じる
            await self.bot.activateBlock(door_block)
            
            result["success"] = True
            result["message"] = f"座標({door_pos.x}, {door_pos.y}, {door_pos.z})のドアを使用しました。"
            self.bot.chat(result["message"])
            return result
            
        except Exception as e:
            result["message"] = f"ドアの使用中に予期せぬエラーが発生しました: {str(e)}"
            self.bot.chat(result["message"])
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
                
        Example:
            >>> # 地面を耕して小麦の種を植える
            >>> position = bot.entity.position
            >>> result = await skills.till_and_sow(position.x, position.y - 1, position.z, "wheat_seeds")
            >>> if result["success"]:
            >>>     print(f"成功: {result['message']}")
            >>> else:
            >>>     print(f"失敗: {result['message']}")
        """
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
            
            # チートモードの場合
            if hasattr(self.bot.modes, 'isOn') and self.bot.modes.isOn('cheat'):
                # 種の名前から「_seed」や「_seeds」を取り除く
                if seed_type:
                    to_remove = ['_seed', '_seeds']
                    for remove in to_remove:
                        if seed_type.endswith(remove):
                            seed_type = seed_type.replace(remove, '')
                    
                    # 農地と種を設置
                    await self.place_block('farmland', x, y, z)
                    await self.place_block(seed_type, x, y+1, z)
                    
                    result["success"] = True
                    result["tilled"] = True
                    result["planted"] = True
                    result["seed_type"] = seed_type
                    result["message"] = f"チートモードで座標({x}, {y}, {z})に農地と{seed_type}を設置しました。"
                    self.bot.chat(result["message"])
                    return result
            
            # 対象のブロックが耕せるかチェック
            if block.name not in ['grass_block', 'dirt', 'farmland']:
                result["message"] = f"{block.name}は耕せません。土または草ブロックである必要があります。"
                self.bot.chat(result["message"])
                return result
                
            # 上のブロックがあるかチェック
            above = self.bot.blockAt(Vec3(x, y+1, z))
            if above.name != 'air':
                result["message"] = f"ブロックの上に{above.name}があるため耕せません。"
                self.bot.chat(result["message"])
                return result
                
            # ブロックまでの距離が遠い場合は近づく
            if self.bot.entity.position.distanceTo(block.position) > 4.5:
                pos = block.position
                if hasattr(self.bot.pathfinder, 'setMovements') and hasattr(self.pathfinder, 'Movements'):
                    self.bot.pathfinder.setMovements(self.pathfinder.Movements(self.bot))
                    await self.bot.pathfinder.goto(self.pathfinder.goals.GoalNear(pos.x, pos.y, pos.z, 4))
            
            # 既に農地でない場合は耕す
            if block.name != 'farmland':
                # クワを探す
                hoe = None
                for item in self.bot.inventory.items():
                    if 'hoe' in item.name:
                        hoe = item
                        break
                        
                if not hoe:
                    result["message"] = "クワを持っていないため耕せません。"
                    self.bot.chat(result["message"])
                    return result
                    
                # クワを装備
                await self.bot.equip(hoe, 'hand')
                
                # ブロックを耕す
                await self.bot.activateBlock(block)
                
                result["tilled"] = True
                self.bot.chat(f"座標({x}, {y}, {z})を耕しました。")
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
                    
                    # 耕せたならある程度は成功
                    if result["tilled"]:
                        result["success"] = True
                    return result
                
                # 種を装備
                await self.bot.equip(seeds, 'hand')
                
                # 種を植える（農地の上に設置）
                # 底面に対して設置するので、Vec3(0, -1, 0)を使用
                await self.bot.placeBlock(block, Vec3(0, -1, 0))
                
                result["planted"] = True
                result["seed_type"] = seed_type
                self.bot.chat(f"座標({x}, {y}, {z})に{seed_type}を植えました。")
            
            result["success"] = True
            
            if seed_type and result["planted"]:
                result["message"] = f"座標({x}, {y}, {z})を耕し、{seed_type}を植えました。"
            else:
                result["message"] = f"座標({x}, {y}, {z})を耕しました。"
                
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
        """
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