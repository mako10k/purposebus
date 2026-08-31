# AGQ initial intent and assumptions

Date: 2026-08-31

## User intent

Build a command-oriented queue between AI agents with MQTT-like discovery and
delivery. A user is also an agent instance. An operator must be able to answer:

- which agent wants which information and for what purpose;
- which agent can provide which information and for what purpose;
- which agents and concrete instances exist, and what they can do;
- whether an instance is active, waiting for information, stale, or dead;
- which project partition contains the communication; and
- what command should be run next to inspect or progress the exchange.

The first implementation is intended to test the behavior and practical value,
not to reproduce the complete MQTT protocol or build a distributed broker.

## Initial MVP decisions

The accepted initial proposal is narrowed to these implementation defaults:

- same-host, same-OS-user operation;
- one logical communication partition per canonical project root by default;
- durable broadcast delivery, with one delivery and acknowledgement state per
  matching subscription;
- explicit agent and instance registration from existing agent processes;
- no requirement to launch an agent through an AGQ wrapper;
- small inline UTF-8 or JSON messages and opaque artifact references;
- human and AI participants use the same agent, subscription, publication, and
  mailbox model; and
- network federation, competing-consumer work queues, and secret distribution
  are deferred.

These are MVP boundaries, not claims that later versions must remain local or
broadcast-only.

## Authority boundary

Agent capability, an active offer, a matching request, a queued message, and an
`agq next` recommendation are coordination facts only. None of them authorizes
filesystem changes, external writes, credential use, process control,
deployment, release, or another action outside the authority already held by
the acting human or agent.

## Assumptions to validate by building the MVP

- Purpose-bearing subscriptions and offers are more useful than topic names
  alone when agents decide whether and how to respond.
- A single status surface can make waiting, stale, and dead instances easier to
  distinguish than shell/process inspection alone.
- Durable fan-out and explicit acknowledgement are sufficient for the first
  useful handoff scenarios.
- A canonical project-root partition prevents accidental cross-project
  discovery without placing queue files in the project checkout.

## Deferred choices

- background broker process versus direct database access with bounded polling;
- remote transport and authentication;
- competing-consumer work queues;
- organization-wide discovery or explicitly bridged partitions;
- quantitative throughput and latency targets beyond functional MVP checks;
- rich schema negotiation beyond exact schema identifiers; and
- automatic adapters for `secdat`, `perttool`, or other tools.
