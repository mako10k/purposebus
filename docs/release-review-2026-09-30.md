# PurposeBus 1.0.0 再レビューとリリース計画

対象は `/home/katsumata-m/purposebus` の core 1.0.0、読み取り専用MCP
0.1.0a0、Skill形式Plugin `1.0.0+codex.20260908103255`。
現在の基準コミットは `2a2b3a68c8f44a4107268e4fd51949106a37d486`。
要件 `docs/requirements.md`、公開応答契約、Accepted ADR-0001/0002を適用する。

## レビュー境界と結果

現段階で求めるものは、既存要件への実装適合、ローカル配布物の再現性、
既存state schema 1の再利用・rollback、公開する候補の識別と配布後の読戻し。
独立レビューはコードと契約を読み取りで確認し、次の2件を再現した。

| 分類 | 現行義務 | 観測 | 修正・検証条件 |
| --- | --- | --- | --- |
| INSIDE | FR-001：cwdを含むcanonical Git worktreeを既定Partitionとする | GIT_WORK_TREE=/tmpで別Partitionを選ぶ | Git環境の上書きを除外し、実際のcwdを包含するrootを選ぶ。独立した2個のGit repositoryとnested cwdでCLI回帰確認 |
| INSIDE | CLI-004：無効入力を構造化診断と終了状態で区別する | 巨大durationでinfまたは日時overflowを起こす | 非有限値を拒否し、日時範囲外をInvalidInputとする。poll・subscription・publishをCLIで確認し、論理stateが不変であることを照合 |
| OUTSIDE | ADR-0001の後続controller phase | controllerは制約のみの非実行package | 今回の受入対象に起動・停止・委任を追加しない。将来は上位要件と設計から扱う |
| BOUNDARY_DISPUTE | 公開先・ref・visibility・最大書込み | 現行release契約では未指定 | exact候補・配布物と一緒にownerの判断に戻す |

## 修正設計

要件から基本設計への対応：Partition解決は `partition` が所有し、値の検証と
日時正規化は `util` が所有する。CLIの既存InvalidInput処理とtransaction rollback
を利用して、公開schemaとdurable schemaを維持する。

詳細設計：Git discovery子processへ渡す環境からGIT_変数を除外し、返されたrootが
物理cwdを含むことも確認する。durationのfloat変換では有限性を検証し、日時加算と
UTC変換の表現範囲外をInvalidInputへ変換する。新たな待機上限値は発明しない。

既存9月8日契約・証拠は履歴として保持する。新しい契約
`release/v1-20260930-contract.json` で修正後の重要ファイルと証拠を固定する。
Pluginのファイル自体は変更せず、既存版のidentityを保つ。

## 正本PERTの再計画

目的：人・AI agentが公開されたexact packageを新規導入し、同じhost・userの
明示Partitionで既存CLI契約を利用できること。

`T_V1_REVALIDATE_20260930` → `G_V1_RELEASE_AUTHORIZATION` →
`T_PUBLISH_V1_0_0` → `V1_0_0_RELEASED` を正本roadmapで管理する。

1. 2件の修正、公開CLI回帰、独立した変更レビューを完了する。
2. 修正候補のsource archive、core/MCP/controller wheels、Plugin ZIPを再構築し、
   二重build、core upgrade/rollback、破損state、並行読取、隔離Plugin transitionを確認する。
3. current coreを使う新規Plugin会話とinstalled MCPを確認し、結果をexact artifactへ紐付ける。
4. exact候補、公開先、branch/tag、assets、visibility、最大書込みをowner判断へ提示する。
5. 指定された公開を一度実施し、server refと配布物hashを独立読戻しする。
6. 実際に公開されたcoreを隔離環境へ導入してrequest-response-ackを確認する。

想定公開案は公開GitHub repository `mako10k/purposebus` の1.0.0 Releaseと
既存repo marketplaceによるPlugin配布。PyPI、public Plugin Directory、active-profile
installation、mainへのmergeは公開案の選択に含めるかをownerが決める。

既存候補の即時公開は不具合が残るため採らない。controllerやremote transportの追加は
Accepted scopeを変更するため別要件の判断に戻す。

残内部工数の初期agent見積り：修正・検証・公開候補固定2〜6時間、公開・読戻し・
新規導入確認2〜6時間、計4〜12時間、信頼度低。外部承認待ちは別で期限不明。
PERTの宣言velocity 1p/日には実測根拠を取得できず、forecastの2.167日は採用しない。
新規taskの開始・完了・active timeを測定してobserve-velocityを更新する。

## 残るリスクと復旧選択

今回の確認対象はLinux/WSLのローカル同一user。native Desktop GUI、cloud、別host、
別user、署名、registry・public directoryの審査は未確認。別surfaceを今回のrelease義務へ
追加する場合は、その要件・工数・検証をowner判断で再計画する。

実運用の障害・誤Partitionへの実データ書込みは今回観測していないので、live stateの
復旧は必要と判断していない。改善は公開前の修正と隔離stateの回帰確認とする。
package rollback材料は既存0.2.0a1 coreとpredecessor Plugin。公開結果が曖昧な場合は
再送せずserver objectを読み取り、既存objectとの一致・不一致・不存在を識別する。
公開後の削除・tag移動・rollbackは別途対象と作用を固定してowner判断を得る。
