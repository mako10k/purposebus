# PurposeBus local MVP implementation status

Status: executable experiment

Date: 2026-08-31

## Implemented vertical slice

The prototype implements the normative entity model with a Python standard
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

## Experiment frontier

The direct-database approach remains an experiment. Real multi-agent trials
should measure poll latency, writer contention, heartbeat accuracy, usability of
purpose text, and whether durable broadcast is sufficient. A broker daemon is
the next architecture candidate only if those measurements expose a material
problem that cannot be addressed while preserving the direct model's simpler
lifecycle.

Remote transport, federation, competing consumers, exactly-once delivery,
automatic delegation, secret resolution, and cross-user authorization remain
explicit non-goals for this MVP.
