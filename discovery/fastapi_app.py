from fastapi import FastAPI, HTTPException, Depends, Query, Path, BackgroundTasks
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import List, Optional, Dict, Any
import uvicorn
import asyncio
from discovery import Discovery
from contextlib import asynccontextmanager
import math # math.fabs を使うためにインポート
from javascript import require # Vec3 を使う可能性のため (skills.pyの依存関係)

# Discoveryインスタンスの初期化
discovery = Discovery()
skills = None

# lifespanコンテキストマネージャを定義
@asynccontextmanager
async def lifespan(app: FastAPI):
    # アプリケーション起動時の処理
    global skills
    discovery.bot_join()
    skills = discovery.create_skills()
    # サーバー接続確認（非同期で実行）
    asyncio.create_task(check_server_connection())
    
    yield
    
    # アプリケーション終了時の処理
    # 必要に応じてボットの切断処理などを実装
    pass

# FastAPIインスタンスを作成
app = FastAPI(
    title="MineCraft Bot API",
    description="Minecraft Bot API は、MineFlayer を使用したマインクラフトボットの制御APIです。",
    version="1.0.0",
    lifespan=lifespan
)

# CORSミドルウェアの設定
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# サーバー接続確認
async def check_server_connection():
    server_active = await discovery.check_server_active(timeout=15)
    if not server_active:
        raise HTTPException(status_code=503, detail="マインクラフトサーバーに接続できません。ポートを確認してください")

# ルートエンドポイント
@app.get("/")
async def root():
    return {"message": "MineCraft Bot API is running..."}

# サーバー情報の取得
@app.get("/server/info", tags=["server"])
async def get_server_info():
    return discovery.get_server_info()

# ボット接続状態の確認 -> ボット周辺ブロックの領域分類に変更
@app.get("/bot/status", tags=["bot"], summary="ボットの状態と周辺情報（バイオーム、時間、体力、空腹度、エンティティ、インベントリ、ブロック分類）を取得")
async def get_bot_status():
    # --- ボットの基本情報を取得 ---
    try:
        bot_entity = discovery.bot.entity
        bot_pos_raw = bot_entity.position # Y座標はエンティティ基準
        bot_health = discovery.bot.health
        bot_food = discovery.bot.food
        bot_time = discovery.bot.time.timeOfDay

        # ボットがいるブロックとバイオームを取得
        center_block = discovery.bot.blockAt(bot_pos_raw)
        bottom_block = discovery.bot.blockAt(bot_pos_raw.offset(0, -1, 0))
        bot_pos = center_block.position.offset(0, 1, 0)
        bot_biome_name = bottom_block.biome.name

        bot_x = bot_pos.x
        bot_z = bot_pos.z

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"ボットの基本情報の取得に失敗しました: {e}")

    # --- 周囲のブロックを取得 & 分類 ---
    try:
        blocks = await skills.get_surrounding_blocks(
            position=bot_pos, # スキルの引数名に合わせる
            x_distance=3,
            y_distance=2,
            z_distance=3
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"周辺ブロック情報の取得に失敗しました: {e}")

    # ブロック名をグループごとに一時的に格納
    temp_grouped_block_names = {"group1": [], "group2": [], "group3": [], "group4": [], "group0": []}

    if blocks:
        for block in blocks:
            block_pos_dict = block.get('position')
            block_name = block.get('name')
            if not isinstance(block_pos_dict, dict) or block_name is None:
                continue

            block_x = block_pos_dict.get('x')
            block_z = block_pos_dict.get('z')
            if not isinstance(block_x, (int, float)) or not isinstance(block_z, (int, float)):
                continue

            dx = block_x - bot_x
            dz = block_z - bot_z

            if math.fabs(dx) < 1e-6 and math.fabs(dz) < 1e-6:
                 temp_grouped_block_names["group0"].append(block_name)
            elif dz > 1e-6 and math.fabs(dx) <= dz + 1e-6:
                temp_grouped_block_names["group1"].append(block_name)
            elif dx > 1e-6 and math.fabs(dz) <= dx + 1e-6:
                temp_grouped_block_names["group2"].append(block_name)
            elif dz < -1e-6 and math.fabs(dx) <= math.fabs(dz) + 1e-6:
                temp_grouped_block_names["group3"].append(block_name)
            elif dx < -1e-6 and math.fabs(dz) <= math.fabs(dx) + 1e-6:
                temp_grouped_block_names["group4"].append(block_name)

    # ブロック分類結果（重複除去とソート）
    classified_blocks = {
        "front_blocks": sorted(list(set(temp_grouped_block_names["group1"]))),
        "right_blocks": sorted(list(set(temp_grouped_block_names["group2"]))),
        "back_blocks": sorted(list(set(temp_grouped_block_names["group3"]))),
        "left_blocks": sorted(list(set(temp_grouped_block_names["group4"]))),
        "center_blocks": sorted(list(set(temp_grouped_block_names["group0"])))
    }

    # --- 近くのエンティティ情報を取得 ---
    nearby_entities_info = []
    try:
        # _get_nearby_entities は同期メソッドの可能性あり
        nearby_entities_raw = skills._get_nearby_entities(max_distance=16) # 範囲は適宜調整
        if nearby_entities_raw:
            for entity in nearby_entities_raw:
                # 有効なエンティティ情報のみ抽出
                if hasattr(entity, 'name') and hasattr(entity, 'position') and entity.position:
                    nearby_entities_info.append({
                        "name": entity.name,
                        "position": {
                            "x": round(entity.position.x, 1), # 小数点以下第一位で四捨五入
                            "y": round(entity.position.y, 1), # 小数点以下第一位で四捨五入
                            "z": round(entity.position.z, 1)  # 小数点以下第一位で四捨五入
                        }
                    })
    except Exception as e:
        print(f"Warning: Failed to get nearby entities ({e})")
        # エラーが発生しても処理は続行

    # --- インベントリ情報を取得 ---
    inventory_info = {}
    try:
        # get_inventory_counts は同期メソッド
        inventory_info = skills.get_inventory_counts()
    except Exception as e:
        print(f"Warning: Failed to get inventory counts ({e})")
        # エラーが発生しても処理は続行

    # --- 最終的なレスポンスを作成 ---
    final_result = {
        "biome": bot_biome_name,
        "time_of_day": bot_time,
        "health": bot_health,
        "hunger": bot_food,
        "nearby_entities": nearby_entities_info,
        "inventory": inventory_info,
        **classified_blocks # ブロック分類結果を展開して結合
    }

    return final_result

@app.post("/bot/teleport", tags=["bot"])
async def teleport_bot(position_x: float, position_y: float, position_z: float):
    discovery.bot.chat(f"/tp bot {position_x} {position_y} {position_z}")
    return {"message": "ボットを転送しました"}

# サーバー起動用コード
if __name__ == "__main__":
    uvicorn.run("fastapi_app:app", host="0.0.0.0", port=8000, reload=True) 