# PurposeBus 0.2 alpha implementation status

Status: 0.2.0a0 accepted; 0.2.0a1 response-contract update under development

Date: 2026-09-04

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

The unaccepted 0.2.0a1 development candidate addresses GitHub Issue #1 and its
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
hardening. They do not justify a broker daemon or MCP server. A broader broker
candidate remains contingent on later evidence of a material problem that cannot
be addressed while preserving the direct model's simpler lifecycle.

The post-trial Plugin surface comparison is complete. It retains the public-CLI
Skill for the verified local Codex CLI and configured Desktop-to-WSL paths,
records other Codex and ChatGPT surfaces as unsupported, and leaves MCP,
workspace distribution, and public-directory publication outside the accepted
alpha scope. See
[the 2026-09-04 surface decision](codex-plugin-surface-decision-2026-09-04.md).

The accepted local alpha and the response-contract candidate retain durable
state schema version `1` and the direct SQLite design. They do not require a
state migration, broker daemon, or MCP server.
`T_BETA_REPLAN` is now the next planning task: it must select later work from
measured alpha evidence rather than treating the provisional beta package as
already accepted scope.

Remote transport, federation, competing consumers, exactly-once delivery,
automatic delegation, secret resolution, and cross-user authorization remain
explicit non-goals for this MVP.
