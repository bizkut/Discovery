# MineCraft Mod Install Gide

Discoveryを動作させるには、FabicによるModインストールを推奨しています

## Fabric のインストール

1. [fabic](https://fabricmc.net/use/installer/)よりインストーラーをダウンロードし、Fabicをインストールします
1. ダウンロードした実行ファイルを実行します
1. 「クライアント」➛ Minecraftバージョンにて「1.19」を選択します(1.20.6まで対応しているはずだが、未確認)
1. 「インストール」を押し、Fabricをインストールします。

## Mod の導入

1. 「Win」+「R」で「ファイル名を設定して実行」を開き「%appdata%」と入力し「OK」を押します。
1. アプリケーションフォルダ内の「.minecraft」➛ 「mods」を開きます。
1. 以下のModをダウンロードし、modsフォルダーに保存します。

   **注意: curseforgeリンクを開いた後、「Files」「All Games Version」を任意のバージョン(例1.19)に変更し適合したバージョンのjarファイルをダウンロードしてください**
   - [Fabric API](https://www.curseforge.com/minecraft/mc-mods/fabric-api)
   - [CompleteConfig](https://www.curseforge.com/minecraft/mc-mods/completeconfig)
   - [Mod Menu](https://www.curseforge.com/minecraft/mc-mods/modmenu)
   - [Multiplayer Server Pause (Forge)](https://www.curseforge.com/minecraft/mc-mods/multiplayer-server-pause-forge)

## 動作確認

1. マインクラフトランチャーを起動します。
1. Fabricの導入が完了していればMineCraft Java Editionのビルド選択に「Fabric-loader-your_version」が表示されます。
1. Fabricビルドを選択して、「プレイ」を押します。警告が表示されますが「プレイ」を押します。
1. MOD導入が完了していれば問題なく起動します。エラーが発生した場合、導入Modのバージョンを確認してください。