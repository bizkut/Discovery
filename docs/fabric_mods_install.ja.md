# Fabricモッドのインストール

Voyagerを使用するには、以下のFabricモッドが必要です：

1. [fabric-api](https://www.curseforge.com/minecraft/mc-mods/fabric-api/files/3902660)
2. [fabric-language-kotlin](https://www.curseforge.com/minecraft/mc-mods/fabric-language-kotlin/files/3850090)
3. [fabric-carpet](https://www.curseforge.com/minecraft/mc-mods/carpet/files/3725895)
4. [lithium-fabric](https://www.curseforge.com/minecraft/mc-mods/lithium/files/3830120)

上記のリンクからモッドをダウンロードし、Minecraftの`mods`フォルダに配置してください。

最後のモッド[Better Respawn](https://github.com/xieleo5/better-respawn/tree/1.19)については、手動でクローンしてコンパイルする必要があります：

1. リポジトリをクローンした後、`settings.gradle`の最後の行にある`'forge'`文字列を削除します。
2. `gradlew build`を実行してモッドをコンパイルします。コンパイルされたjarファイルは`better-respawn/fabric/build/libs/better-respawn-fabric-1.19-2.0.0.jar`にあります。このjarファイルをmodsフォルダに配置してください。
   * `better-respawn`をビルドするにはJava Runtime Environment v17以上が必要です。新しいバージョンのJREではビルド時にエラーが発生する場合があります。JRE v17のアーカイブは[こちら](https://www.oracle.com/java/technologies/javase/jdk17-archive-downloads.html)で入手できます。
3. ゲームを起動した後、`YOUR_MINECRAFT_GAME_LOCATION/config/better-respawn`に移動し、propertiesファイルを以下のように修正してください：
   ```
   respawn_block_range=32
   max_respawn_distance=32
   min_respawn_distance=0
   ```

最後に、`azure_login`の`version`を使用している`fabric-loader-0.14.18-1.19`に変更することを忘れないでください。このバージョンは`YOUR_MINECRAFT_GAME_LOCATION/version`フォルダで確認できます。

これで[README.md](../README.md#getting-started)に戻り、使用を開始できます。 