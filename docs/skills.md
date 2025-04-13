# Skillsクラス関数一覧

このドキュメントでは、`discovery/skill/skills.py`ファイル内の`Skills`クラスが提供する関数とその機能について説明します。

## 目次

1. [初期化](#初期化)
2. [インベントリ管理](#インベントリ管理)
3. [ブロック操作](#ブロック操作)
4. [移動](#移動)
5. [クラフト・製作](#クラフト製作)
6. [戦闘](#戦闘)
7. [エンティティ操作](#エンティティ操作)
8. [農業](#農業)
9. [ユーティリティ関数](#ユーティリティ関数)

## 初期化

### `__init__(self, discovery)`
Discoveryインスタンスを受け取り、そのプロパティを初期化します。

引数:
- `discovery`: Discoveryクラスのインスタンス

## インベントリ管理

### `get_inventory_counts(self)`
ボットのインベントリ内の各アイテムの数を辞書形式で返します。

戻り値:
- 辞書: キーがアイテム名、値がその数量

### `equip(self, item_name)`
指定されたアイテムを適切な装備スロットに装備します（道具や防具など）。

引数:
- `item_name`: 装備するアイテムまたはブロックの名前

戻り値:
- 辞書: 操作結果

### `discard(self, item_name, num=-1)`
指定されたアイテムを捨てます。

引数:
- `item_name`: 捨てるアイテムまたはブロックの名前
- `num`: 捨てるアイテムの数（デフォルトは-1で、すべて捨てる）

戻り値:
- 辞書: 操作結果

### `put_in_chest(self, item_name, num=-1)`
指定されたアイテムを最も近いチェストに入れます。

引数:
- `item_name`: チェストに入れるアイテムまたはブロックの名前
- `num`: チェストに入れるアイテムの数（デフォルトは-1で、すべて入れる）

戻り値:
- 辞書: 操作結果

### `take_from_chest(self, item_name, num=-1)`
指定されたアイテムを最も近いチェストから取り出します。

引数:
- `item_name`: チェストから取り出すアイテムまたはブロックの名前
- `num`: チェストから取り出すアイテムの数（デフォルトは-1で、すべて取り出す）

戻り値:
- 辞書: 操作結果

### `view_chest(self)`
最も近いチェストの中身を表示します。

戻り値:
- 辞書: チェストの内容を含む操作結果

### `consume(self, item_name="")`
指定されたアイテムを1つ食べる/飲みます。

引数:
- `item_name`: 食べる/飲むアイテムの名前（デフォルトは空で、手に持っているアイテムを消費）

戻り値:
- 辞書: 操作結果

### `pickup_nearby_items(self)`
周囲のドロップアイテムを拾います。

戻り値:
- 辞書: 操作結果

## ブロック操作

### `get_nearest_block(self, block_type, max_distance=64)`
指定されたブロックタイプの最も近いブロックを返します。

引数:
- `block_type`: 探すブロックタイプ
- `max_distance`: 探索する最大距離

戻り値:
- Block: 最も近いブロック、見つからない場合はNone

### `get_nearest_free_space(self, size=1, distance=8, y_offset=0)`
指定されたサイズの空きスペース（上部が空気で下部が固体ブロック）を見つけます。

引数:
- `size`: 探す空きスペースの（size × size）サイズ
- `distance`: 探索する最大距離
- `y_offset`: 見つかった空きスペースに適用するY座標オフセット

戻り値:
- Vec3: 見つかった空きスペースの南西角の座標

### `place_block(self, block_type, x, y, z, place_on='bottom', dont_cheat=False)`
指定された座標にブロックを設置します。

引数:
- `block_type`: 設置するブロックタイプ
- `x`, `y`, `z`: 設置する座標
- `place_on`: 優先的に設置する面の方向
- `dont_cheat`: チートモードでも通常の方法でブロックを設置するかどうか

戻り値:
- 辞書: 操作結果

### `break_block_at(self, x, y, z)`
指定された座標のブロックを破壊します。

引数:
- `x`, `y`, `z`: 破壊するブロックの座標

戻り値:
- 辞書: 操作結果

### `collect_block(self, block_type, num=1, exclude=None)`
指定されたタイプのブロックを収集します。

引数:
- `block_type`: 収集するブロックのタイプ
- `num`: 収集するブロックの数
- `exclude`: 除外するブロックの位置のリスト

戻り値:
- 辞書: 操作結果

### `get_all_registry_blocks(self)`
レジストリに登録されているすべてのブロック名を取得します。

戻り値:
- リスト: ブロック名のリスト

### `auto_light(self)`
周りに松明がない場合、インベントリに松明がある場合、現在位置が空気である場合に松明を設置します。

戻り値:
- bool: 松明を設置した場合はTrue

### `should_place_torch(self)`
松明を設置すべきかどうかを判断します。

戻り値:
- bool: 松明を設置すべき場合はTrue

### `use_door(self, door_pos=None)`
指定された位置にあるドア・フェンスゲートを使用します。

引数:
- `door_pos`: 使用するドアの位置（Noneの場合は最も近いドアを使用）

戻り値:
- 辞書: 操作結果

## 移動

### `move_to_position(self, x, y, z, min_distance=2, canDig=True, dontcreateflow=True, dontMineUnderFaillingBlock=True)`
指定された位置に移動します。

引数:
- `x`, `y`, `z`: 移動先の座標
- `min_distance`: 目標位置からの最小距離
- `canDig`: ブロックを掘るかどうか
- `dontcreateflow`: 液体ブロックに接触するブロックを掘らないかどうか
- `dontMineUnderFaillingBlock`: 落下ブロックの下で掘るのを許可するか

戻り値:
- 辞書: 操作結果

### `go_to_nearest_block(self, block_type, min_distance=2, range=64)`
指定されたタイプの最も近いブロックまで移動します。

引数:
- `block_type`: 移動先のブロックタイプ
- `min_distance`: ブロックから保つ距離
- `range`: ブロックを探す最大範囲

戻り値:
- 辞書: 操作結果

### `go_to_nearest_entity(self, entity_type, min_distance=2, range=64)`
指定されたタイプの最も近いエンティティまで移動します。

引数:
- `entity_type`: 移動先のエンティティタイプ
- `min_distance`: 移動後、エンティティと保つ距離
- `range`: エンティティを探す最大範囲

戻り値:
- 辞書: 操作結果

### `go_to_bed(self)`
最も近いベッドで寝ます。

戻り値:
- 辞書: 操作結果

### `move_away(self, distance)`
現在の位置から任意の方向に指定した距離だけ離れます。

引数:
- `distance`: 移動する距離

戻り値:
- 辞書: 操作結果

### `avoid_enemies(self, distance=16)`
周囲の敵対的なエンティティから逃げます。

引数:
- `distance`: 逃げる最大距離

戻り値:
- 辞書: 操作結果

## クラフト・製作

### `craft_recipe(self, item_name, num=1)`
指定されたアイテムをレシピから作成します。

引数:
- `item_name`: 作成するアイテムの名前
- `num`: 作成する数量

戻り値:
- 辞書: 操作結果

### `smelt_item(self, item_name, num=1)`
かまどを使用してアイテムを精錬します。

引数:
- `item_name`: 精錬するアイテム名
- `num`: 精錬するアイテムの数

戻り値:
- 辞書: 操作結果

### `clear_nearest_furnace(self)`
最も近いかまどを見つけ、中のアイテムをすべて取り出します。

戻り値:
- 辞書: 操作結果

### `get_item_crafting_recipes(self, item_name)`
アイテムのクラフトレシピを取得します。

引数:
- `item_name`: アイテム名

戻り値:
- リスト: レシピのリスト。各レシピは[材料辞書, 結果辞書]の形式

## 戦闘

### `attack_nearest(self, mob_type, kill=True, pickup_item=True)`
指定したタイプのモブを攻撃します。

引数:
- `mob_type`: 攻撃するモブのタイプ
- `kill`: モブが死ぬまで攻撃し続けるかどうか
- `pickup_item`: モブが死んだ時にドロップアイテムを拾うかどうか

戻り値:
- 辞書: 操作結果

### `attack_entity(self, entity, kill=True, pickup_item=True)`
指定したエンティティを攻撃します。

引数:
- `entity`: 攻撃するエンティティ
- `kill`: エンティティが死ぬまで攻撃し続けるかどうか
- `pickup_item`: エンティティが死んだ時にドロップアイテムを拾うかどうか

戻り値:
- 辞書: 操作結果

### `defend_self(self, range=9)`
周囲の敵対的なモブから自身を守ります。

引数:
- `range`: モブを探す範囲

戻り値:
- 辞書: 操作結果

## 農業

### `till_and_sow(self, x, y, z, seed_type=None)`
指定された座標の地面を耕し、指定された種を植えます。

引数:
- `x`, `y`, `z`: 耕す地点の座標
- `seed_type`: 植える種の種類

戻り値:
- 辞書: 操作結果

## ユーティリティ関数

### `_make_item(self, item_name, count=1)`
指定された名前とカウントでアイテムオブジェクトを作成します。

### `_is_smeltable(self, item_name)`
アイテムが精錬可能かどうかを判断します。

### `_get_smelting_fuel(self)`
インベントリから精錬に使用できる燃料を探します。

### `_get_item_name(self, item_id)`
アイテムIDから対応するアイテム名を取得します。

### `_get_item_id(self, item_name)`
アイテム名からアイテムIDを取得します。

### `_get_item_id_from_entity(self, entity)`
エンティティからアイテムIDを取得します。

### `_equip_highest_attack(self)`
最も攻撃力の高い武器を装備します。

### `_get_nearby_entity_of_type(self, entity_type, max_distance=24)`
指定された種類の最も近いエンティティを取得します。

### `_get_nearest_hostile_entity(self, max_distance=24)`
指定した距離以内で最も近い敵対的なエンティティを取得します。

### `_get_nearby_entities(self, max_distance=24)`
指定した距離以内にある全てのエンティティを取得し、距離順にソートして返します。

### `_is_entity_nearby(self, entity, max_distance=24)`
特定のエンティティが近くにいるか確認します。

### `_is_hostile(self, entity)`
エンティティが敵対的かどうかを判断します。 