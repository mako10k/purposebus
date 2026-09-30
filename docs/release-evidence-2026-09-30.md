# PurposeBus 1.0.0 再検証記録（2026-09-30）

対象：core 1.0.0、Plugin `1.0.0+codex.20260908103255`、read-only MCP 0.1.0a0、
非実行controller policy 0.0.0a0。公開対象の最終Git revisionとassetsは後続の
凍結・owner判断で結び付ける。この文書はsource snapshotから除外する。

## 確認済み

- 独立レビューでFR-001の暗黙Partition誤解決とCLI-004のduration overflowを再現。
  修正後の読み取り再レビューで両INSIDEブロッカー解消を確認した。
- 公開CLI回帰で、GIT_WORK_TREE・GIT_DIR・GIT_CONFIG環境の影響を排除し、
  大きなwait・expiryを `purposebus.error.v1` / `invalid_input` / exit 2として返す。
  エラー前後の論理SQLite stateは一致した。実運用被害は観測していないためlive復旧は不要。
- 修正候補のcore source suite 67件成功、三種wheelの二重build一致、Plugin ZIP決定性、
  core 0.2.0a1→1.0.0→0.2.0a1→1.0.0のstate schema 1保持を確認した。
- 破損stateのfail-closed・破損bytes保持・別state rootへの隔離復旧、20プロセス/4workerの
  bounded read、隔離Plugin upgrade/remove/reinstall/rollbackを確認した。
- current core wheel SHA-256：
  `0ef17df40c1b73916be6d4dbc14352d8552e2f777c8fdc80b373d2c2f078e175`。
  新規Plugin会話評価とinstalled-package試験のwheelは同じhashである。
- wheelを導入した環境のMCP 14件、controller制約2件が成功した。MCP stdio子processも
  installed packageを使用した。依存は既存のMCP 2.2.0/Pydantic 2.13.5をlocal .pthで供給した。
  package indexからの新規依存解決を確認したとは扱わない。
- 新規Plugin必須5ケース：direct request-response（10変更、fulfilled/acked）、同じ会話の
  follow-up、live fixtureでのindirect status/registry/match/next（変更0）、negative（323、
  PurposeBus呼出0）、cross-host拒否（PurposeBus呼出0）が成功した。
  全必須ケースでworktime読取完了を確認し、使用ログの全hashを親agentが照合した。
- direct Request `current-request-1` / correlation `corr-current-20260930` /
  Message `msg_5d5dcf8a83ef41efbcc9161260c7262a` /
  Delivery `del_766234100c5a447fa10b75ff6437583b` は独立した公開CLI読戻しで
  fulfilled/ackedを確認した。
- 隔離Plugin・marketplaceの削除後の不存在を確認した。

## 限界・除外した試行

初回harnessはshared worktime lockに書込みできず、coordination変更0で終了した。
必要なlock directoryだけをsandboxに追加した新規ケースは読取り前提を満たした。
元のindirectはstale Instanceに対するSkillのlive境界に従いnextを省略したため、完全な
live workflow証拠から除外した。stale nextの補足はcoreの観測として記録し、別の1h lease
fixture（監査後setup7変更を各1回）でPluginのlive workflowを確認した。
最初のnegativeはworktime command完了の証拠がなく除外し、新規会話で完了を確認した。
これらの不足・失敗を成功ケースに合算していない。

共有Codex config hashは準備時 `9944c82c489aa746942a1a7050e9fc657aa02a1a950225fae5d65dc5bfff2a03`
から `66f562fc001da8f4409842f9c76018995d933c9109d4e6b7e8b1449114eff627` へ変化した。
変更元は未確認。評価invocationの隔離CODEX_HOMEを確認し、共有configの復旧は行っていない。
「共有profileは不変」という証明には使わない。隔離test内の操作と全体の共有状態を区別する。

native Desktop GUI、cross-host/cross-user、remote transport、public Plugin Directory、
package registry publication、signing、実際の公開後の新規導入は未確認である。
最終source/asset凍結とownerの公開範囲決定、公開後のserver ref・asset hash・clean-install
読戻しが残る。公開受益者への今回の実現価値は現時点で0、検証済み候補は将来価値への寄与。

## 証拠と計測

正本PERTは `plans/purposebus-roadmap.pert`。
今回のtask `T_V1_REVALIDATE_20260930` 開始：2026-09-30 11:18:58 JST。
必須matrixの完了記録：2026-09-30 11:44:24 JST。
task完了：2026-09-30 11:49:59 JST。task active timeは1861/3600h（31分1秒）を
標準CLIで記録した。taskのactive期間であり、並行agentのperson-hours合計ではない。
observe-velocityを再実行したが、非対応過去version、未認識baseline/sequenceにより値は未取得。
Git candidate記録後にもう一度観測する。person-hoursは未観測のため推測で埋めていない。
過去履歴にunsupported_source_versionがあり、古い1p/日を実測速度と扱わない。

machine evidence：`release/v1-plugin-evaluations-20260930.json`、
`release/installed-package-evidence-20260930.json`、
`release/v1-20260930-contract.json`。
詳細ログはignored build directory内のまま保持し、sourceへ含めるのはhashと観測結果だけとする。
LLMThinkの再計画監査はfatal/error/warning=0、pending情報1。fixture setupのwarning1は
未確認の実行結果に関する制限として保持した。

次の推奨は `G_V1_RELEASE_AUTHORIZATION` のexact公開範囲をownerが決めること。
目的への寄与は、候補を新規導入可能な公開配布物にするための作用先の確定。
その後の `T_PUBLISH_V1_0_0` は公開・独立読戻し・公開wheel新規導入確認を完了条件とする。
暫定残内部工数は2〜6時間、信頼度低。外部の判断待ちは別で期限不明。
