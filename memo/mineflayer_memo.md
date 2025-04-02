# MineFlyer Primitives Code(Voyager)

LLM側には、Conetxtが渡され、変数にみを渡すことでコンテキスト量を節約しています。
実際の実行時では Codeも渡すことで、コンテキスト量と、実行を両立させています。

## craftitems

### Context
``` js
// オークの原木2個からオークの板8個を作成(レシピを2回実行): craftItem(bot, "oak_planks", 2);
// この関数を呼び出す前に作業台を設置しておく必要があります
async function craftItem(bot, name, count = 1) {
    const item = mcData.itemsByName[name];
    const craftingTable = bot.findBlock({
        matching: mcData.blocksByName.crafting_table.id,
        maxDistance: 32,
    });
    await bot.pathfinder.goto(
        new GoalLookAtBlock(craftingTable.position, bot.world)
    );
    const recipe = bot.recipesFor(item.id, null, 1, craftingTable)[0];
    await bot.craft(recipe, count, craftingTable);
}
```

### Code

``` js
async function craftItem(bot, name, count = 1) {
    // return if name is not string
    if (typeof name !== "string") {
        throw new Error("name for craftItem must be a string");
    }
    // return if count is not number
    if (typeof count !== "number") {
        throw new Error("count for craftItem must be a number");
    }
    const itemByName = mcData.itemsByName[name];
    if (!itemByName) {
        throw new Error(`No item named ${name}`);
    }
    const craftingTable = bot.findBlock({
        matching: mcData.blocksByName.crafting_table.id,
        maxDistance: 32,
    });
    if (!craftingTable) {
        bot.chat("Craft without a crafting table");
    } else {
        await bot.pathfinder.goto(
            new GoalLookAtBlock(craftingTable.position, bot.world)
        );
    }
    const recipe = bot.recipesFor(itemByName.id, null, 1, craftingTable)[0];
    if (recipe) {
        bot.chat(`I can make ${name}`);
        try {
            await bot.craft(recipe, count, craftingTable);
            bot.chat(`I did the recipe for ${name} ${count} times`);
        } catch (err) {
            bot.chat(`I cannot do the recipe for ${name} ${count} times`);
        }
    } else {
        failedCraftFeedback(bot, name, itemByName, craftingTable);
        _craftItemFailCount++;
        if (_craftItemFailCount > 10) {
            throw new Error(
                "craftItem failed too many times, check chat log to see what happened"
            );
        }
    }
}
```

## exploreUntil

### Context
``` js
/*
鉄鉱石を見つけるまで探索する。鉄鉱石は通常地下にあるため、Vec3(0, -1, 0)を使用
await exploreUntil(bot, new Vec3(0, -1, 0), 60, () => {
    const iron_ore = bot.findBlock({
        matching: mcData.blocksByName["iron_ore"].id,
        maxDistance: 32,
    });
    return iron_ore;
});

豚を見つけるまで探索する。豚は通常地上にいるため、Vec3(1, 0, 1)を使用
let pig = await exploreUntil(bot, new Vec3(1, 0, 1), 60, () => {
    const pig = bot.nearestEntity((entity) => {
        return (
            entity.name === "pig" &&
            entity.position.distanceTo(bot.entity.position) < 32
        );
    });
    return pig;
});
*/
async function exploreUntil(bot, direction, maxTime = 60, callback) {
    /*
    この関数の実装は省略されています。
    direction: Vec3、-1、0、1の値のみ含むことができます
    maxTime: number、探索の最大時間
    callback: function、早期停止条件、毎秒呼び出され、戻り値がnullでない場合に探索を停止します

    戻り値: 探索がタイムアウトした場合はnull、それ以外の場合はcallbackの戻り値を返します
    */
}
```