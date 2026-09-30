# Purpose r2 部分単位のCause連結

2026-09-30 / 完了

所有者の「Causeを部分単位で連結してください。」に基づき、確定本文を変えず、provenanceを以下へ変更した。

```
所有者要求・承認の該当部分（11 REF、root証拠境界）
    ↑ Cause
PL-01〜24（本文・Origin Traceを維持、Causeのみ改訂）
    ↑ Cause
状態表／最小フロー（2節）およびUC-01〜22（22 REF）
```

矢印は下流の観測者から上流の根拠へ向ける。共有された確定要件・結果・承認・要求の全文4 REFは承認時のスナップショットとしてHEADを維持する。旧部分Sealもimmutable履歴として保存する。PL世代の変更は、下流UC/節のCauseにexact previous targetを記録した。

## 根拠の意味と制約

root証拠は所有者要求の転記3部分、r2採用範囲1部分、確定選択7部分。各rootも全文ファイルからのexact Origin Traceを持つ。転記や承認の該当部分を出所境界として登録したもので、ツールによる本人認証や独立した事実検証ではない。

各PLにはr2採用範囲へのCauseを含める。個別の所有者発言で規定されていない詳細を、個別要求として捏造しないためである。この承認範囲は複数PLに共通するが、全文ファイルHEADをCauseにする形ではない。

UC→PLは当該机上会話で参照する意味上の対応であり、機械的な全挙動網羅証明ではない。UC間の文章参照をCauseとして逆向きに追加せず、観測対象の要件をCauseにする。古い全体承認ファイルをこの細分化へ再連結すると承認時の履歴が変わるため維持する。

ファイル全体の文字列変更だけでは部分HEADやCauseは自動更新されない。更新時はtrace compareで該当部分を確認し、意味変更があれば所有者判断に基づきその部分を改版する。SourceSnapshotは全文を保持するため、bindの観測先とimmutable起源・Cause・承認の意味を区別する。

## 検証

- 11根拠REF新規、24 PL REF改訂、22 UC REF新規、2節REF改訂：計59 REF。
- 各対象のexact Cause集合と内容bytesを読み戻し、PLと節のOrigin Mapが変更前と同じことを確認。
- r2要件/机上結果の全ファイルSHA-256と全文4 REFのHEADは変更なし。
- UC-14のtrace compareはPRESENT/complete、fsck=ok、115 Seals/73 REFs、stale=0。
- SealGraph更新はローカルのみ。実装・受理済み本文・既存5文書の差異は変更していない。

全ID・旧新対応・Cause一覧は [JSON記録](purpose-lifecycle-partial-causes.json)。前の `purpose-lifecycle-granular-seals.md` のID一覧は部分単位Cause変更前の履歴であり、現在のHEAD一覧は本記録を使用する。

## 部分対応一覧

| 対象 | CauseのREF |
|---|---|
| `requirements/purpose-lifecycle-r2/PL-01` | `authority/purpose-lifecycle-r2/accepted-scope`, `authority/purpose-lifecycle-r2/decision-1`, `intent/purpose-lifecycle/roles` |
| `requirements/purpose-lifecycle-r2/PL-02` | `authority/purpose-lifecycle-r2/accepted-scope`, `authority/purpose-lifecycle-r2/decision-1`, `intent/purpose-lifecycle/roles` |
| `requirements/purpose-lifecycle-r2/PL-03` | `authority/purpose-lifecycle-r2/accepted-scope`, `authority/purpose-lifecycle-r2/decision-1`, `authority/purpose-lifecycle-r2/decision-7`, `intent/purpose-lifecycle/roles` |
| `requirements/purpose-lifecycle-r2/PL-04` | `authority/purpose-lifecycle-r2/accepted-scope`, `authority/purpose-lifecycle-r2/decision-2`, `intent/purpose-lifecycle/dialogue` |
| `requirements/purpose-lifecycle-r2/PL-05` | `authority/purpose-lifecycle-r2/accepted-scope`, `authority/purpose-lifecycle-r2/decision-2`, `intent/purpose-lifecycle/dialogue` |
| `requirements/purpose-lifecycle-r2/PL-06` | `authority/purpose-lifecycle-r2/accepted-scope`, `authority/purpose-lifecycle-r2/decision-4`, `intent/purpose-lifecycle/roles` |
| `requirements/purpose-lifecycle-r2/PL-07` | `authority/purpose-lifecycle-r2/accepted-scope`, `authority/purpose-lifecycle-r2/decision-3`, `intent/purpose-lifecycle/roles` |
| `requirements/purpose-lifecycle-r2/PL-08` | `authority/purpose-lifecycle-r2/accepted-scope`, `authority/purpose-lifecycle-r2/decision-3`, `intent/purpose-lifecycle/roles` |
| `requirements/purpose-lifecycle-r2/PL-09` | `authority/purpose-lifecycle-r2/accepted-scope`, `authority/purpose-lifecycle-r2/decision-5`, `intent/purpose-lifecycle/roles` |
| `requirements/purpose-lifecycle-r2/PL-10` | `authority/purpose-lifecycle-r2/accepted-scope`, `authority/purpose-lifecycle-r2/decision-5`, `authority/purpose-lifecycle-r2/decision-6`, `intent/purpose-lifecycle/roles` |
| `requirements/purpose-lifecycle-r2/PL-11` | `authority/purpose-lifecycle-r2/accepted-scope`, `authority/purpose-lifecycle-r2/decision-1`, `intent/purpose-lifecycle/roles` |
| `requirements/purpose-lifecycle-r2/PL-12` | `authority/purpose-lifecycle-r2/accepted-scope`, `authority/purpose-lifecycle-r2/decision-4`, `intent/purpose-lifecycle/roles` |
| `requirements/purpose-lifecycle-r2/PL-13` | `authority/purpose-lifecycle-r2/accepted-scope`, `authority/purpose-lifecycle-r2/decision-7`, `intent/purpose-lifecycle/roles` |
| `requirements/purpose-lifecycle-r2/PL-14` | `authority/purpose-lifecycle-r2/accepted-scope`, `authority/purpose-lifecycle-r2/decision-7`, `intent/purpose-lifecycle/roles` |
| `requirements/purpose-lifecycle-r2/PL-15` | `authority/purpose-lifecycle-r2/accepted-scope`, `intent/purpose-lifecycle/environments` |
| `requirements/purpose-lifecycle-r2/PL-16` | `authority/purpose-lifecycle-r2/accepted-scope`, `authority/purpose-lifecycle-r2/decision-2`, `intent/purpose-lifecycle/dialogue` |
| `requirements/purpose-lifecycle-r2/PL-17` | `authority/purpose-lifecycle-r2/accepted-scope`, `authority/purpose-lifecycle-r2/decision-2`, `intent/purpose-lifecycle/dialogue` |
| `requirements/purpose-lifecycle-r2/PL-18` | `authority/purpose-lifecycle-r2/accepted-scope`, `authority/purpose-lifecycle-r2/decision-2`, `intent/purpose-lifecycle/dialogue` |
| `requirements/purpose-lifecycle-r2/PL-19` | `authority/purpose-lifecycle-r2/accepted-scope`, `authority/purpose-lifecycle-r2/decision-2`, `authority/purpose-lifecycle-r2/decision-4`, `intent/purpose-lifecycle/dialogue` |
| `requirements/purpose-lifecycle-r2/PL-20` | `authority/purpose-lifecycle-r2/accepted-scope`, `authority/purpose-lifecycle-r2/decision-2`, `intent/purpose-lifecycle/dialogue` |
| `requirements/purpose-lifecycle-r2/PL-21` | `authority/purpose-lifecycle-r2/accepted-scope`, `authority/purpose-lifecycle-r2/decision-2`, `intent/purpose-lifecycle/dialogue` |
| `requirements/purpose-lifecycle-r2/PL-22` | `authority/purpose-lifecycle-r2/accepted-scope`, `authority/purpose-lifecycle-r2/decision-2`, `authority/purpose-lifecycle-r2/decision-7`, `intent/purpose-lifecycle/dialogue` |
| `requirements/purpose-lifecycle-r2/PL-23` | `authority/purpose-lifecycle-r2/accepted-scope`, `authority/purpose-lifecycle-r2/decision-5`, `authority/purpose-lifecycle-r2/decision-6`, `intent/purpose-lifecycle/dialogue` |
| `requirements/purpose-lifecycle-r2/PL-24` | `authority/purpose-lifecycle-r2/accepted-scope`, `authority/purpose-lifecycle-r2/decision-4`, `intent/purpose-lifecycle/dialogue` |
| `evidence/purpose-lifecycle-tabletop-r2/UC-01` | `requirements/purpose-lifecycle-r2/PL-01`, `requirements/purpose-lifecycle-r2/PL-02`, `requirements/purpose-lifecycle-r2/PL-04`, `requirements/purpose-lifecycle-r2/PL-06`, `requirements/purpose-lifecycle-r2/PL-07`, `requirements/purpose-lifecycle-r2/PL-08`, `requirements/purpose-lifecycle-r2/PL-16` |
| `evidence/purpose-lifecycle-tabletop-r2/UC-02` | `requirements/purpose-lifecycle-r2/PL-01`, `requirements/purpose-lifecycle-r2/PL-04`, `requirements/purpose-lifecycle-r2/PL-05`, `requirements/purpose-lifecycle-r2/PL-09`, `requirements/purpose-lifecycle-r2/PL-21` |
| `evidence/purpose-lifecycle-tabletop-r2/UC-03` | `requirements/purpose-lifecycle-r2/PL-02`, `requirements/purpose-lifecycle-r2/PL-03`, `requirements/purpose-lifecycle-r2/PL-07`, `requirements/purpose-lifecycle-r2/PL-08` |
| `evidence/purpose-lifecycle-tabletop-r2/UC-04` | `requirements/purpose-lifecycle-r2/PL-02`, `requirements/purpose-lifecycle-r2/PL-04`, `requirements/purpose-lifecycle-r2/PL-12` |
| `evidence/purpose-lifecycle-tabletop-r2/UC-05` | `requirements/purpose-lifecycle-r2/PL-01`, `requirements/purpose-lifecycle-r2/PL-04`, `requirements/purpose-lifecycle-r2/PL-05`, `requirements/purpose-lifecycle-r2/PL-06`, `requirements/purpose-lifecycle-r2/PL-19`, `requirements/purpose-lifecycle-r2/PL-20` |
| `evidence/purpose-lifecycle-tabletop-r2/UC-06` | `requirements/purpose-lifecycle-r2/PL-03`, `requirements/purpose-lifecycle-r2/PL-06`, `requirements/purpose-lifecycle-r2/PL-07`, `requirements/purpose-lifecycle-r2/PL-12`, `requirements/purpose-lifecycle-r2/PL-18` |
| `evidence/purpose-lifecycle-tabletop-r2/UC-07` | `requirements/purpose-lifecycle-r2/PL-07`, `requirements/purpose-lifecycle-r2/PL-08`, `requirements/purpose-lifecycle-r2/PL-09`, `requirements/purpose-lifecycle-r2/PL-10`, `requirements/purpose-lifecycle-r2/PL-22` |
| `evidence/purpose-lifecycle-tabletop-r2/UC-08` | `requirements/purpose-lifecycle-r2/PL-03`, `requirements/purpose-lifecycle-r2/PL-09`, `requirements/purpose-lifecycle-r2/PL-12`, `requirements/purpose-lifecycle-r2/PL-15`, `requirements/purpose-lifecycle-r2/PL-23` |
| `evidence/purpose-lifecycle-tabletop-r2/UC-09` | `requirements/purpose-lifecycle-r2/PL-06`, `requirements/purpose-lifecycle-r2/PL-07`, `requirements/purpose-lifecycle-r2/PL-08`, `requirements/purpose-lifecycle-r2/PL-11` |
| `evidence/purpose-lifecycle-tabletop-r2/UC-10` | `requirements/purpose-lifecycle-r2/PL-11`, `requirements/purpose-lifecycle-r2/PL-12`, `requirements/purpose-lifecycle-r2/PL-13`, `requirements/purpose-lifecycle-r2/PL-22`, `requirements/purpose-lifecycle-r2/PL-24` |
| `evidence/purpose-lifecycle-tabletop-r2/UC-11` | `requirements/purpose-lifecycle-r2/PL-10`, `requirements/purpose-lifecycle-r2/PL-18`, `requirements/purpose-lifecycle-r2/PL-23` |
| `evidence/purpose-lifecycle-tabletop-r2/UC-12` | `requirements/purpose-lifecycle-r2/PL-01`, `requirements/purpose-lifecycle-r2/PL-09`, `requirements/purpose-lifecycle-r2/PL-13`, `requirements/purpose-lifecycle-r2/PL-15`, `requirements/purpose-lifecycle-r2/PL-16` |
| `evidence/purpose-lifecycle-tabletop-r2/UC-13` | `requirements/purpose-lifecycle-r2/PL-01`, `requirements/purpose-lifecycle-r2/PL-02`, `requirements/purpose-lifecycle-r2/PL-07`, `requirements/purpose-lifecycle-r2/PL-08`, `requirements/purpose-lifecycle-r2/PL-16`, `requirements/purpose-lifecycle-r2/PL-17`, `requirements/purpose-lifecycle-r2/PL-18` |
| `evidence/purpose-lifecycle-tabletop-r2/UC-14` | `requirements/purpose-lifecycle-r2/PL-05`, `requirements/purpose-lifecycle-r2/PL-17`, `requirements/purpose-lifecycle-r2/PL-19`, `requirements/purpose-lifecycle-r2/PL-20` |
| `evidence/purpose-lifecycle-tabletop-r2/UC-15` | `requirements/purpose-lifecycle-r2/PL-01`, `requirements/purpose-lifecycle-r2/PL-06`, `requirements/purpose-lifecycle-r2/PL-18`, `requirements/purpose-lifecycle-r2/PL-19` |
| `evidence/purpose-lifecycle-tabletop-r2/UC-16` | `requirements/purpose-lifecycle-r2/PL-01`, `requirements/purpose-lifecycle-r2/PL-04`, `requirements/purpose-lifecycle-r2/PL-18`, `requirements/purpose-lifecycle-r2/PL-21` |
| `evidence/purpose-lifecycle-tabletop-r2/UC-17` | `requirements/purpose-lifecycle-r2/PL-07`, `requirements/purpose-lifecycle-r2/PL-08`, `requirements/purpose-lifecycle-r2/PL-17`, `requirements/purpose-lifecycle-r2/PL-22` |
| `evidence/purpose-lifecycle-tabletop-r2/UC-18` | `requirements/purpose-lifecycle-r2/PL-04`, `requirements/purpose-lifecycle-r2/PL-05`, `requirements/purpose-lifecycle-r2/PL-20`, `requirements/purpose-lifecycle-r2/PL-21` |
| `evidence/purpose-lifecycle-tabletop-r2/UC-19` | `requirements/purpose-lifecycle-r2/PL-07`, `requirements/purpose-lifecycle-r2/PL-10`, `requirements/purpose-lifecycle-r2/PL-17`, `requirements/purpose-lifecycle-r2/PL-23` |
| `evidence/purpose-lifecycle-tabletop-r2/UC-20` | `requirements/purpose-lifecycle-r2/PL-06`, `requirements/purpose-lifecycle-r2/PL-12`, `requirements/purpose-lifecycle-r2/PL-24` |
| `evidence/purpose-lifecycle-tabletop-r2/UC-21` | `requirements/purpose-lifecycle-r2/PL-04`, `requirements/purpose-lifecycle-r2/PL-06`, `requirements/purpose-lifecycle-r2/PL-12`, `requirements/purpose-lifecycle-r2/PL-21` |
| `evidence/purpose-lifecycle-tabletop-r2/UC-22` | `requirements/purpose-lifecycle-r2/PL-06`, `requirements/purpose-lifecycle-r2/PL-18`, `requirements/purpose-lifecycle-r2/PL-24` |
| `requirements/purpose-lifecycle-r2/section-states` | `requirements/purpose-lifecycle-r2/PL-01`, `requirements/purpose-lifecycle-r2/PL-02`, `requirements/purpose-lifecycle-r2/PL-03`, `requirements/purpose-lifecycle-r2/PL-05`, `requirements/purpose-lifecycle-r2/PL-06`, `requirements/purpose-lifecycle-r2/PL-07`, `requirements/purpose-lifecycle-r2/PL-08`, `requirements/purpose-lifecycle-r2/PL-09`, `requirements/purpose-lifecycle-r2/PL-11`, `requirements/purpose-lifecycle-r2/PL-12` |
| `requirements/purpose-lifecycle-r2/section-interactions` | `requirements/purpose-lifecycle-r2/PL-01`, `requirements/purpose-lifecycle-r2/PL-02`, `requirements/purpose-lifecycle-r2/PL-04`, `requirements/purpose-lifecycle-r2/PL-06`, `requirements/purpose-lifecycle-r2/PL-07`, `requirements/purpose-lifecycle-r2/PL-08`, `requirements/purpose-lifecycle-r2/PL-16`, `requirements/purpose-lifecycle-r2/PL-17`, `requirements/purpose-lifecycle-r2/PL-21` |

今回の残作業0。次の設計/検証では、その内容を支えるPLのexact SealをCauseに指定する。承認や意味的正しさをCauseの存在だけで判断しない。
