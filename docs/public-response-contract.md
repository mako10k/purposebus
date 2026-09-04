# PurposeBus public response contract

Status: 0.2.0a1 development candidate; not yet locally accepted

Date: 2026-09-04

## Boundary

PurposeBus exposes purpose-specific response projections. SQLite rows,
`Partition` storage members, and process-observation records are internal inputs,
not response objects. The allowlists in `src/purposebus/public.py` are the
executable field contract; an unknown persistence field is omitted unless it is
deliberately added to one of those projections.

Successful JSON documents use `purposebus.*.v2` and contain exactly these
top-level roles:

- `schema`: command-specific response identity;
- `actor`: the explicit acting Agent or Instance, or `null` for an operator read;
- `partition`: semantic routing context; and
- `result`: a command-specific response projection.

Errors remain `purposebus.error.v1`; this change does not alter their field
shape or exit-status contract.

## Partition context

The one authoritative top-level `partition` object contains:

| Field | Public purpose |
| --- | --- |
| `partition_id` | Stable logical routing identity |
| `path` | Canonical source path required by FR-001 |
| `source` | Resolution method: explicit path, Git worktree, or current directory |
| `display_name` | Human-oriented name derived from the canonical path |

`state_root`, Partition storage directory, and `database` are internal. They are
not emitted by ordinary JSON or human output. `status.result` does not repeat
the Partition object.

## Resource fields

The ordinary resource projections classify emitted fields as follows:

| Resource | Semantic and workflow fields |
| --- | --- |
| Agent | `agent_id`, `kind`, `description`, `capabilities`, `created_at`, `updated_at` |
| Instance | identity and objective; lifecycle, activity, heartbeat and lease; derived liveness and wait validity; creation and update times |
| Subscription and Request | identity, owner, topic, purpose, schema, durability, stored and effective state, expiry, correlation, creation and update times |
| Offer | identity, owner, topic, purpose, schema, stored and effective state, expiry, creation and update times |
| Message | identity, producer, topic, purpose, payload kind, artifact and correlation metadata, expiry, idempotency key, retention and advertisement state, creation time; deduplication and delivery count when publishing |
| Delivery | delivery, Message and Subscription identities; stored and effective state; lease and acknowledgement state; owner and workflow metadata; Message routing and correlation metadata; payload only for an explicit payload-bearing operation |
| Event | sequence and identity, entity and transition, actor, time, and deliberate event details |

The following persistence or observation values are not ordinary resource
fields:

- Message `command_digest` and stored `payload_text`;
- Instance host, boot identity, PID, process-start identity, their wait-loop
  equivalents, and raw wait interval or selector values; and
- Subscription, Message, and Delivery join columns used only to derive public
  state.

Derived `liveness`, `liveness_reason`, `wait_valid`, and `wait_reason` retain the
required semantic evidence without copying the underlying process-observation
record into every Instance response. `events` is the explicit non-payload
diagnostic history; its details are allowlisted per entity and event type, so a
new stored detail is not public until the response contract deliberately adds
it.

## Command-specific shapes

- Resource `list` commands return `result.items` plus `result.page`.
- `status` returns backend-neutral storage health, full counts, and a bounded
  Instance collection. Partition context exists only at document top level.
- `match` returns bounded `matches` and `unmet` collections. Availability is a
  property of each match; an additional duplicate `unavailable` collection is
  not emitted. Candidate Offers inside an unmet item are independently bounded.
- `next` returns one projected Instance plus bounded action and warning
  collections.
- `poll` returns `result.deliveries`. Each leased Delivery contains an exact
  `next.command` acknowledgement step and states that the same Partition and
  state configuration must be reused.
- `message show --include-payload` and `poll` are the payload-bearing response
  surfaces. Message list, Delivery list, status, next, match, and events do not
  emit payload content.

Human output has command-specific rendering for the same identities, states,
reasons, counts, payload-bearing operations, and next commands. It is not a
recursive dump of the JSON document. Full integration detail remains available
through `--format json`.

## Bounded collection contract

Resource lists, status Instances, match results, and next actions default to
100 returned items and reject limits outside `1..1000`. Each page reports
`limit`, `returned`, `total`, and `truncated`. This is a bounded-result contract,
not cursor pagination.

Unmet-match candidate lists default to 25 and reject limits outside `1..100`.
Poll retains its existing `1..100` lease bound. Event queries retain their
existing `1..1000` bound and stored history remains capped at 10,000 events.

`match` no longer serializes unavailable pairs twice. The underlying local
calculation may still inspect all active Subscriptions and Offers to classify
results; a future query-performance change must preserve the same bounded public
contract.

## Compatibility and state migration

PurposeBus 0.2.0a0 emitted `purposebus.*.v1` success documents whose shapes were
partly inherited from persistence rows. PurposeBus 0.2.0a1 changes the common
context, resource projections, collection shapes, human rendering, and receive
guidance, so it emits `purposebus.*.v2` instead of silently changing v1.

The SQLite state schema remains version `1`. Existing supported state is opened
without migration or mutation. This is an output-contract transition, not a
storage migration. Integrations, including the PurposeBus Codex Plugin, must
check the core version and v2 schema before using the new shapes.

## Receive guidance

A successful poll supplies the exact Delivery ID and acknowledgement command.
The command is not authority to acknowledge: the payload must first be handled
and the owning actor must remain the same. A normal `no_message` error now
suggests retrying the same poll context or using `next`; it remains a normal
empty or timeout outcome rather than a mutation failure.
