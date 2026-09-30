# PurposeBus 1.0.0 implementation status

Status: local 1.0.0 release package verified; publication authorization pending

Date: 2026-09-08

## Implemented vertical slice

The alpha implements the normative entity model with a Python standard
library CLI and one SQLite WAL database per canonical Partition. It includes:

- Agent registry and Instance start, heartbeat, stop, liveness, and wait state;
- purpose-bearing Subscriptions, correlation-constrained one-shot Requests,
  Offers, fact-rich matching, and classified unmet demand;
- exact, `+`, and trailing `#` topic matching with absent-or-exact schemas;
- atomic durable fan-out, bounded leases, explicit acknowledgement, expiry,
  five-attempt dead-lettering, and retained current Messages;
- producer-scoped publish idempotency plus read-only Message lookup before a
  retry;
- explicit mutation actors and owner-family checks, including direct Agent
  acknowledgement for offline mailboxes;
- explicit poll-target validation that distinguishes an empty queue, a missing
  Subscription, and an ownership mismatch before wait state or delivery work;
- human and JSON output with Partition and actor context, task-oriented help,
  `status`, `events`, and purpose-bearing read-only `next` navigation; and
- project Partition isolation, private same-user state, and no network listener.

Every process invocation opens the durable store independently. Consequently,
the restart tests exercise recovery across separate CLI processes rather than
depending on an in-memory broker.

## Bounded behavior

| Resource | MVP bound | Observable result |
| --- | --- | --- |
| Inline payload | 64 KiB UTF-8 | invalid-input error |
| One poll result | 1 to 100 Deliveries | invalid-input error outside the range |
| One blocking poll | explicit caller timeout | `no_message` exit after the deadline |
| Delivery processing | 5 leases | `dead_letter` after the fifth lease times out |
| Event query | 1 to 1,000 rows | invalid-input error outside the range |
| Stored event history | latest 10,000 rows | `status.storage.events_pruned` records removals |
| Resource list, status Instance, and next-action output | default 100, caller range 1 to 1,000 | page metadata reports total and truncation |
| Match output | default 100 results; 25 candidates per unmet need | independent result and candidate bounds |

## Acceptance evidence

The isolated CLI suite covers the twelve acceptance conditions in
`docs/requirements.md`, including independent fan-out, lease recovery, killed
wait projection, PID reuse, direct human offline mailbox acknowledgement,
Request correlation for ordinary and retained Messages, actor ownership denial,
artifact metadata placement, retained and ordinary Partition isolation,
idempotent read-back, `next` explanations, discoverable help, concurrency,
private permissions, and fail-closed unknown schemas.

Run the evidence locally with:

```sh
make check
```

The condition-to-test traceability and clean-install smoke procedure are in
[the MVP acceptance map](mvp-acceptance.md). The owner accepted candidate
`09cdd3e491587380484ab1d2a9a36b1bfacea5f9`; receipt
`RCPT_MVP_0_1_OWNER_20260831` records that decision in the roadmap. Publication
and production readiness remain separate decisions.

Inspection commands are verified against logical table snapshots so incidental
SQLite WAL or shared-memory sidecars are not mistaken for coordination-state
mutation.

The 0.2.0 alpha adds the bounded ownership diagnostic, state-reopen check,
core/Plugin compatibility assertions, isolated package evidence, and new-session
Plugin permission checks. Its exact candidate hashes and results are in
[the alpha acceptance record](alpha-acceptance-2026-09-04.md).

The owner-accepted 0.2.0a1 beta candidate addresses GitHub Issue #1 and its
public-surface audit. It separates public serializers from persistence records,
removes storage paths, command digests, and raw process observations from
ordinary output, introduces bounded command-specific collections, removes the
duplicate match and status projections, provides task-oriented human output,
and makes poll-to-ack guidance explicit. These incompatible successful response
shapes use `purposebus.*.v2`; errors and durable state remain schema version `1`.
See [the public response contract](public-response-contract.md).

## Alpha result and beta frontier

The first real local multi-agent trial is complete. It exercised raw CLI and
fresh-session Codex Plugin paths with two AI Agents and one human Agent, including
provider discovery, correlated response, durable fan-out, failure recovery,
offline mailbox acknowledgement, poll latency, writer contention, heartbeat
projection, purpose text, identity, and permission behavior. The evidence and
accepted post-MVP scope are recorded in
[the 2026-09-04 trial report](local-multi-agent-trial-2026-09-04.md).

The bounded results retain the direct-database approach and Skill-only Plugin,
keep correlated Requests and explicit acknowledgement alongside durable
broadcast, and select ownership diagnostics and regression coverage for alpha
hardening. They did not by themselves justify a broker daemon or MCP server. A
broader broker candidate remains contingent on later evidence of a material
problem that cannot be addressed while preserving the direct model's simpler
lifecycle.

The post-trial Plugin surface comparison is complete. It retains the public-CLI
Skill for the verified local Codex CLI and configured Desktop-to-WSL paths,
records other Codex and ChatGPT surfaces as unsupported, and leaves MCP,
workspace distribution, and public-directory publication outside the accepted
alpha scope. See
[the 2026-09-04 surface decision](codex-plugin-surface-decision-2026-09-04.md).

The accepted local alpha and the response-contract candidate retain durable
state schema version `1` and the direct SQLite design. They do not require a
state migration or broker daemon.

The 2026-09-08 beta replan selects an additive, local stdio, read-only MCP
adapter as the first new slice for the cross-client coordination requirement.
The adapter is isolated under `integrations/purposebus_mcp`, pins its MCP 2.x
and schema dependencies only there, and calls the public CLI for six observation
and guidance operations. It does not change the core dependency set, state
schema, direct SQLite implementation, or Skill-only Plugin manifest. Its exact
boundary is [the MCP contract](mcp-readonly-contract.md) and
[ADR-0001](adr/0001-add-local-read-only-mcp.md).

The sibling `integrations/purposebus_codex_controller` package is a non-runnable
policy skeleton. It records a future first-proof ceiling of one Codex session,
read-only filesystem, no network, no subagents, and no experimental App Server
API. No Codex lifecycle method, PurposeBus write, Connector invocation, client
profile installation, or agent launch is implemented or claimed by this slice.

`T_BETA_REPLAN` freezes this bounded Phase 0 through Phase 2 scope. The beta
build evidence is complete and recorded in
[the 2026-09-08 beta candidate record](beta-readonly-mcp-acceptance-2026-09-08.md).
`T_BETA_BUILD` is complete and `V0_5_BETA_ACCEPTED` is reached and accepted.
The accepted scope preserves separate acceptance gates for Codex lifecycle
control, PurposeBus mutations, Plugin or profile installation, remote transport,
and publication.

`T_RC_HARDENING` is complete, and owner receipt
`RCPT_V0_9_RC_OWNER_20260908` accepts the local RC contract at
`V0_9_RC_ACCEPTED`. Its machine-readable compatibility boundary, reproducible
artifact procedure, isolated core and Plugin transition checks, bounded-load
probe, and corrupt-state recovery procedure are documented in
[the RC hardening runbook](rc-hardening.md) and
[ADR-0002](adr/0002-freeze-rc-compatibility-and-provenance.md). Publication and
release authorization remain separate states.

`T_V1_PLUGIN_PACKAGE` is locally complete. Plugin
`1.0.0+codex.20260908092104` remains Skill-only, declares exact core
compatibility `==0.2.0a1`, and passes deterministic packaging, isolated
install/remove, raw CLI fallback, and new Codex CLI session evaluations for
direct, indirect, follow-up, negative, cross-host boundary, and full correlated
request-response behavior. See [the Plugin 1.0 package contract](plugin-v1-package.md)
and [candidate evidence](plugin-v1-candidate-evidence-2026-09-08.md). The active
Plugin profile remains at its prior installed version; no Desktop GUI run,
publication, commit, push, release, deployment, MCP addition, or Connector use
is claimed.

`T_V1_RELEASE_PREP` freezes core `1.0.0`, release Plugin
`1.0.0+codex.20260908103255`, the optional MCP adapter's exact core check,
public v2 and state-schema 1 compatibility, reproducible package artifacts,
predecessor rollback material, and a repeated exact fresh-session matrix. See
[the release preparation runbook](v1-release-prep.md). The candidate has no
commit, tag, or server-side revision yet; all publication destinations and
writes remain behind `G_V1_RELEASE_AUTHORIZATION`.

Remote transport, federation, competing consumers, exactly-once delivery,
automatic delegation, secret resolution, and cross-user authorization remain
explicit non-goals for this MVP.
