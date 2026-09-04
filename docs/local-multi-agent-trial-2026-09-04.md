# PurposeBus local multi-agent trial

Status: accepted; findings and post-MVP scope frozen

Date: 2026-09-04

## Scope and authority

This trial exercises the accepted local MVP and Codex Plugin through the public
`purposebus` CLI only. It does not authorize or establish a Git commit, push,
publication, release, deployment, remote transport, direct database access, or
production use.

The trial used an isolated state root and Partition:

- Partition path: `/tmp/purposebus-multi-agent-partition.HcTU8k`
- Partition ID:
  `path-sha256:a528c3eff80dbc89341babff0f82aee23c2dd9dca359165de8070055b4f6f985`
- State root: `/tmp/purposebus-multi-agent-state.kPkqND`
- CLI: `purposebus 0.1.0a0`
- Plugin: `purposebus@purposebus-local`
- Plugin version: `0.1.0+codex.20260904012439`

## Participants and execution paths

| Participant | Kind | Path | Fresh Codex threads |
| --- | --- | --- | --- |
| `trial-requester` | AI | Raw public CLI, Plugin disabled through an ignored user config | `01a06a23-27e9-7f83-8cfa-2125e6743385`, `01a06a27-9df8-7563-80bb-2d32fb4a0e2c`, `01a06a28-dcd5-7091-b607-423ac08f6436`, `01a06a2a-2644-7410-a010-6208d9dee251` |
| `trial-provider` | AI | Installed PurposeBus Plugin and its Skill | `01a06a24-7746-70d0-a856-5338eb8cb169` |
| `trial-human` | Human | Offline mailbox review and direct Agent acknowledgement | Current owner conversation |

The Plugin session loaded the installed Skill from the versioned Plugin cache,
confirmed `purposebus 0.1.0a0`, kept the Partition and state root explicit, and
used no direct storage access. The raw sessions were separate Codex processes
without the Plugin. All PurposeBus mutations had an explicit Agent or Instance
actor where required.

## Flow results

### Provider discovery and request response

Before the provider joined, raw `match` classified all five demand records as
`no_active_offer`. After the provider registered four schema-constrained Offers,
`match` returned five live matches and `next --instance trial-provider-1`
returned `consider_request` for `trial-request-1`. The result exposed the topic,
schema, requester, both purpose texts, correlation ID, expiry, provider identity,
and provider liveness.

The Plugin participant published correlated Message
`msg_659cd6f39dec4016af64169c11d05ffa`. Raw participant A leased and acknowledged
Delivery `del_ef1cf523f0e34ad997ab45c049037f57`. Independent read-back returned
`request_state=fulfilled` and `effective_request_state=fulfilled` for
`trial-request-1`.

### Durable fan-out and offline mailbox

Plugin publication `msg_b0c46afdc6cb4c3a95b6af95ed9326ba` atomically created
two distinct Deliveries for the same Message:

- AI Delivery `del_0659aeed398643f1ada523d9a00f3d64` was leased and
  acknowledged by `trial-requester-1`.
- Human Delivery `del_d4c786aab1164c0a89c99392bfb7d641` was reviewed and
  acknowledged directly at attempt 0 by Agent `trial-human`, which had no live
  Instance.

The human Message has schema `purposebus.trial.broadcast.v1`, purpose
"Deliver the same trial result independently to AI and offline human
subscribers", and payload:

```json
{"participants":["ai","human"],"result":"fanout-ready"}
```

The owner reported `understanding=acceptable`, authorized the exact
acknowledgement, and accepted the post-MVP scope decision. The Delivery was not
polled or leased. Exactly one `ack --agent trial-human` mutation recorded
`acked_at=2026-09-04T02:25:26.449Z`; independent read-back returned
`effective_state=acked`, event sequence 82 with actor type `agent`, and zero
pending Deliveries.

### Failure recovery

Raw participant A leased recovery Delivery
`del_642c456a62774beb846bdc537d3a9e6e` for two seconds at attempt 1 and ended
without acknowledgement. A later raw Codex process observed it as effectively
queued. A second poll using the original owning Instance identity leased the
same Delivery at attempt 2 and acknowledged it. Event history records:

| Sequence | Event | Actor | Attempt |
| --- | --- | --- | --- |
| 22 | `leased` | `trial-requester-1` | 1 |
| 24 | `lease_timed_out` | `trial-requester-1` | 1 |
| 25 | `leased` | `trial-requester-1` | 2 |
| 26 | `acked` | `trial-requester-1` | 2 |

A new Instance `trial-requester-2` in the same Agent family could not poll the
Delivery because the Subscription was owned by `trial-requester-1`. The public
error was only `no_message`; it did not explain the owner mismatch. Recovery
therefore worked across a new CLI process with the original Instance identity,
but a new Instance cannot take over an Instance-owned Subscription. Source
inspection confirmed the mechanism: Instance ownership requires exact
`owner_id == instance_id`, while Agent ownership compares the Subscription owner
with the polling Instance's `agent_id`.

A separate Agent-owned recovery case then created Delivery
`del_6aabd28419fe457bb74096aad2a5aaaf`. `trial-requester-1` abandoned attempt 1;
after lease timeout, successor Instance `trial-requester-2` leased the same
Delivery at attempt 2 and acknowledged it. Event sequences 78 through 81 record
`leased`, `lease_timed_out`, `leased`, and `acked`, with the actor changing from
`trial-requester-1` to `trial-requester-2`. This establishes both recovery
contracts without weakening their different identity scopes.

### Blocking poll latency and wait projection

A bounded poll for `trial-latency-sub` was visible through `status` as
`activity=waiting`, `liveness=alive`, `wait_valid=true`, with the exact selector,
start, deadline, PID, and process-identity reason. The matching Message was
created at `2026-09-04T02:06:40.527Z`; the waiting poll leased its Delivery at
`2026-09-04T02:06:40.589Z`, a 62 ms publish-to-lease interval. The publication
command took 0.35 seconds wall time. After the poll returned, the Instance was
again `idle` and its wait fields were cleared. The Delivery was acknowledged.

This is one same-host observation, not a latency distribution or a service-level
claim.

### Writer contention

Two AI Instance actors issued 20 simultaneous publications to the same isolated
Partition. A second 20-publication run established a sequential command
baseline.

| Run | Success | Failure | Wall time | Per-command min | p50 | p95 | max |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| 20 simultaneous processes | 20 | 0 | 953.723 ms | 316.127 ms | 478.220 ms | 802.825 ms | 938.969 ms |
| 20 sequential processes | 20 | 0 | 4307.343 ms | 160.904 ms | 202.412 ms | 287.398 ms | 292.123 ms |

All 40 results used `purposebus.publish.v1`, returned unique Message IDs, and
reported no deduplication. The simultaneous run increased per-command latency,
consistent with contention or serialization, but produced no lock failures and
completed the batch faster because process startup and work overlapped. These
figures include CLI and Python process overhead; they are not storage-only
benchmarks.

### Heartbeat accuracy

`trial-heartbeat-2` used a ten-second lease. A heartbeat at
`2026-09-04T02:08:04.638Z` set the exact projected expiry to
`2026-09-04T02:08:14.638Z`. Public `instance list` observed it alive at
`2026-09-04T02:08:12.002Z` and stale with
`liveness_reason=heartbeat_lease_expired` at
`2026-09-04T02:08:24.407Z`. The observations bound the transition consistently
around the declared deadline; they do not measure the exact transition instant.

## Usability and permission findings

- Actor identity was clear in successful JSON results: operator reads used
  `actor=null`, and writes named an exact Agent or Instance. Owner type still
  matters operationally; sharing an Agent ID did not make an Instance-owned
  Subscription available to another Instance.
- Purpose text was useful in `match`, `next`, poll results, and Delivery
  inspection. It let both AI participants distinguish decision, broadcast,
  recovery, latency, and human-review intent without inspecting unrelated
  payloads.
- The Plugin path completed all nine authorized provider mutations without an
  approval prompt or retry when the isolated state root was explicitly writable.
  It did not treat matching demand as authority for external work.
- One raw session guessed the nonexistent `delivery poll` form before reading
  top-level help. The Plugin Skill avoided this by explicitly naming `publish`,
  `poll`, and `ack` as top-level commands.
- The raw consumer's standing `worktimectl` read failed because the
  workspace-write sandbox could not create its lock under the user state root.
  PurposeBus itself remained constrained to the explicitly added isolated state
  directory. This is a session sandbox interaction, not a PurposeBus mutation
  failure.
- `no_message` was safe but insufficiently diagnostic when the requested
  Subscription existed and was owned by a different Instance.

## Accepted post-MVP scope decision

The owner accepted and froze the following decision for the 0.2 alpha:

1. Keep the direct local store and do not add a broker daemon. The bounded trial
   showed latency and serialization costs but no correctness or lock failure
   that requires a lifecycle-expanding daemon.
2. Keep the Codex Plugin Skill-only and public-CLI-only. It materially improved
   command selection and preserved identity and authority boundaries; this trial
   found no need for an MCP server.
3. Keep durable broadcast for independent fan-out, but do not make
   broadcast-only delivery the whole surface. Correlated Requests and explicit
   acknowledgement remain necessary, and competing consumers remain out of
   scope.
4. Add bounded hardening for ownership diagnostics and guidance: explain
   Instance-owned versus Agent-owned Subscription recovery, make a mismatched
   requested Subscription distinguishable from an empty queue, and preserve
   both verified recovery cases as regressions.
5. Do not add remote transport, federation, cross-user authorization,
   exactly-once delivery, automatic delegation, or secret resolution from this
   evidence.

This acceptance completes `T_LOCAL_MULTI_AGENT_TRIALS` and freezes
`TRIAL_FEEDBACK_FROZEN`. The downstream surface comparison was completed
separately in [the post-trial decision](codex-plugin-surface-decision-2026-09-04.md).
This trial itself does not authorize alpha implementation, commit, push,
publication, release, or deployment.
