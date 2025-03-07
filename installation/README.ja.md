# Voyagerインストールガイド

このフォルダーには、Voyagerをセットアップするために必要な詳細なインストール手順が含まれています。

## インストール手順の概要

1. [Minecraftインスタンスのインストール](minecraft_instance_install.ja.md)
   - Minecraftゲーム（バージョン1.19）のセットアップ
   - Azure Loginの設定（推奨）または公式ランチャーの設定

2. [Fabricモッドのインストール](fabric_mods_install.ja.md)
   - 必要なFabricモッドのダウンロードとインストール
   - Better Respawnモッドの手動ビルドとセットアップ

## 重要な要件

- Minecraft バージョン: 1.19
- Fabric Loader バージョン: 0.14.18
- Java Runtime Environment: v17以上（Better Respawnのビルドに必要）

## インストール後の確認事項

1. Minecraftが正しく設定されているか
   - バージョンが1.19であることを確認
   - LANワールドが正しく公開できることを確認

2. Fabricモッドが正しくインストールされているか
   - すべての必要なモッドがmodsフォルダーに存在することを確認
   - Better Respawnの設定が正しく行われていることを確認

3. 接続設定の確認
   - Azure Loginを使用する場合：認証情報が正しく設定されているか確認
   - 公式ランチャーを使用する場合：ポート番号をメモしているか確認

## トラブルシューティング

問題が発生した場合は、以下を確認してください：

1. Minecraftのバージョンが正しいか
2. すべてのFabricモッドが正しいバージョンでインストールされているか
3. Java Runtime Environmentのバージョンが適切か
4. Azure Login設定が正しく行われているか

詳細な問題解決については、メインの[FAQ](../FAQ.md)を参照してください。 