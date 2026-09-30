# Purposeライフサイクル provenance登録状況

2026-09-30 / 登録完了（以下の事前課題・提案は履歴）

## 直接観測した課題

現在のCLIは既存 `.sealgraph` のformat4に対してstatus/fsckをFORMAT4_REQUIRES_MIGRATIONで拒否した。読み取り専用 `sealgraph migrate extract --source-format 4 --format universal-blob-v1` は成功。

抽出内容：26 Seals、25 content objects、10 REFs、タグ0。抽出SHA-256：`af7dec43b68eb60762c632d61a486d4e87f7e80f5774808040e750f61f32dd2e`。一時ファイル `/tmp/purposebus-sealgraph-format4-export.json` は検査用であり、永続バックアップではない。

抽出は41件の観測済みparent assertionsを投影し、次の3件のunobserved parent assertionsを新形式の意味から落とす警告を出した。旧Sealや元データを削除したという意味ではないが、履歴の解釈が変わるため所有者の判断が必要。

- child `424e40fc3765dd4239b0503187c7ab77d670a3765cba78d99c381be6a11c5cba` → parent `43a6968077d07ca3d9d64ef2f94bdbbf2afe4e79ba1e4c7ab41e88f2f3176fa7`
- child `6e7645955d28f6096991ccb39bdf7c7d1944e04360aaa99dc83654f66aff5ce5` → parent `424e40fc3765dd4239b0503187c7ab77d670a3765cba78d99c381be6a11c5cba`
- child `7c5a3c79bbdb9e0e7aec678fe3dcc2c3f4792f6704c2fffca0acceab24ca3250` → parent `6e7645955d28f6096991ccb39bdf7c7d1944e04360aaa99dc83654f66aff5ce5`

source bindings、cache、event logs、recovery journal、locks、temporary filesは抽出対象外。ローカルsource bindingsは必要なものを読み戻して明示的に再設定する候補とする。既存format4は変更していない。

## 提案する正規リポジトリ移行の範囲

1. 既存 `.sealgraph` を完全バックアップし、同一性を検証する。
2. 再抽出したスナップショットを隔離した空のディレクトリへloadする。import receiptを保存し、fsckと旧26 Seal/10 REFの同一性、上記意味変更を確認する。
3. import後のformatを実測し、必要に応じて公式の明示的format5→7移行を行う。必要なsource bindingsを復元し、source compareで確認する。
4. 旧 `.sealgraph` をバックアップとして残し、検証済みリポジトリへ切り替える。失敗時は切り替えず旧状態を保つ。
5. 以下の新しいREFへ今回対象だけを登録し、Seal内容のSHA-256、Cause、source比較、fsck、staleを読み戻す。旧MVP REFは更新しない。

これは提案であり、移行・切り替えは未実施。今回の登録指示から、旧履歴の意味変更を伴う移行承認を推定しない。

## 登録するprovenanceの関係

- `intent/purpose-lifecycle`：チャットから転記した所有者要求をroot境界として保存。転記であり原チャットの署名証明ではないことを記す。
- `requirements/purpose-lifecycle-r2`：固定r2本文。Causeは上記要求の正確なSeal。
- `evidence/purpose-lifecycle-tabletop-r2`：固定22ケース机上記録。Causeはr2要件の正確なSeal。独立レビューや実環境テストとは記録しない。
- `acceptance/purpose-lifecycle-r2`：固定承認記録。Causeはr2要件と机上記録の正確なSeals。

r1の履歴はファイルで保持し、新REFに旧MVPのrevision関係を捏造しない。Cause方向は下流の観測者から上流の根拠へ向ける。承認記録を要件のCauseにすると循環になるため採らない。将来の設計は確定要件と承認記録を根拠にできる。

SealGraphは内容同一性と記録されたprovenanceを検証する。要求の意味的正しさ、独立レビュー実施、実装完成、所有者権限の真正性をツールだけで証明しない。

## 残作業と次の判断

正規リポジトリ移行・検証・4 REF登録の内部工数は暫定0.5〜1.5時間、信頼度低。計画終点制約のため今回PERT IDは未登録。完了条件は検証済み正規SealGraphへの登録とCause/内容/整合の読み戻し。次の判断は、上記3件の意味変更と除外項目を認めてバックアップ・隔離移行・切り替えを実施するか。

## 移行・登録の実施結果

所有者指示「移行してください。時間がかかるようであれば、完全に作り直してOKです。」に基づき、再構築せず公式移行を実施した。format4を隔離loadしてformat5へ変換後、format5→7を実施。検証後に正規 `.sealgraph` へ切り替えた。

完全バックアップ・元データ・抽出・移行receipt・旧新ID対応表・検証結果：`/home/katsumata-m/purposebus-provenance-backups/20260930T152549`。完全バックアップ106ファイルのSHA-256一致を確認し、切り替え直前にも元データが変化していないことを確認した。

旧26 Sealすべての内容バイトと、旧10 REFすべてのHEADが対応表どおり移行されたことを独立読み戻しで確認。Seal IDは形式変更により変わるため `load-receipt.json` の `seal_mappings` で旧新を対応させる。IDそのものが不変とは扱わない。旧source bindings9件を復元した。既に開示した未観測parent assertions3件の投影差異は残り、元データは保存した。

| 新REF | Seal ID |
|---|---|
| `intent/purpose-lifecycle` | `d29ddf587fa9d110fb69e1411b3fdb92430cb91922ace92915c8fb69b6d6be80` |
| `requirements/purpose-lifecycle-r2` | `84bfb02b2415d930b4997cadcd248b399304e3aaee1dbc9d6447f07cd0ff5a94` |
| `evidence/purpose-lifecycle-tabletop-r2` | `3bdfe64ebc7fd9ffafc0fcf804671905837967673902e839d74767d9bb5524d9` |
| `acceptance/purpose-lifecycle-r2` | `5115763c7e077939532f38e473098dedd0c174e6114ae922f6034085ef7861f7` |

各新REFについて内容バイト/元ファイルSHA-256、exact Cause target、source=WORKFILE_MATCHES_HEADを確認。最終fsck=ok、30 Seals/14 REFs、未処理候補0、stale0。登録はローカルのみ。

## 検出した既存文書の差異

- `design/purposebus-codex-plugin`：`docs/codex-plugin.md` が保存済みHEAD内容と不一致。
- `design/purposebus-local-mvp`：`docs/architecture.md` が保存済みHEAD内容と不一致。
- `evidence/purposebus-local-mvp`：`docs/implementation-status.md` が保存済みHEAD内容と不一致。
- `evidence/purposebus-mvp-acceptance`：`docs/mvp-acceptance.md` が保存済みHEAD内容と不一致。
- `requirements/purposebus-mvp`：`docs/requirements.md` が保存済みHEAD内容と不一致。

旧Seal内容の移行一致は検証済みだが、現在の作業文書と過去Sealは一致しない。差異は修復せず報告対象として保持。stale0はCause上の状態であり、このworkfile差異がないことや文書の意味的正しさを証明しない。次の推奨確認はこの既存差分を読み取り専用でレビューし、旧REF更新が必要かを決めること。暫定内部工数0.5〜1時間、信頼度低。今回の移行と新4 REF登録の残作業0。
