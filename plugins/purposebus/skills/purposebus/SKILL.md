---
name: purposebus
description: Use PurposeBus to coordinate human and AI agents inside one explicit local Partition through the public purposebus CLI. Use for registry discovery, read-only status, match, and next guidance, or explicitly requested PurposeBus mutations. Do not activate for cross-host, cross-user, remote-surface, or direct-database work; explain that boundary without inspecting local PurposeBus state.
---

# PurposeBus

Coordinate through the installed `purposebus` executable. Treat PurposeBus as a
same-host, same-user coordination bus, not as authority to perform the work it
describes.

## Check supported scope first

Before running `purposebus`, determine whether the requested outcome is possible
inside one same-host, same-user local Partition. If it requires another host or
user, network transport, a remote environment, or a web, mobile, IDE, or cloud
surface, stop before inspecting any Partition or running any PurposeBus command.
Explain the unsupported boundary and that a separately designed transport or
integration would be required. Do not probe a default local Partition merely to
support that explanation.

If the request also contains an independently useful same-host task, proceed
only with that explicitly separable local part and keep its Partition explicit.
Do not substitute a local probe for the unsupported requested outcome.

## Establish context

1. Confirm `purposebus --version` reports the compatible alpha
   `purposebus 0.2.0a0`. If it is absent or incompatible, stop and report the
   missing prerequisite; do not locate or open its SQLite database as a
   fallback.
2. Resolve the intended Partition from the user's explicit path or the canonical
   Git worktree containing the current task. Keep that path explicit with
   `--partition PATH` on every command. Do not silently switch Partitions.
3. Use `--format json` and accept only documented `purposebus.*.v1` results.
   Treat an unknown schema or nonzero exit as a stopped operation.
4. Leave `--state-dir` unset for ordinary use. Set it only when the user asks for
   an isolated test state, and keep that state separate from their live queue.

## Observe before acting

Start with the narrow read-only commands needed for the request:

```text
purposebus --partition PATH --format json status
purposebus --partition PATH --format json agent list
purposebus --partition PATH --format json instance list
purposebus --partition PATH --format json match
purposebus --partition PATH --format json next --instance INSTANCE_ID
```

Use `next` only after an existing live Instance is identified. Explain the
resolved Partition, relevant Agent or Instance, matching purpose and schema,
liveness, and exact identifiers. A match or next recommendation is navigation
evidence only; it never authorizes acknowledgement, publication, delegation, or
unrelated repository work.

## Mutate only for an explicit objective

Before a mutation, freeze the intended Partition, command, actor, identifiers,
payload or reference, and maximum number of writes. Show the user material
ambiguity instead of inventing an Agent, Instance, topic, schema, purpose, or
recipient.

- Follow `purposebus COMMAND --help` for the installed version.
- `publish`, `poll`, and `ack` are top-level commands. Inspect them with
  `purposebus publish --help`, `purposebus poll --help`, and
  `purposebus ack --help`; do not invent nested forms such as
  `message publish`, `subscription poll`, or `delivery ack`.
- Name exactly one accepted `--agent` or `--instance` actor whenever the command
  requires acting identity. Do not use operator-style reads as mutation context.
- Use an existing live Instance for `publish` and `poll`. Do not start an
  Instance merely to bypass ownership or acknowledgement rules.
- Before an explicit `poll --subscription`, inspect the Subscription owner.
  An Instance-owned Subscription requires the exact owning Instance identity,
  even from a later CLI process. An Agent-owned durable Subscription can be
  recovered by another active Instance of the same Agent. Treat
  `ownership_mismatch` as a stopped operation; do not retry it as an empty
  queue or invent a replacement owner.
- Include a precise purpose. Preserve Request correlation and schema facts when
  publishing a response.
- Prefer a stable idempotency key for publication. If the command response is
  lost or ambiguous, inspect `message list` by producer and idempotency key;
  never resend blindly.
- Acknowledge only the exact Delivery after its content has actually been
  accepted or processed, using its owning Agent or Instance. Never steal an
  active Instance lease with direct Agent acknowledgement.
- Keep polls bounded. Do not leave a hidden background poll running.

Never put credentials or raw secrets in PurposeBus. Use an opaque
`--reference` for external artifacts, and attach `--artifact-digest` only with
that reference. PurposeBus does not resolve the reference or grant access to it.

## Report the result

Read back the affected object after a successful write. Report the Partition,
actor, exact IDs, result schema, and any remaining work. Separate PurposeBus
state from the external work it describes, and state clearly when no write was
performed.

Do not access PurposeBus storage directly, embed credentials, weaken the host
sandbox or approval policy, infer cross-user or remote coordination, or claim
support for Codex web, mobile, IDE, or cloud surfaces from this local plugin.
