# PurposeBus MVP use cases and effect checks

These scenarios define the first observable product value. They supplement the
normative requirements; if wording conflicts, `docs/requirements.md` wins.

## UC-001: Discover a provider before asking for work

**Participants:** Agent A, Agent B, operator

**Preconditions:** B is registered with a stable capability and has an active
Offer for `test/result` with purpose and schema metadata.

**Flow:**

1. A declares a Subscription or Request for `test/result`, including why the
   information is needed.
2. The operator or A runs `match` or `next`.
3. PurposeBus reports B as a candidate, the matching topic/schema facts, B's current
   availability, and whether B has a live Instance.

**Effect check:** The user can distinguish "B can normally provide this", "B
currently offers this", and "B has a live process" without inspecting B's
terminal.

**Boundary:** The match does not cause B to run tests.

## UC-002: Provider sees purpose-bearing demand

**Participants:** Agent A as requester, Agent B as provider

**Flow:**

1. A creates a one-shot Request with a purpose, correlation identity, schema,
   and expiry.
2. B runs `purposebus next`.
3. PurposeBus reports the Request because it matches B's active Offer.
4. B separately decides whether its existing authority permits producing the
   information.

**Effect check:** B can decide relevance from topic, schema, requester, purpose,
and expiry without reading unrelated queue payloads.

## UC-003: Durable fan-out with independent acknowledgement

**Participants:** Producer P, subscribers A and C

**Flow:**

1. A and C create durable matching Subscriptions.
2. P publishes one Message with an idempotency key.
3. A and C each poll and receive distinct Delivery IDs for the same Message.
4. A acknowledges its Delivery; C does not.

**Effect check:** A is complete while C remains pending. Repeating P's identical
publish does not create another Message.

## UC-004: Observe a live polling wait

**Participants:** Waiting Agent A, operator

**Flow:**

1. A starts a bounded blocking poll.
2. The operator runs `status` while the poll is blocked.
3. PurposeBus reports A as `activity=waiting` and `liveness=alive`, with wait start,
   deadline, and selection metadata.
4. A receives a Message or times out.

**Effect check:** The final state no longer claims an active wait. If A is
killed, liveness eventually becomes dead or stale without permanently retaining
a false wait.

## UC-005: Recover a delivery after failure

**Participants:** Subscriber A

**Flow:**

1. A polls and leases a Delivery.
2. A terminates before acknowledgement.
3. PurposeBus restarts or a new A Instance starts after lease expiry.
4. The Delivery becomes available again and is acknowledged.

**Effect check:** The Message is not lost, and history explains both attempts.

## UC-006: Human Agent with an offline mailbox

**Participants:** Human H, producer P

**Flow:**

1. H registers a durable Subscription and then has no live Instance.
2. P publishes a matching Message.
3. Later, H starts an interactive Instance, polls, reads, and acknowledges it.

**Effect check:** H receives the Message without being falsely reported alive or
dead while no process evidence exists.

## UC-007: Project Partition isolation

**Participants:** Agents in project A and project B

**Flow:**

1. Each project uses the same topic, Agent display name, Subscription pattern,
   and Offer pattern.
2. A Message is published in project A.
3. Status and poll are executed in project B.

**Effect check:** Project B discovers and receives none of project A's dynamic
state. Both results expose different resolved Partition IDs.

## UC-008: Retained current information

**Participants:** Producer P, late subscriber A

**Flow:**

1. P explicitly publishes a retained status Message.
2. A creates a matching durable Subscription afterward.
3. A receives a Delivery for the current retained Message.
4. P publishes a newer retained Message for the same exact topic and schema.

**Effect check:** New subscribers see the newer current value, while event
history still distinguishes the two publications. Ordinary publications are not
retained.

## UC-009: Read-only navigation

**Participants:** Any Agent or operator

**Flow:**

1. Capture a digest or equivalent snapshot of the durable state.
2. Run `status`, `match`, list/show commands, and `next` repeatedly.
3. Capture the durable state again, excluding time-derived projections.

**Effect check:** No Message, Delivery, acknowledgement, heartbeat, Offer,
Subscription, or event was created or changed by navigation.

## UC-010: Ambiguous publication outcome

**Participants:** Producer P

**Flow:**

1. P publishes with an idempotency key but loses the command response.
2. P performs read-only lookup using the producer and idempotency key.
3. If the Message exists, P accepts that identity; otherwise P retries the exact
   same command.

**Effect check:** At most one Message exists. A retry with different content and
the same key fails visibly.

## Evaluation questions after the prototype

- Can an operator understand who is waiting for what from one status view?
- Can a provider understand why a request was routed to it?
- Does `next` reduce manual registry and inbox inspection?
- Does explicit purpose improve responses compared with topic-only exchange?
- Is durable fan-out sufficient, or do real workflows require competing
  consumers in the next scope?
- Does the selected local architecture keep waiting state accurate without
  requiring every Agent to be launched through a wrapper?
