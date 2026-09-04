# PurposeBus MVP requirements

Status: initial implementation baseline

Date: 2026-08-31

This document is the normative requirements source for the first PurposeBus
implementation. `MUST`, `MUST NOT`, `SHOULD`, and `MAY` are normative.

## 1. Objective

PurposeBus MUST provide a command-oriented, local-first coordination queue in which
human and AI agents can discover one another, declare purpose-bearing
information needs and offers, publish information, wait for durable delivery,
acknowledge it, and inspect instance state inside an explicit project
partition.

The MVP is successful when the use cases in `docs/use-cases.md` can be
demonstrated through public CLI commands and stable machine-readable results.

## 2. Core model

| Entity | Meaning | Required identity and state |
| --- | --- | --- |
| Agent | Stable logical human or AI participant within one Partition | `agent_id`, `kind`, description, capabilities |
| Instance | One concrete run or interactive presence of an Agent | `instance_id`, `agent_id`, partition, objective, lifecycle observations |
| Subscription | A declared need for matching information | `subscription_id`, owner, topic filter, purpose, durability, expiry |
| Offer | A declaration that information can currently be provided | `offer_id`, owner, topic filter, purpose, availability, expiry |
| Request | A one-shot, expiring Subscription with correlation | `request_id`, subscription identity, completion state |
| Message | Information published to one topic | `message_id`, producer, topic, purpose, payload or reference, timestamps |
| Delivery | Subscriber-specific durable delivery state | message and subscription IDs, state, attempt, lease, acknowledgement |
| Partition | The logical discovery and communication boundary | stable `partition_id`, canonical source, display name |

## 3. Invariants

### INV-001: Logical identity and process identity are separate

An Agent MAY have zero, one, or multiple Instances. Restarting an Agent MUST NOT
silently reuse an old Instance identity.

### INV-002: Activity and liveness are separate

The reported activity (`idle`, `busy`, `waiting`, `draining`, or `stopped`) MUST
be independent of observed liveness (`alive`, `stale`, `dead`, or `unknown`). A
waiting instance can be alive; an instance last declaring itself busy can be
stale or dead.

### INV-003: PID is an observation, not identity or authority

PID alone MUST NOT establish Instance identity or authorization. When local
process probing is available, PurposeBus MUST combine host identity, boot identity,
PID, and process start identity sufficiently to detect ordinary PID reuse. If
that evidence is unavailable, liveness MUST be `unknown` rather than guessed.

### INV-004: Offer and publish are separate

An Offer declares current ability or availability. It MUST NOT itself execute
work or publish a Message. A Message MAY exist without an Offer, and status MUST
make unadvertised publication distinguishable.

### INV-005: Coordination is not authorization

Registration, capability metadata, Offers, Subscriptions, Requests, Messages,
matches, and `next` results MUST NOT grant authority for unrelated local or
external actions.

### INV-006: Partition containment is the default

Discovery, matching, publication, and delivery MUST remain inside one resolved
Partition unless a future explicit bridge contract is introduced. The MVP MUST
NOT perform implicit cross-partition discovery or delivery.

### INV-007: A communication boundary is not an OS security boundary

PurposeBus MUST describe Partition containment as an application-level routing and
visibility rule. It MUST NOT claim that a Partition replaces filesystem
permissions, OS identity, a sandbox, or authorization.

## 4. Functional requirements

### FR-001: Partition resolution

- With no override, PurposeBus MUST resolve the canonical Git worktree root containing
  the current directory.
- Outside a Git worktree, PurposeBus MUST use the canonical current directory.
- `--partition PATH` MUST allow an explicit path-based Partition.
- Resolution MUST normalize symbolic and relative paths before deriving the
  stable Partition identity.
- Human and JSON status MUST expose the resolved identity and source path.

Dynamic queue state MUST be stored outside the project checkout under the
user's state directory. The implementation SHOULD follow the XDG state
directory convention and MUST protect state from other OS users using the
strongest normal same-user file permissions available on the platform.

### FR-002: Agent registry

PurposeBus MUST register, list, and show stable Agents inside the resolved Partition. A
registry record MUST include:

- an explicit `agent_id` that is unique within the Partition;
- `kind` with at least `human` and `ai`;
- a human-readable description;
- zero or more capability identifiers; and
- creation and last-update timestamps.

Capabilities describe relatively stable ability. Current objective and current
availability MUST remain Instance and Offer facts instead of being folded into
capabilities. The MVP MUST NOT expose an implicit cross-Partition global agent
registry. A human or AI participant MAY register the same explicit `agent_id`
separately in multiple Partitions, but those records remain independent.

### FR-003: Instance lifecycle

PurposeBus MUST start/register, heartbeat, stop, list, and inspect Instances. An active
record MUST contain an `instance_id`, owning `agent_id`, Partition, current
objective, activity, heartbeat timestamp, and lease expiry. Host, boot, PID, and
process-start observations MUST be recorded when available.

Existing agents MUST be able to self-register and heartbeat through commands;
launching the process through a PurposeBus wrapper MUST NOT be required for the MVP.

### FR-004: Liveness projection

PurposeBus MUST derive `alive`, `stale`, `dead`, or `unknown` from explicit stop state,
heartbeat lease, and safe local process observations. Human output MUST explain
the decisive observation. JSON output MUST expose both the derived value and
its evidence source.

### FR-005: Subscriptions

An Agent or Instance MUST be able to create, list, pause, resume, and cancel a
Subscription. Creation MUST require a topic filter and non-empty purpose.
Subscription records MUST expose:

- owner and Partition;
- topic filter;
- purpose;
- expected schema identifier when constrained;
- durable or instance-scoped lifetime;
- creation and expiry times; and
- active, paused, expired, or cancelled state.

The MVP topic syntax MUST support slash-separated exact topics plus MQTT-style
single-level `+` and trailing multi-level `#` filters. Publication topics MUST
not contain wildcards.

### FR-006: Offers

An Agent or Instance MUST be able to create, list, pause, resume, and cancel an
Offer. Creation MUST require a topic filter and non-empty purpose. An Offer MUST
expose its schema identifier when constrained, availability state, owner,
Partition, creation time, and expiry.

An Offer describes information that can be provided. It MUST NOT imply that the
provider has performed the work, that the data already exists, or that the
provider has authority to obtain it.

### FR-007: Matching and unmet demand

PurposeBus MUST match active Subscriptions or Requests to active Offers within the same
Partition using topic filters and exact schema identifiers when both sides
declare a schema. It MUST report:

- candidate providers for a need;
- unmet needs with no current candidate;
- needs whose candidates have no live Instance; and
- demand matching the current Agent's Offers.

Matching MUST NOT reserve a provider or automatically execute a task.

### FR-008: Requests

`request` MUST provide a one-shot convenience flow built on a durable,
expiring Subscription and a correlation identity. It MUST support creating the
request without waiting and waiting up to an explicit timeout. Request states
MUST include `open`, `response_available`, `fulfilled`, `cancelled`, and
`expired`. A matching Delivery transitions the Request to `response_available`;
acknowledging an accepted matching Delivery transitions it to `fulfilled`.
Acknowledgement MUST remain explicit unless the caller requested documented
auto-ack behavior.

For a Request, correlation is a delivery constraint rather than descriptive
metadata: a Message MUST create a Delivery for that Request only when the
Message correlation identity exactly equals the Request correlation identity.
An absent or different correlation identity MUST NOT change the Request state.
This rule applies equally to ordinary and retained Messages.

### FR-009: Publication

An Instance MUST be able to publish a Message with a concrete topic, non-empty
purpose, and one of:

- an inline UTF-8 payload;
- an inline JSON payload; or
- an opaque artifact reference with optional digest.

Artifact digests are metadata for opaque references only. Supplying a digest
with either inline payload form MUST fail as invalid input. PurposeBus treats a
reference and its digest as opaque strings and MUST NOT resolve the reference,
inspect the referenced data, or infer authority from either value.

Inline payloads MUST be bounded to at most 64 KiB in the MVP. A Message SHOULD
carry a schema identifier and MAY carry correlation, causation, expiry,
idempotency, and retained-message metadata.

Publication with the same producer-scoped idempotency key and unchanged command
content MUST resolve to the original Message rather than create a duplicate.
Reuse of the key with changed content MUST fail.

### FR-010: Durable broadcast delivery

Each active matching durable Subscription MUST receive its own durable Delivery
record. The MVP delivery contract MUST be at least once. Delivery states MUST
include `queued`, `leased`, `acked`, `expired`, and `dead_letter`.

Polling MAY lease a Delivery for bounded processing. A lease that expires
without acknowledgement MUST make the Delivery eligible for redelivery. One
subscriber's acknowledgement MUST NOT acknowledge another subscriber's
Delivery.

Competing-consumer delivery, in which only one member of a group receives the
Message, is outside the MVP.

### FR-011: Polling and waiting visibility

An Instance MUST be able to poll immediately or wait up to an explicit timeout.
During a blocking wait, PurposeBus MUST project that Instance as `activity=waiting` and
expose the wait start, deadline, and relevant Subscription or topic selection.
Normal return, interruption, or detected process loss MUST prevent a permanent
false `waiting` state.

### FR-012: Acknowledgement and recovery

Acknowledgement MUST name an exact Delivery and owning Instance or Agent. It
MUST be idempotent for the same Delivery. After process or PurposeBus restart, all
successfully committed, unexpired, unacknowledged Deliveries MUST remain
recoverable.

An Instance may acknowledge a Delivery only after that exact Instance leased
it. A stable Agent may directly acknowledge a queued or lease-expired Delivery
owned by that Agent, so an offline human mailbox does not require fabricating a
live Instance. Direct Agent acknowledgement MUST NOT steal a current Instance
lease or acknowledge an Instance-owned Delivery.

### FR-013: Retained information

Publication MAY explicitly mark a Message retained. At most one current
retained Message per exact topic and schema identity MUST be visible in a
Partition. A new matching durable Subscription MUST receive the current retained
Message as an ordinary subscriber-specific Delivery. Retention MUST NOT be the
default.

### FR-014: Human Agent parity

A human Agent MUST be able to use the same registry, Subscription, Offer,
publication, polling, mailbox, and acknowledgement commands as an AI Agent. A
human Agent MAY have a durable mailbox while no live process Instance exists;
its liveness is then `unknown` or absent, not falsely `dead`.

### FR-015: Current-state inspection

PurposeBus MUST provide read-only commands to inspect:

- the Partition and backend-neutral storage health;
- Agents and Instances;
- Subscriptions, Requests, and Offers, including their purposes;
- matches and unmet demand;
- queued, leased, expired, and dead-letter Deliveries; and
- recent state transitions without exposing payload content by default.

### FR-016: Agent-oriented next actions

`purposebus next` MUST return the current Agent or Instance's unread Deliveries,
matching Requests, acknowledgement work, heartbeat needs, and stale-state
warnings. Every item MUST include a reason and an explicit command or help route
when one exists.

`next` is navigation evidence only. It MUST NOT execute, acknowledge, publish,
or authorize any action.

### FR-017: Event history

Successful state transitions MUST append a timestamped event carrying stable
entity identifiers and transition type. Default history views MUST omit Message
payloads. Event history MUST distinguish self-declared state, process
observation, expiry, lease timeout, and operator action.

### FR-018: Secret and artifact handling

The MVP MUST NOT resolve credentials or secret references automatically. Users
and agents MUST NOT place raw secrets in inline payloads. PurposeBus MAY transport an
opaque reference, but reading the referenced artifact remains a separate action
under the caller's existing authority. PurposeBus MUST NOT claim that an opaque
reference is safe merely because it resembles a `secdat` key reference.

## 5. CLI requirements

### CLI-001: Public language and structure

Public command names, help, JSON field names, and default diagnostic messages
MUST be agent-neutral English. Commands SHOULD be organized by resource:
`agent`, `instance`, `subscription`, `offer`, `request`, and `delivery`, with
top-level `publish`, `poll`, `ack`, `match`, `status`, and `next` workflows.

### CLI-002: Discoverable help

The CLI MUST provide a complete top-level catalog and detailed nested help. It
MUST include task-oriented `help usecases`, conceptual `help concepts`, and
Partition guidance. Errors SHOULD include the narrowest useful next command or
help route.

### CLI-003: Stable JSON

Every inspection and workflow command needed by an Agent MUST support
machine-readable JSON with an explicit schema identity and schema version. The
same semantic distinctions MUST be preserved in human and JSON output.
Removing a field, changing a field's meaning, or changing a result collection's
shape MUST use a new response schema version rather than silently changing an
existing version.
Global context and output options MUST be accepted before or after a subcommand,
including the documented `purposebus next --format json` form.

### CLI-004: Output discipline

On success, structured data MUST be written to standard output. Diagnostics
MUST be written to standard error. Exit status MUST distinguish success,
invalid input, unavailable state, timeout/no message, conflict, and internal
failure without requiring diagnostic-string parsing.
Ordinary output MUST NOT expose persistence locations, internal command
digests, or raw process-observation records. Operational evidence that is not
part of a workflow response MUST use an explicit diagnostic surface.

### CLI-005: Explicit context

Commands MUST expose the resolved Partition and acting Agent or Instance in
JSON. Mutating commands MUST fail when the acting identity is absent or
ambiguous; they MUST NOT select an arbitrary live Instance.
The resolved Partition MUST have one authoritative top-level projection; a
command result MUST NOT repeat it.

`init`, `agent register`, and `instance start` are bootstrap operations. `init`
has no acting identity; registration and start explicitly act as the identity
being created. A Subscription, Request, or Offer owner acts when creating that
record. Instance heartbeat and stop are self-actions by the named Instance.
All other mutations MUST name exactly one `--agent` or `--instance` actor as
applicable. An Agent and its Instances form one ownership family for lifecycle
changes, but direct Delivery acknowledgement follows the narrower FR-012 rules.
Read-only commands expose a null actor unless an Instance is explicitly named
as navigation context.

### CLI-006: Read-only status

`status`, `next`, `match`, list/show operations, and help MUST NOT acknowledge,
publish, heartbeat, repair, expire early, or otherwise change coordination
state. Time-derived projections MAY change as time advances without being
recorded as a command-side mutation.

### CLI-007: Safe retries

Commands that create Messages or other non-idempotent records MUST accept an
idempotency key or return an identity that allows an ambiguous outcome to be
resolved read-only. Documentation MUST instruct callers to read back before
retrying an ambiguous mutation.

### CLI-008: Initial command catalog

The MVP command surface MUST cover these workflows, though final spelling MAY
be refined before implementation acceptance:

```text
purposebus init
purposebus agent register|list|show
purposebus instance start|heartbeat|stop|list|show
purposebus subscription add|list|pause|resume|cancel
purposebus offer add|list|pause|resume|cancel
purposebus request create|list|show|cancel
purposebus publish
purposebus poll
purposebus ack
purposebus match
purposebus status
purposebus next
purposebus events
purposebus help usecases|concepts|partitions|agent
```

### CLI-009: Public response boundary

Public response projections MUST use explicit field allowlists separate from
persistence rows and internal runtime records. List, show, status, next, poll,
and match MUST each have an intentional command-specific projection. Adding a
persistence column MUST NOT add a public field automatically.

Resource collections MUST expose a documented result bound or pagination
contract. Match output MUST avoid duplicate serialization of the same pair and
bound nested candidate output. Human output MUST be task-oriented rather than a
recursive rendering of the machine document.

A leased Delivery response MUST identify an exact acknowledgement step. A
normal empty or timed-out poll MUST provide a retry or inspection hint without
implying that acknowledgement is authorized before payload handling.

## 6. Non-functional requirements

### NFR-001: Durability

A successful mutating command MUST mean its state is durably committed. Restart
recovery MUST not depend on a client process remaining alive.

### NFR-002: Atomicity and concurrency

Concurrent clients MUST not produce duplicate identifiers, partial entity
records, cross-Partition delivery, or lost acknowledgements. A Message and the
Delivery records for the active matching Subscription snapshot at one defined
serialization point MUST become visible atomically.

### NFR-003: Determinism

Given the same durable state and observation time, JSON inspection results MUST
use deterministic ordering and stable projections.

### NFR-004: Bounded resources

Polling, payload size, event retention, redelivery attempts, history output,
resource lists, status detail, next actions, and match expansion MUST have
documented bounds. Reaching a bound MUST produce an observable state, page
metadata, or error rather than silently dropping live data.

### NFR-005: Local access boundary

The MVP MUST listen only on a same-user local transport or use same-user local
storage. It MUST NOT expose a network listener. On Linux, runtime directories
MUST be mode `0700`, regular state files MUST be mode `0600`, and any local
socket MUST reject access by other OS users.

### NFR-006: Inspectability

An operator MUST be able to explain why a Delivery exists, why an Instance is
reported stale or dead, and why an Offer matched a Subscription using stable
identifiers and non-secret metadata.

### NFR-007: Portability boundary

Linux is the initial required runtime. The public JSON and help contracts MUST
avoid CodingAgent-specific names so another agent implementation can integrate
without translation.

### NFR-008: Testability

Time, process observations, boot identity, and state-root selection MUST be
injectable or isolatable in tests. Acceptance tests MUST NOT depend on the
developer's live queue or ambient project Partition.

## 7. MVP acceptance conditions

1. Two AI Agent records and one human Agent record can coexist in one isolated
   test Partition and are visible through both human and JSON output.
2. A purpose-bearing Subscription and Offer match only inside their Partition,
   and unmatched or schema-incompatible demand is explained.
3. One publication creates independent Deliveries for two matching durable
   Subscriptions; acknowledging one leaves the other pending.
4. A leased but unacknowledged Delivery becomes available after lease expiry
   and survives a full service or process restart.
5. A blocking poll makes its Instance visibly alive and waiting, and normal
   return or killed-process detection clears or invalidates that projection.
6. PID reuse simulation does not attach the old Instance to the new process.
7. A human Agent receives and later acknowledges a Message without requiring a
   continuously live human process.
8. The same topic in two Partitions produces no cross-partition discovery,
   matching, retained delivery, or ordinary delivery.
9. Repeating an identical publication idempotency key produces one Message;
   changing content under that key fails without changing the original.
10. `purposebus next --format json` explains unread data, matched demand, heartbeat
    needs, and stale warnings without mutating state.
11. Help exposes the complete command catalog, concepts, use cases, Partition
    behavior, JSON schema identities, and remediation routes.
12. State corruption or an unsupported state schema fails closed with a
    diagnostic; it is not silently reset or repaired.
13. Public responses omit persistence and raw process-observation fields,
    collections report their bounds, human output is task-oriented, and the
    poll result supplies an exact acknowledgement step without changing the
    supported state schema.

## 8. Explicit MVP non-goals

- MQTT wire compatibility or MQTT client compatibility.
- Remote hosts, TCP listeners, federation, clustering, or replication.
- Cross-user authentication and authorization.
- Competing-consumer work queues.
- Exactly-once delivery.
- Agent scheduling, automatic delegation, or automatic task execution.
- Treating `purposebus next` as authority to act.
- Secret storage, secret-value inspection, or automatic `secdat` resolution.
- General artifact storage beyond bounded inline payloads and opaque references.
- Semantic schema negotiation beyond absent or exact schema identifiers.
- Organization-wide registry search or implicit parent/child Partition access.
- Guaranteed detection that a human is physically present.

## 9. Deferred decisions and implementation frontier

The requirements intentionally do not yet select a daemon, Unix socket
protocol, direct database architecture, programming language, or package
format. The next implementation activity is a narrow architecture experiment
that compares the smallest viable local designs against durability, blocking
wait visibility, restart recovery, and concurrent-client acceptance conditions.

No remote transport, work-queue mode, automatic tool adapter, or broader
authorization model may be inferred from this baseline.
