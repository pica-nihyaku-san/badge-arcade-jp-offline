# バッジとれーるセンター 日本版 オフライン化 移植計画

作成: 2026-11-10 / 非公開・個人利用前提 / 目標: 起動 + 練習キャッチャー (最終的には Vanilla 相当 = 通常台も含む見込み)

## 前提 (確定済み)
- 手元の CIA は **日本版**。セーブ・extdata は **なし** (新規状態から開始で問題ない設計にする)
- 日本版タイトルID: 本体 `0004000000134600`、更新は `0004000E00134600` (EUR版のパターンからの推定、CIA 実物で要検証)
- 対象バージョン: 本体 1.3.0 + 更新 1.3.1 (EUR 版パッチと同じ構成)

## お手本 (調査済み・ローカルに clone 済み)
- `eur-reference/` = GrouchoGlasses42/badge-arcade-offline (EUR 版オフライン化、v0.5.4)
- 構成が移植向き:
  - `patches/badge_offline.s` (733行) — パッチ本体は ARM アセンブリソース。基準アドレスは EUR 1.3.0
  - `src/badge_versions.py` — 1.3.0→1.3.1 のアドレス対応表 (関数単位でマッチ、全体シフトではない)。SHA-256 とサイズで対象 code.bin を検証
  - `src/badge_patch.py` — code.bin を検証して IPS を生成するビルダー
  - テスト一式あり (EUR では 446 tests / Azahar 実績あり)
- Vanilla は code.ips 1 本のみで動作し、台レイアウトは更新データ内蔵のものを使う。練習台は通常台と別枠で読み込まれる (EUR で確認済み)

## 素材受領状況 (2026-11-10)
- ✅ 本体CIA (36,488,192 bytes, SHA-256 5e809ecb…) / 更新CIA (100,381,696 bytes, SHA-256 81355ca5…) を `inputs/` に受領
- ✅ メタデータ検証済み: 本体タイトルID `0004000000134600` (title ver. raw 1040)、更新 `0004000e00134600` (raw 5200)。各2コンテンツ (本体+マニュアル)
- ✅ **訂正 (2026-11-10)**: GM9 の standard ビルドは復号済みだった (実機側でも "file is not encrypted" 表示を確認)。当初の「暗号化されたまま」判定は CIA セクション順序 (Meta は最後) のパーサバグが原因
- ✅ 展開完了 (ctrtool を自前ビルドして使用): 
  - 本体 code.bin (展開後) 3,280,896 bytes (0x321000), SHA-256 51fb6f8a…
  - 更新 code.bin (展開後) **3,502,080 bytes (0x357000)**, SHA-256 ee533a05… — **EUR 更新版とサイズ完全一致**
  - 更新 RomFS に region_common/Schedule.xml、region_JPN/sharc/pc.sarc 等を確認。code 内に npdl CDN URL、allbadge_v131.dat、boss.sarc 等の文字列を確認 → JP 更新は v131 世代で確定

## 移植作業 (JP でやること)
1. ~~**素材受領**~~ ✅ / 残り: 復号済み CIA の受領
2. **展開**: 両 CIA から復号済み code.bin (本体 1.3.0 / 更新 1.3.1) と RomFS を抽出
   - 要ツール準備: ctrtool 等 (現環境に未導入、着手時に用意)
3. **アドレス対応表の JP 版を作成**:
   - EUR 1.3.0 code.bin と JP 1.3.0 code.bin を関数単位でバイナリマッチングし、パッチ内の絶対参照 (~100箇所) の JP 対応アドレスを特定
   - 同様に JP 1.3.1 への対応表を作成し、`badge_versions.py` に JP Revision を追加 (SHA-256/サイズ/world_shift)
   - リージョン差分に注意: region_JPN パス、Schedule.xml、文字列、NASC/NNID 周りの差異
4. **ビルド**: 既存ビルダーで JP 用 code.ips を生成 (game-only 版を第一候補にする = HOMEメニュー側バッジデータに触らない)
5. **検証 (実機の前に)**:
   - Azahar 上で JP 本体+更新+IPS を起動し、タイトル到達・練習台レイアウト読み込み・無料プレイ周りを確認 (EUR 版の検証手順を踏襲)
   - 通れば実機 (New3DS LL) で Luma game patching テスト
6. **仕上げ確認**: 起動→練習キャッチャー完走、結果画面、再起動後のローカルセーブ保持、通信が発生しないこと

## リスク / 未知数
- JP 1.3.1 のコード配置が EUR とどれだけ乖離しているか (同一コードベースなので大半は関数マッチで解決する想定だが、保証はまだない)
- JP 固有のオンライン処理 (国内向け文言・遷移) が EUR と異なる分岐を持つ可能性
- 実機投入は Azahar 検証を通してから。それまでは実機の HOME メニュー側データに触らない

## 完了条件
- オフライン状態で起動し、当たりつき！練習キャッチャーが最後まで遊べ、終了・再起動しても詰まらないこと

## 初回プローブ結果 (2026-11-10)
- EUR 1.3.1 のフック48箇所について、JP 更新 code.bin の同一オフセットを逆アセンブル確認
- **30/48 が関数プロローグ (push {.., lr} 等) に一致**。特に SDK 領域 (0x18Fxxx〜0x24Fxxx) はほぼ全て一致
- 不一致の多くは元々関数途中へのフック (badge_versions の対応表で別アドレスに飛ぶ箇所等) とみられ、配置が大きくズレている兆候はない
- → JP/EUR のコード配置は大半が共通という作業仮説でアドレス対応を進める

## アドレス対応プローブ結果 (2026-11-10, work/mapping-probe.md)
- **48フック中 38件 HIGH、9件 MEDIUM、1件 LOW**（title_start は命令パターン署名で確定、第2プローブで6件追加解決。LOW の request_complete #2 は候補3件を Azahar 動的検証で確定予定。詳細: work/mapping-probe.md / work/mapping-probe2.md / work/session-notes.md）
- SDKスタブ群13件は全件プロローグ完全一致 → EUR/JP は同一レイアウト系統で確定
- ペイロード置き場 (cave): JP では 0x34CD78 ("NexUpdateFreePlay" ワーカー入口) から取るべき。容量 0x930 ≥ EUR 実ペイロード 0x8F4
- v131 ファイル名群は静的ポインタテーブル VA 0x42BCC0〜 から参照。.data の +0x1000 シフトも JP で同一 → データ参照は移植可能性高
- 次: JP リビジョン（アドレス表＋ビルダー）を作り、初回 JP code.ips をビルド → Azahar 検証

## 最終状態 (2026-11-10) — リリース整理完了・2バリアント

完了条件 (起動 + 練習キャッチャー) は v6 時点で達成。その後、通常台・
0 円購入・バッジ保存/復元・初回説明の永続化・プレイ中の HOME ボタン
まで実機確認済みとなり、**v13 を正式版**とした。詳細な解析・検証の
記録は work/crash3-analysis.md §20–§34 / work/jp-build-notes.md。

### 飾れる版 (kazereru) = v13
- `out/release/kazereru/code.ips` (正規成果物 `out/code_v13.ips` と同一)
- SHA-256 `369bca8094f76894d1db37acb8c402338f441d1353f49343b8f9178ff6bbca4d`、44 records / 34 hooks
- badge_home_* スタブ全除去: 共有 extdata 0x14D1 の生成・HOME 書き出しはネイティブ
- 実機確認済み: 起動 (SD エラーなし)、説明の永続化、HOME ボタン動作、購入/保存/復元
- 未検証は 1 点のみ: 「バッジをかざる」自体 (書き出し経路は有効。§29 の再テスト待ち)

### 飾らない版 (kazaranai) = v13_light
- `out/release/kazaranai/code.ips` (正規成果物 `out/code_v13_light.ips` と同一)
- SHA-256 `5cc924659a79c1a85212277f4cd2fee59237edad938c222b449c31d74173d2b7`、53 records / 43 hooks
- v13 との差分は書き出し/装飾系スタブ 9 件のみ。起動に必須の 6 件
  (0x14D1 生成チェーン 4 件 + 説明フラグ + home_result #1) は stock 維持
  (素朴な game-only 構成は v12 の起動 SD エラーになるため不可、§33/§34)
- Azahar 2 ブート検証済み (フレッシュ起動含む)。**実機は初回起動チェック待ち**

### 系統ヘッド
- `out/code.ips` / `out/build.json` は v13 (飾れる版) を指す。
