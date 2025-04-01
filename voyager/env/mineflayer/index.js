/**
 * Minecraftボット制御サーバー
 * 
 * このファイルは、MinecraftボットのHTTP APIサーバーを実装します。
 * Express.jsを使用してRESTful APIを提供し、以下の機能を実装しています：
 * - ボットの起動と初期化 (/start)
 * - ボットのアクション実行 (/step)
 * - ボットの停止 (/stop)
 * - ゲームの一時停止 (/pause)
 */

// 基本的なNode.jsモジュール
const fs = require("fs");                    // ファイルシステム操作用
const express = require("express");          // Webサーバーフレームワーク
const bodyParser = require("body-parser");   // リクエストボディ解析用
const mineflayer = require("mineflayer");    // Minecraftボット制御用

// カスタムモジュールのインポート
const skills = require("./lib/skillLoader");                     // ボットのスキル管理
const { initCounter, getNextTime } = require("./lib/utils");     // ユーティリティ関数
const obs = require("./lib/observation/base");                   // 基本観察機能
const OnChat = require("./lib/observation/onChat");             // チャット監視
const OnError = require("./lib/observation/onError");           // エラー監視
const { Voxels, BlockRecords } = require("./lib/observation/voxels");  // ブロック観察
const Status = require("./lib/observation/status");             // 状態監視
const Inventory = require("./lib/observation/inventory");       // インベントリ管理
const OnSave = require("./lib/observation/onSave");            // セーブ機能
const Chests = require("./lib/observation/chests");            // チェスト管理
const { plugin: tool } = require("mineflayer-tool");           // ツール操作

// グローバルなボットインスタンス
let bot = null;

// Expressアプリケーションの初期化
const app = express();

/**
 * ミドルウェアの設定
 * - JSONリクエストの最大サイズを50MBに制限
 * - URL encodedリクエストの最大サイズも50MBに制限
 */
app.use(bodyParser.json({ limit: "50mb" }));
app.use(bodyParser.urlencoded({ limit: "50mb", extended: false }));

/**
 * ボット起動エンドポイント
 * 新しいボットインスタンスを作成し、初期設定を行います
 * 
 * リクエストパラメータ:
 * - host: Minecraftサーバーのホスト名（デフォルト: localhost）
 * - port: サーバーポート
 * - waitTicks: ティック待機時間
 * - reset: リセットモード（"hard"の場合、完全リセット）
 * - position: 初期位置
 * - spread: プレイヤー拡散の有無
 */
app.post("/start", (req, res) => {
    // 既存のボットがある場合は切断
    if (bot) onDisconnect("Restarting bot");
    bot = null;
    console.log(req.body);

    // 新しいボットインスタンスの作成
    bot = mineflayer.createBot({
        host: req.body.host || "localhost", // Minecraftサーバーのホスト
        port: req.body.port,               // Minecraftサーバーのポート
        username: "bot",                   // ボットのユーザー名
        disableChatSigning: true,          // チャット署名を無効化
        checkTimeoutInterval: 60 * 60 * 1000, // 1時間のタイムアウト
    });

    // エラーイベントの初期設定
    bot.once("error", onConnectionFailed);

    /**
     * ボットの状態変数の初期化
     * - waitTicks: アクション間の待機時間
     * - globalTickCounter: 全体的なティックカウンター
     * - stuckTickCounter: スタック状態の検出用カウンター
     * - stuckPosList: スタック位置の履歴
     * - iron_pickaxe: 鉄のツルハシの所持状態
     */
    bot.waitTicks = req.body.waitTicks;
    bot.globalTickCounter = 0;
    bot.stuckTickCounter = 0;
    bot.stuckPosList = [];
    bot.iron_pickaxe = false;

    // キック（強制切断）イベントの監視
    bot.on("kicked", onDisconnect);

    /**
     * マウントイベントの処理
     * 物理的なティック処理が停止するのを防ぐため、
     * 自動的に降下します
     */
    bot.on("mount", () => {
        bot.dismount();
    });

    /**
     * スポーン時の初期化処理
     * - インベントリのリセット（ハードリセット時）
     * - 位置の設定
     * - プラグインの読み込み
     * - ゲームルールの設定
     */
    bot.once("spawn", async () => {
        bot.removeListener("error", onConnectionFailed);
        let itemTicks = 1;
        if (req.body.reset === "hard") {
            bot.chat("/clear @s");
            bot.chat("/kill @s");
            const inventory = req.body.inventory ? req.body.inventory : {};
            const equipment = req.body.equipment
                ? req.body.equipment
                : [null, null, null, null, null, null];
            for (let key in inventory) {
                bot.chat(`/give @s minecraft:${key} ${inventory[key]}`);
                itemTicks += 1;
            }
            const equipmentNames = [
                "armor.head",
                "armor.chest",
                "armor.legs",
                "armor.feet",
                "weapon.mainhand",
                "weapon.offhand",
            ];
            for (let i = 0; i < 6; i++) {
                if (i === 4) continue;
                if (equipment[i]) {
                    bot.chat(
                        `/item replace entity @s ${equipmentNames[i]} with minecraft:${equipment[i]}`
                    );
                    itemTicks += 1;
                }
            }
        }

        if (req.body.position) {
            bot.chat(
                `/tp @s ${req.body.position.x} ${req.body.position.y} ${req.body.position.z}`
            );
        }

        // 鉄のツルハシの所持確認
        if (bot.inventory.items().find((item) => item.name === "iron_pickaxe")) {
            bot.iron_pickaxe = true;
        }

        // 必要なプラグインの読み込み
        const { pathfinder } = require("mineflayer-pathfinder");    // 経路探索
        const tool = require("mineflayer-tool").plugin;             // ツール操作
        const collectBlock = require("mineflayer-collectblock").plugin;  // ブロック収集
        const pvp = require("mineflayer-pvp").plugin;               // PvP機能
        const minecraftHawkEye = require("minecrafthawkeye").default;   // 視覚支援
        bot.loadPlugin(pathfinder);
        bot.loadPlugin(tool);
        bot.loadPlugin(collectBlock);
        bot.loadPlugin(pvp);
        bot.loadPlugin(minecraftHawkEye);

        // 観察機能の注入
        obs.inject(bot, [
            OnChat,      // チャット監視
            OnError,     // エラー監視
            Voxels,      // ブロック観察
            Status,      // 状態監視
            Inventory,   // インベントリ管理
            OnSave,      // セーブ機能
            Chests,      // チェスト管理
            BlockRecords // ブロック記録
        ]);
        skills.inject(bot);  // スキルの注入

        /**
         * プレイヤーの拡散配置
         * /spreadplayers コマンドを使用して、プレイヤーをランダムな位置に配置
         * - 現在位置を中心に、半径300ブロック以内
         * - 高度80ブロック以下の地点に配置
         * - チーム分けは無効
         */
        if (req.body.spread) {
            bot.chat(`/spreadplayers ~ ~ 0 300 under 80 false @s`);
            await bot.waitForTicks(bot.waitTicks);
        }

        await bot.waitForTicks(bot.waitTicks * itemTicks);
        res.json(bot.observe());

        initCounter(bot);

        /**
         * ゲームルールの設定
         * - keepInventory: プレイヤーが死亡時にインベントリとXPを保持
         * - doDaylightCycle: 昼夜サイクルの進行を停止
         */
        bot.chat("/gamerule keepInventory true");    // 死亡時のアイテム保持を有効化
        bot.chat("/gamerule doDaylightCycle false"); // 昼夜サイクルを停止
    });

    /**
     * 接続失敗時のエラーハンドリング
     * エラーをログに記録し、クライアントにエラーレスポンスを返します
     * @param {Error} e - 発生したエラー
     */
    function onConnectionFailed(e) {
        console.log(e);
        bot = null;
        res.status(400).json({ error: e });
    }

    /**
     * ボット切断時の処理
     * - ビューワーの終了
     * - ボットの終了
     * - 状態のクリーンアップ
     * @param {string} message - 切断理由のメッセージ
     */
    function onDisconnect(message) {
        if (bot.viewer) {
            bot.viewer.close();
        }
        bot.end();
        console.log(message);
        bot = null;
    }
});

/**
 * ボットのアクション実行エンドポイント
 * 指定されたコードを実行し、結果を返します
 * 
 * リクエストパラメータ:
 * - code: 実行するJavaScriptコード
 * - programs: 事前に定義された補助プログラム
 * 
 * レスポンス:
 * - 成功時: ボットの観察結果
 * - 失敗時: エラーメッセージ
 */
app.post("/step", async (req, res) => {
    // エラーハンドリングの設定
    let response_sent = false;

    /**
     * 未捕捉エラーのハンドリング
     * @param {Error} err - 発生したエラー
     */
    function otherError(err) {
        console.log("Uncaught Error");
        bot.emit("error", handleError(err));
        bot.waitForTicks(bot.waitTicks).then(() => {
            if (!response_sent) {
                response_sent = true;
                res.json(bot.observe());
            }
        });
    }

    process.on("uncaughtException", otherError);

    // Minecraft関連データの初期化とカスタマイズ
    const mcData = require("minecraft-data")(bot.version);
    
    // アイテム名の別名マッピング（互換性のため）
    mcData.itemsByName["leather_cap"] = mcData.itemsByName["leather_helmet"];
    mcData.itemsByName["leather_tunic"] = mcData.itemsByName["leather_chestplate"];
    mcData.itemsByName["leather_pants"] = mcData.itemsByName["leather_leggings"];
    mcData.itemsByName["leather_boots"] = mcData.itemsByName["leather_boots"];
    mcData.itemsByName["lapis_lazuli_ore"] = mcData.itemsByName["lapis_ore"];
    mcData.blocksByName["lapis_lazuli_ore"] = mcData.blocksByName["lapis_ore"];

    // パスファインダー関連のモジュールインポート
    const {
        Movements,
        goals: {
            Goal,
            GoalBlock,
            GoalNear,
            GoalXZ,
            GoalNearXZ,
            GoalY,
            GoalGetToBlock,
            GoalLookAtBlock,
            GoalBreakBlock,
            GoalCompositeAny,
            GoalCompositeAll,
            GoalInvert,
            GoalFollow,
            GoalPlaceBlock,
        },
        pathfinder,
        Move,
        ComputedPath,
        PartiallyComputedPath,
        XZCoordinates,
        XYZCoordinates,
        SafeBlock,
        GoalPlaceBlockOptions,
    } = require("mineflayer-pathfinder");
    const { Vec3 } = require("vec3");

    // パスファインダーの初期設定
    const movements = new Movements(bot, mcData);
    bot.pathfinder.setMovements(movements);

    // カウンターの初期化
    bot.globalTickCounter = 0;
    bot.stuckTickCounter = 0;
    bot.stuckPosList = [];

    /**
     * 物理的なティックごとの処理
     * - グローバルカウンターの更新
     * - スタック状態の検出と処理
     */
    function onTick() {
        bot.globalTickCounter++;
        if (bot.pathfinder.isMoving()) {
            bot.stuckTickCounter++;
            if (bot.stuckTickCounter >= 100) {
                onStuck(1.5);
                bot.stuckTickCounter = 0;
            }
        }
    }

    bot.on("physicTick", onTick);

    // 各種失敗カウンターの初期化
    let _craftItemFailCount = 0;    // クラフト失敗回数
    let _killMobFailCount = 0;      // モブ討伐失敗回数
    let _mineBlockFailCount = 0;    // ブロック採掘失敗回数
    let _placeItemFailCount = 0;    // アイテム設置失敗回数
    let _smeltItemFailCount = 0;    // 精錬失敗回数

    // コードの実行準備
    const code = req.body.code;
    const programs = req.body.programs;
    bot.cumulativeObs = [];
    await bot.waitForTicks(bot.waitTicks);
    
    // コードの実行と結果の処理
    const r = await evaluateCode(code, programs);
    process.off("uncaughtException", otherError);
    if (r !== "success") {
        bot.emit("error", handleError(r));
    }
    
    // アイテムの返却処理
    await returnItems();
    
    // 最終メッセージの待機と応答送信
    await bot.waitForTicks(bot.waitTicks);
    if (!response_sent) {
        response_sent = true;
        res.json(bot.observe());
    }
    bot.removeListener("physicTick", onTick);

    /**
     * コード評価関数
     * 提供されたコードとプログラムを実行します
     * 
     * @param {string} code - 実行するコード
     * @param {string} programs - 補助プログラム
     * @returns {string} 実行結果（"success"または エラーオブジェクト）
     */
    async function evaluateCode(code, programs) {
        try {
            await eval("(async () => {" + programs + "\n" + code + "})()");
            return "success";
        } catch (err) {
            return err;
        }
    }

    /**
     * スタック状態の検出と処理
     * 一定時間同じ場所に留まっている場合、
     * ボットの位置を調整します
     * 
     * @param {number} posThreshold - 位置の閾値（ブロック単位）
     */
    function onStuck(posThreshold) {
        const currentPos = bot.entity.position;
        bot.stuckPosList.push(currentPos);

        // 履歴が5件たまったら判定
        if (bot.stuckPosList.length === 5) {
            const oldestPos = bot.stuckPosList[0];
            const posDifference = currentPos.distanceTo(oldestPos);

            if (posDifference < posThreshold) {
                teleportBot();
            }

            // 最古の位置を削除
            bot.stuckPosList.shift();
        }
    }

    /**
     * ボットのテレポート処理
     * スタック状態から脱出するため、
     * 近くの安全な場所にテレポートします
     */
    function teleportBot() {
        const blocks = bot.findBlocks({
            matching: (block) => {
                return block.type === 0;  // 空気ブロックを探す
            },
            maxDistance: 1,
            count: 27,
        });

        if (blocks) {
            const randomIndex = Math.floor(Math.random() * blocks.length);
            const block = blocks[randomIndex];
            bot.chat(`/tp @s ${block.x} ${block.y} ${block.z}`);
        } else {
            // 安全なブロックが見つからない場合は上方向に移動
            bot.chat("/tp @s ~ ~1.25 ~");
        }
    }

    /**
     * アイテムの返却処理
     * セッション終了時に以下のアイテムを返却します：
     * - クラフティングテーブル
     * - かまど
     * - チェスト（インベントリが32以上の場合）
     * - 鉄のツルハシ（所持していた場合）
     */
    function returnItems() {
        /**
         * Minecraft: /gamerule doTileDrops false
         * - ブロックを破壊した時にアイテムがドロップしないようにするゲームルール
         * - 主にブロックの整理や環境のクリーンアップに使用
         * Mineflayer: bot.chat()でMinecraftコマンドを実行
         */
        bot.chat("/gamerule doTileDrops false");
        
        // クラフティングテーブルの処理
        const crafting_table = bot.findBlock({
            matching: mcData.blocksByName.crafting_table.id,
            maxDistance: 128,
        });
        if (crafting_table) {
            /**
             * Minecraft: /setblock <x> <y> <z> air destroy
             * - 指定座標のブロックを空気ブロックに置き換える
             * - destroy: ブロックを破壊エフェクトと共に消去
             * Mineflayer: bot.chat()で座標を指定してブロックを削除
             */
            bot.chat(
                `/setblock ${crafting_table.position.x} ${crafting_table.position.y} ${crafting_table.position.z} air destroy`
            );

            /**
             * Minecraft: /give @s crafting_table
             * - @s: コマンドを実行したプレイヤー（この場合はボット）自身
             * - アイテムをインベントリに直接追加
             * Mineflayer: bot.chat()でボットのインベントリにアイテムを追加
             */
            bot.chat("/give @s crafting_table");
        }

        // かまどの処理
        const furnace = bot.findBlock({
            matching: mcData.blocksByName.furnace.id,
            maxDistance: 128,
        });
        if (furnace) {
            /**
             * Minecraft: /setblock <x> <y> <z> air destroy
             * - かまどを空気ブロックに置き換えて消去
             * Mineflayer: bot.chat()で座標を指定してかまどを削除
             */
            bot.chat(
                `/setblock ${furnace.position.x} ${furnace.position.y} ${furnace.position.z} air destroy`
            );

            /**
             * Minecraft: /give @s furnace
             * - かまどをボットのインベントリに追加
             * Mineflayer: bot.chat()でボットのインベントリにかまどを追加
             */
            bot.chat("/give @s furnace");
        }

        // インベントリ管理（チェストの付与）
        if (bot.inventoryUsed() >= 32) {
            if (!bot.inventory.items().find((item) => item.name === "chest")) {
                /**
                 * Minecraft: /give @s chest
                 * - インベントリが32スロット以上使用されている場合
                 * - チェストをボットのインベントリに追加
                 * Mineflayer: bot.chat()でボットのインベントリにチェストを追加
                 */
                bot.chat("/give @s chest");
            }
        }

        // 鉄のツルハシの処理
        if (
            bot.iron_pickaxe &&
            !bot.inventory.items().find((item) => item.name === "iron_pickaxe")
        ) {
            /**
             * Minecraft: /give @s iron_pickaxe
             * - 鉄のツルハシをボットのインベントリに追加
             * - bot.iron_pickaxeがtrueで、インベントリに鉄のツルハシがない場合に実行
             * Mineflayer: bot.chat()でボットのインベントリに鉄のツルハシを追加
             */
            bot.chat("/give @s iron_pickaxe");
        }

        /**
         * Minecraft: /gamerule doTileDrops true
         * - ブロックを破壊した時にアイテムが通常通りドロップするように戻す
         * - ゲームの通常の動作に戻すための設定
         * Mineflayer: bot.chat()でゲームルールを元に戻す
         */
        bot.chat("/gamerule doTileDrops true");
    }

    /**
     * エラーハンドリング関数
     * エラーメッセージを整形し、デバッグ情報を付加します
     * 
     * @param {Error} err - 発生したエラー
     * @returns {string} 整形されたエラーメッセージ
     */
    function handleError(err) {
        let stack = err.stack;
        if (!stack) {
            return err;
        }
        console.log(stack);
        const final_line = stack.split("\n")[1];
        const regex = /<anonymous>:(\d+):\d+\)/;

        // エラー位置の特定
        const programs_length = programs.split("\n").length;
        let match_line = null;
        for (const line of stack.split("\n")) {
            const match = regex.exec(line);
            if (match) {
                const line_num = parseInt(match[1]);
                if (line_num >= programs_length) {
                    match_line = line_num - programs_length;
                    break;
                }
            }
        }
        if (!match_line) {
            return err.message;
        }

        // エラーメッセージの生成
        let f_line = final_line.match(
            /\((?<file>.*):(?<line>\d+):(?<pos>\d+)\)/
        );
        if (f_line && f_line.groups && fs.existsSync(f_line.groups.file)) {
            const { file, line, pos } = f_line.groups;
            const f = fs.readFileSync(file, "utf8").split("\n");
            let source = file + `:${line}\n${f[line - 1].trim()}\n `;

            const code_source =
                "at " +
                code.split("\n")[match_line - 1].trim() +
                " in your code";
            return source + err.message + "\n" + code_source;
        } else if (
            f_line &&
            f_line.groups &&
            f_line.groups.file.includes("<anonymous>")
        ) {
            const { file, line, pos } = f_line.groups;
            let source =
                "Your code" +
                `:${match_line}\n${code.split("\n")[match_line - 1].trim()}\n `;
            let code_source = "";
            if (line < programs_length) {
                source =
                    "In your program code: " +
                    programs.split("\n")[line - 1].trim() +
                    "\n";
                code_source = `at line ${match_line}:${code
                    .split("\n")
                    [match_line - 1].trim()} in your code`;
            }
            return source + err.message + "\n" + code_source;
        }
        return err.message;
    }
});

/**
 * ボットの停止エンドポイント
 * ボットを安全に終了させ、リソースを解放します
 * 
 * レスポンス:
 * - message: "Bot stopped"
 */
app.post("/stop", (req, res) => {
    bot.end();
    res.json({
        message: "Bot stopped",
    });
});

/**
 * ゲームの一時停止エンドポイント
 * ゲームを一時停止し、ボットの状態を保持します
 * 
 * レスポンス:
 * - 成功時: { message: "Success" }
 * - 失敗時: { error: "Bot not spawned" }
 */
app.post("/pause", (req, res) => {
    if (!bot) {
        res.status(400).json({ error: "Bot not spawned" });
        return;
    }
    bot.chat("/pause");
    bot.waitForTicks(bot.waitTicks).then(() => {
        res.json({ message: "Success" });
    });
});

// サーバーの設定と起動
const DEFAULT_PORT = 3000;
const PORT = process.argv[2] || DEFAULT_PORT;

/**
 * サーバーの起動
 * 指定されたポート（デフォルト: 3000）でサーバーを起動します
 */
app.listen(PORT, () => {
    console.log(`Server started on port ${PORT}`);
});
