# PurposeBus local 0.2 alpha architecture

Status: direct-store design retained through local alpha

Date: 2026-09-04

## Decision

The first executable MVP uses one SQLite database per resolved Partition and
direct CLI access. Blocking poll uses short, bounded read transactions with a
sleep between attempts; it does not hold a database transaction while waiting.

This remains an experiment, not a decision that PurposeBus will never have a
broker daemon. The direct design was selected first because it can test durable
delivery, concurrent client serialization, process-visible waits, restart
recovery, and operator value without introducing a second service lifecycle.
The bounded local trial and alpha verification found no material failure that
requires replacing this design, so it remains selected through the 0.2 alpha.

## Runtime shape

```text
Agent process
    |
    | purposebus command with explicit Agent or Instance identity
    v
PurposeBus CLI process
    |
    | short SQLite transaction / bounded poll loop
    v
XDG state root / partitions / PARTITION_ID / purposebus.sqlite3
```

Dynamic state is outside the project checkout. `PURPOSEBUS_STATE_DIR` provides an
explicit test and integration override. The default state root follows
`XDG_STATE_HOME`, falling back to `~/.local/state/purposebus`.

## Concurrency and durability

- SQLite foreign keys are enabled.
- Mutations use `BEGIN IMMEDIATE` and commit before reporting success.
- WAL mode permits readers while one writer serializes a mutation.
- Publication inserts the Message, the active Subscription snapshot, and all
  initial Delivery rows in one transaction.
- Subscriber leases permit at-least-once redelivery after expiry.
- Producer-scoped idempotency keys bind to a canonical command digest.

## Waiting and liveness

An Instance is a durable logical run record. It may optionally carry external
process evidence supplied by the integrating Agent. A blocking `poll` records
the polling CLI PID separately, heartbeats the Instance, and clears the wait on
normal return or interruption. If the polling CLI is killed, read-only status
invalidates the wait when the stored boot/PID/start tuple no longer identifies a
live process.

Activity and liveness remain separate projections. No-PID human Instances can
be alive from a current heartbeat, become stale after lease expiry, and become
dead only after an explicit stop.

## Security boundary

The MVP is same-host and same-OS-user only. State directories are mode `0700`
and regular database files are mode `0600`. There is no network listener.
Partition isolation is an application routing rule, not an OS authorization
boundary. Payloads must not contain raw secrets, and opaque references are not
resolved automatically.

## Experiment result and next decision

The CLI suite and local trial demonstrated:

- independent durable fan-out and acknowledgement;
- lease-expiry redelivery after client restart;
- visible, non-sticky blocking waits;
- project Partition isolation;
- deterministic read-only status and next actions; and
- acceptable behavior with concurrent local clients.

The observed ownership ambiguity was corrected in poll-target validation and
operator guidance; it was not caused by the lack of a broker. A broker daemon
becomes the next candidate only if later evidence shows that bounded polling,
heartbeat accuracy, contention, shared-state access, or lifecycle requirements
cannot be addressed while preserving the direct model's simplicity. That
decision belongs to `T_BETA_REPLAN`.
