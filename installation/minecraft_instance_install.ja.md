# Minecraftインスタンスのインストール

Voyagerを使用するには、まず公式の[Minecraft](https://www.minecraft.net/)ゲーム（バージョン1.19）がインストールされている必要があります。

Voyager用のMinecraftインスタンスを開始するには2つの方法があります。GPT-4が無限ループを生成する場合があり、その場合にリクエストタイムアウトが発生します。Azure loginを使用すると、リクエストタイムアウト時に自動的に再開できます。

## オプション1: Microsoft Azure Login（推奨）
このメソッドを使用すると、リクエストタイムアウト時にVoyagerが自動的に再開できます。これは[minecraft-launcher-lib](https://minecraft-launcher-lib.readthedocs.io/en/stable/tutorial/microsoft_login.html#let-the-user-log-in)ライブラリに依存しています。

1. [Azure Portal](https://portal.azure.com/)にサインインします。
2. [Azure Active Directory](https://portal.azure.com/#blade/Microsoft_AAD_IAM/ActiveDirectoryMenuBlade/Overview)に移動します。
3. 左パネルの`アプリの登録`タブをクリックします。
4. `新規登録`ボタンをクリックします。
5. フォームに以下の値を入力します：
    - 名前: `YOUR_APP_NAME`（任意のアプリ名）
    - サポートされているアカウントの種類: `任意のAzure ADディレクトリ内のアカウントと個人のMicrosoftアカウント`
    - リダイレクトURI タイプ: `パブリッククライアント/ネイティブ（モバイル＆デスクトップ）`、値: `https://127.0.0.1/auth-response`
    （最後に`KeyError: 'access_token'`が発生する場合は、タイプを`Web`に変更してみてください。詳細は[FAQ](https://github.com/MineDojo/Voyager/blob/main/FAQ.md)を参照）
6. `登録`ボタンをクリックします。
7. 表示される`アプリケーション（クライアント）ID`が、あなたの`client_id`となります。
8. [オプション] `証明書とシークレット`タブに移動し、`新しいクライアントシークレット`ボタンをクリックします。説明を入力し、`追加`をクリックすると値が表示されます。これがあなたの`secret_value`となります。
9. Minecraftのインストール場所`YOUR_MINECRAFT_GAME_LOCATION/versions`に移動し、所有しているバージョンを確認します。フォルダ名がすべて有効な`version`の値となります。

これらの手順の後、以下のようなazure_login情報が得られます：
```python
azure_login = {
    "client_id": "ステップ7で取得したCLIENT_ID",
    "redirect_url": "https://127.0.0.1/auth-response",
    "secret_value": "[オプション] ステップ8で取得したSECRET_KEY",
    "version": "使用したいMINECRAFTバージョン",
}
```

**Voyagerは`fabric-loader-0.14.18-1.19`バージョンを使用してすべての実験を実行します。** 現在このバージョンをお持ちでない場合は、[Fabric Mods Install](fabric_mods_install.md#fabric-mods-install)セクションに進み、そこの手順に従ってゲームのfabricバージョンをインストールしてください。

## オプション2: Minecraft公式ランチャー

公式Minecraftをインストールした後、Minecraft公式ランチャーを開き、以下の手順に従ってください：
1. プレイしたいバージョンを選択してゲームを起動します。
2. `シングルプレイヤー`を選択し、新しいワールドを作成します。
3. ゲームモードを`クリエイティブ`に、難易度を`ピースフル`に設定します。
4. ワールドが作成されたら、`Esc`キーを押して`LANに公開`を選択します。
5. `チートを許可: オン`を選択し、`LANワールドを開始`を押します。
6. チャットログにポート番号が表示されます。これがあなたの`mc-port`となり、後でVoyagerを初期化する際に使用します。 