# r2要件・節単位のSealとbind実験

2026-09-30 / 登録とbind実験完了

既存ファイル単位の要件・承認Sealを保持し、PL-01〜24と主要2節（状態、最小のやり取り）を個別REFとして追加した。各REFのCauseは確定r2のexact Seal `84bfb02b2415d930b4997cadcd248b399304e3aaee1dbc9d6447f07cd0ff5a94`。部分Sealは新しい所有者承認ではなく、確定済み本文の抜粋である。

`trace set --source-file ... --source-key purpose-lifecycle-r2-source --content ...` により全文スナップショットから正確な部分文字列とOrigin Traceを登録し、`trace source bind`で同じsource keyを現在のr2ファイルに結び付けた。26 REFすべての内容を読み戻し、元の部分文字列と一致確認。最終trace compareの全26対象にcomplete=true、PRESENTを確認。

## bindの実験

PL-01について原文ファイルを保持したまま一時コピーの「安定したID」を「一時的ID」に変更。bindの同一パス再実行、観測済みパスを指定したrebind、比較、元パスへの復元を試した。

- 元ファイル：PRESENT / EXACT_MATCH
- 変更した一時コピーへrebind：ABSENT_EXACT / NO_EXACT_MATCH
- 元ファイルへrebindで復元：PRESENT / EXACT_MATCH

初回の検証スクリプトが不在ラベルをABSENTと仮定してassertionに失敗した。CLIの実際の出力は正しいABSENT_EXACTだったため検証期待値を修正し、再実行した。一時コピーは削除し、原文bytesとbindの復元を確認した。

bindは現在ファイルの観測先を設定するローカル機能であり、Seal・承認・Causeを変更しない。部分Sealへ通常の全文source bindは付けていない。部分の比較はtrace compareで行う。

## 制約と今後の使い方

Origin Traceは元全文のimmutable snapshotを保存する。秘密を含む全文へ適用する際は、抜粋だけが保存されるとの前提を置かない。今回のr2には共有対象の要件文のみを使用した。

同じ部分文字列が複数回あれば、direct matchingの最初の出現を使用する。現在の一致位置は過去の起源位置の証明ではない。さらにCauseは全文要件を参照しているため、全文要件HEAD更新時の影響判定は部分ごとに限定されない。細粒度Seal登録と細粒度の変更影響判定は別の能力として扱う。

この登録ではシミュレーションと承認記録の細分化、既存5文書の修正/再Sealは行っていない。今後の設計は適切なPL単位をCauseにし、承認根拠も別途参照できる。

## 登録一覧

| REF | Seal ID | 部分内容SHA-256 |
|---|---|---|
| `requirements/purpose-lifecycle-r2/PL-01` | `caf272daf42ae00346252454ebee5539f59f79eb80d0a45b18d84788a3ca8846` | `12f4e8c5dfb827bf3582164f92a2f60d00448ea3c8a034201b89cb6d6c9e9e12` |
| `requirements/purpose-lifecycle-r2/PL-02` | `2eb7c4f2d22084c6aecb4476ddb5f43758291e142ae85b26c07c58f7fc94230b` | `23deefa234c4cdd37ed11643b8126c9a7f1494423f46551537f805d7e817c675` |
| `requirements/purpose-lifecycle-r2/PL-03` | `ab77b8256aa83d719e97460a7f989e25a7085a8818ce0c2fb16bc1f2f8bd5818` | `2c4cea5237f811ee33c02e9a7b69002f8ea80d027389ae78d0da548efc2ba8d6` |
| `requirements/purpose-lifecycle-r2/PL-04` | `c8493b9b80a2259e674364fd4c1b600fa0b81cad11bd24207229d7a158beb110` | `a122cf6513f57be09e467457f04c2e48498b7dfa746f49ebba7c26fcdf3279aa` |
| `requirements/purpose-lifecycle-r2/PL-05` | `876f6084f170d098faba9432e3246f8d1248a871db709e6946605482f6c33bf7` | `74ae0235fde8ec3336335323f99981587ab6500848e4788853a1e1c3a2b8ebe4` |
| `requirements/purpose-lifecycle-r2/PL-06` | `7e471b9ab1187a3a261dcdc356645fbf2ff637fb7706764fa597b2608480d857` | `bac8e295615f08405235c191dfadce38fc63da515f593efeadc4f828ee49a064` |
| `requirements/purpose-lifecycle-r2/PL-07` | `819abca8583d2999e92d6b37c3a6152c9ac639b0340675ce518130ceb2c3bf5f` | `dc25d182d088b345726d2fb03aedfdc9bd683eff4b9ac1e71209a95491e94dd5` |
| `requirements/purpose-lifecycle-r2/PL-08` | `f657f8d67b8f3390c0b5f7248e0b5426c6acd55d049ad48c9095497282b37208` | `6787ab1e0e34928e4c74502f51c4d2917c8ff4cc15109344f814104146a89dd3` |
| `requirements/purpose-lifecycle-r2/PL-09` | `b2542e71f32a6a4a03a3b3e26259b4800d2210cd9e7a9bbd2b5816322af98467` | `8e61eb7eb8c08ee0644e778b42759d7c116d8ee19c965135b35695e499f97823` |
| `requirements/purpose-lifecycle-r2/PL-10` | `08e5c510acefd62fcaa4cf7cdc0bac412660f82c940caf0019e9eb16b5b34631` | `c0ceb45d8633390ab537996e6f661e129ea1943af9f3097aa5c50fba07e5da7b` |
| `requirements/purpose-lifecycle-r2/PL-11` | `f080e80b1efc11413a6bccf9e2d91b4ce345dd5745ddc83ce3eacf480b5714b2` | `9e562cccea284bb7f8c4e7988cf8aced65ae91dc26cf22d40a3d8e42bb8c8eef` |
| `requirements/purpose-lifecycle-r2/PL-12` | `8f8324910ce9193917787bd8586d23ada3726e2693a2e24ba9caaed8f75cbffc` | `289d1a78edaab06d38f1a3462bd2f8acaaacd6c045f89360757869b0727005b9` |
| `requirements/purpose-lifecycle-r2/PL-13` | `323d322cf417841ebe4b04e4e44a151c15a61623d2f6cbc246abebbb15675d86` | `59770c508779a2c7189185f42eb943ef8b4a6711035331af8fe2e902ab051c5d` |
| `requirements/purpose-lifecycle-r2/PL-14` | `f2fa0f539510d5d6994c093e1bffcaa81aa0f9fbdc8d21019a78fdf6f0477735` | `c90b21b1c119e952d4784f2b135df389fcbfc048eabf40b3eae14630e26f984e` |
| `requirements/purpose-lifecycle-r2/PL-15` | `f86864c35f90d3450a694156b2cd92caf2af78c5e20022c14df771a1b3e89b75` | `23c9dfb65678c91ca30f9241365233cecf8b852cb3c487570176ac7dd366dd5a` |
| `requirements/purpose-lifecycle-r2/PL-16` | `8b3749509b9550161fbe81dd14ec8cbdae7ff669567d4483c8acd960dc5d9f35` | `3fc02e74640523e0fd583a733b0e29aaefea442f2d37644ae623c8987f85e4fc` |
| `requirements/purpose-lifecycle-r2/PL-17` | `f169e5d16334f1c4ebe63d27c25e2a88510a96c2099f7827320877c09e4c8fc8` | `812291687da24fc2b22dfe15fb2575859973b9d458d69f0b1fe5a6c42c23fa3e` |
| `requirements/purpose-lifecycle-r2/PL-18` | `2736d966c7bfea703784ee2c5b258f1f56b8727beed5086aed15f61dea6930ae` | `bd234ce24bc591d9d74e1a66842ca5f8f46cead9a246bc608f0655e08eea7c2d` |
| `requirements/purpose-lifecycle-r2/PL-19` | `68583b7fee20dfcd2cbd4d2c245ba240fb8367d058fae91d5dec477d77fc189b` | `4bdc3452b7eca06e8732b33b4c76e16265d8ab281b4aab6aa0f9eedb32cbc888` |
| `requirements/purpose-lifecycle-r2/PL-20` | `8a08b31aca649ed0cefe8d911ab07f66679fca637b9eac158ac7ca8cee9cc429` | `aa3e9f0759fc2f56aa699ec22126a20bdec7b424695337c3f95e6913be9f29c7` |
| `requirements/purpose-lifecycle-r2/PL-21` | `64bf5b2cd3a87b3857007f66ac34cc8bb7672bc6fb706b1d47ce32f0c87b10ca` | `0978c9f0087c6354162c3bf74190979db188c5bacfd90f217918c32d8f4068e0` |
| `requirements/purpose-lifecycle-r2/PL-22` | `1dca5867530abea640ab7d9d1cd97f6773dd378940104416ed3d1174c0dbf0bf` | `be9e1f7394a668b38d8389ddfb465ef808a7435c34c40b3f5e3c9240bf58a92a` |
| `requirements/purpose-lifecycle-r2/PL-23` | `b88be902df4b6e42526e8780c79408b955388ea02cf73b9c33da239e19afc839` | `dc53f3fbc8e4b7a8c122e32bd5942d852cc36e24fe36cd2b9e63d0d6abbb96b1` |
| `requirements/purpose-lifecycle-r2/PL-24` | `d01072d4e2f79424eb3114319faf63d0234c83a8e14c9bb5937f2c9d9cd3e359` | `63f59bce4aee5316d557d0eaa1fdf4d9136c9c2b8b5ae5f881cd942c14019ab5` |
| `requirements/purpose-lifecycle-r2/section-states` | `04ab4f0c1a6c00fb83dafb1d18ba8f43072bf2661d3310b6a21556ae541d5e28` | `4fd81d13c3a3c0bfbaa111e7a6001d069045135d0c7880193d6402f2ea76f165` |
| `requirements/purpose-lifecycle-r2/section-interactions` | `7a9dcacf50e329d8ffefba96b82d089b15bca049aad62e1499b351227d297491` | `f43a054027d28caa3f3f6663efcbac9885f7b022f4efb6c474ed1ffef16ff854` |
