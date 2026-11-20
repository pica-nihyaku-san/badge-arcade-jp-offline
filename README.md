# バッジとれ〜るセンター JP オフラインパッチ

ニンテンドー3DS『バッジとれ〜るセンター』日本版を、インターネット接続なしで遊べるようにするパッチです。

欧州版向けのオフラインパッチ [badge-arcade-offline](https://github.com/GrouchoGlasses42/badge-arcade-offline)（GrouchoGlasses42）を日本版に移植したものです。このリポジトリに含まれているのはパッチとツール類だけで、ゲーム本体のデータは含まれていません。利用にはご自身のゲームが必要です。

## 対象

- 日本版『バッジとれ〜るセンター』本体 1.3.0（タイトルID `0004000000134600`）
- 更新データ 1.3.1（タイトルID `0004000E00134600`）がインストール済みであること
- Luma3DS の game patching が使える環境

## 版の選び方（`jp-releases/`）

2つの版があります。中身はどちらも `code.ips` 1つです。できることと制限の詳細は、各フォルダの README を見てください。

- **飾れる版 v13**（`jp-releases/kazereru/`）
  HOME メニュー連携（バッジの書き出し）を含むフル版です。ゲームの動作は実機で確認済みですが、「バッジをかざる」自体の実機確認はまだです（書き出し経路は有効になっています）。GYTB 等で入れた既存の HOME バッジがある場合、それが置き換わる可能性があります。
- **飾らない版 v13_light**（`jp-releases/kazaranai/`）
  HOME メニュー側のバッジデータに書き込まない版です。それ以外の挙動は飾れる版と同じ構成で、Azahar で起動を検証済みです。

## 導入

1. 更新データがインストール済みであることを確認します。
2. 使いたい版の `code.ips` を、SD カードの `luma/titles/0004000000134600/` に置きます。
3. Luma の game patching を有効にして起動します。初回起動時に共有 extdata（0x14D1）が自動生成されますが、正常な動作です。

## リポジトリの構成

- `jp-releases/` — 日本版のリリース（上記の2版）
- `patches/` — パッチのアセンブリソース。`badge_offline.s` が原作（欧州版）、`badge_offline_jp.s` が日本版です
- `src/`・`tools/`・`tests/` — 原作のビルドシステムに日本版対応（`src/badge_patch_jp.py` など）を加えたもの。Expanded / Custom Weekly モードは欧州版向けで、日本版では未検証です
- `releases/` — 原作の欧州版リリース（参照用）
- `PORT-PLAN.md` — 日本版移植の作業記録
- `docs/upstream-readme-eur.md` — 原作の README（欧州版向けの説明）

## ライセンスとクレジット

- 原作：[GrouchoGlasses42/badge-arcade-offline](https://github.com/GrouchoGlasses42/badge-arcade-offline)。本リポジトリも原作と同じ MIT License です（`LICENSE`）
- TinyXML-2 と picojson は `src/weekly_native/vendor/` 内の各ライセンスに従います
- このプロジェクトは任天堂とは関係ありません
