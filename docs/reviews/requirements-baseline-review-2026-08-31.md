# AGQ requirements baseline self-review

Status: review complete; suitable for the bounded MVP architecture experiment

Date: 2026-08-31

## Scope

This review covers the initial intent, reasoning, normative requirements, and
effect-oriented use cases. It does not review an implementation because none
exists yet. It does not establish performance, remote-operation, security, or
production-readiness evidence.

Reviewed file SHA-256 values:

| File | SHA-256 |
| --- | --- |
| `docs/intent.md` | `733f15874315e56e298d668804915cec50e3955a3b8c4a874842663bedfdc5fa` |
| `docs/requirements.think` | `324085c31b87fa2ad6abb16bcbcff4027380b68dffbe2085e7725adf2184e73e` |
| `docs/requirements.md` | `5f302f3f993c93ac05b2913a8b91914605ad844fd75fdfa9df6f172a59a2835c` |
| `docs/use-cases.md` | `f152ba16b9a92c6f5b22cf05a33f30d7b90c10b9c2267a0dffdcda1fb880323c` |

## LLMThink review

The exact `docs/requirements.think` text was audited as the workspace-local
Thought `docs-requirements` and then finalized. The final audit was generated at
`2026-08-31T02:45:55.265Z` by engine `0.1.0`.

Tool result:

- fatal: 0
- error: 0
- warning: 0
- info: 1
- hint: 18

The one info finding says that explicit pending items reduce decision
certainty. This is accepted: architecture selection, remote transport,
competing consumers, rich schema negotiation, automatic adapters, and measured
performance targets remain deliberately unresolved.

Seventeen hints were conservative contradiction candidates caused by decisions
sharing the user-intent premises `PR1`, `PR2`, or `PR4`. Manual pair review found
no negating conclusions:

- `D1` defines the non-MQTT protocol boundary while `D2` through `D4` define
  entities, purpose, and authority separation inside that boundary.
- `D5`, `D6`, `D9`, and `D10` narrow different aspects of the same prototype
  premise: deployment scope, delivery, process integration, and architecture
  selection.
- `D2` and `D7` both use human/AI parity but address identity and liveness
  respectively.

The remaining hint reports semantic proximity between `D1` and `D2`; they were
kept separate because protocol scope and entity decomposition have different
acceptance consequences.

LLMThink still reports 15 decision-to-support pairs without a persisted
semantic-audit verdict. This review does not relabel all of them `supported`:
some are accepted MVP design choices rather than empirically established
claims. The normative requirements and prototype acceptance tests remain the
appropriate way to validate those choices.

## Corrections made during review

- Split the single broad problem into ten decision-specific questions and
  changed long LLMThink statements to block text.
- Made Agent registry membership and `agent_id` uniqueness explicitly
  Partition-scoped; no hidden global registry remains.
- Defined Request states and the response/acknowledgement transition.
- Defined concurrent publication against one Subscription serialization point.
- Replaced vague same-user permission wording with Linux runtime-directory,
  state-file, and local-socket requirements.

## User-request coverage

| Requested concern | Requirements coverage |
| --- | --- |
| Who subscribes, what they need, and why | `FR-005`, `FR-007`, `FR-008`, `FR-015` |
| Who can publish which information and why | `FR-006`, `FR-007`, `INV-004` |
| User is an Agent participant | `FR-014`, `INV-001`, `INV-002` |
| Agent registry, ability, and purpose | `FR-002`, `FR-003`, `FR-006` |
| Waiting, PID, and liveness visibility | `FR-003`, `FR-004`, `FR-011`, `INV-002`, `INV-003` |
| Project communication boundary | `FR-001`, `INV-006`, `INV-007` |
| Navigable command surface | `FR-016`, `CLI-001` through `CLI-008` |

## SealGraph provenance

The reviewed input chain was sealed upstream-first with local source bindings:

| REF | Head Seal | Cause |
| --- | --- | --- |
| `intent/agq-mvp` | `0339bbbab4a85eabf2752d07e454b317f5b1098083b92eb96d35332886cf8cdb` | root |
| `reasoning/agq-mvp` | `8ec4907ce67da9a5c6f107367361b459f28b83caccc5bad4bdb8f38c4673d313` | intent |
| `requirements/agq-mvp` | `3835a93b265e6acd117a8ef5d5e05f186d17740b4e7325aa74f98732fc2dfadb` | reasoning |
| `usecases/agq-mvp` | `ef3a97c17423f2fc7c7f2eb9ed2863176636152ac9f079cd72761e6c797c9afe` | requirements |

This review is sealed separately as `review/agq-mvp` against all four reviewed
heads. Its own Seal ID cannot be embedded in its sealed content without making
the content self-referential; the REF is the stable lookup handle.

## Decision

The baseline is internally consistent enough to begin one bounded architecture
experiment. Implementation must remain within the same-host, same-user,
durable-broadcast MVP and demonstrate the twelve acceptance conditions before
the scope is broadened.

The baseline does not choose the implementation architecture. A successful
prototype must produce evidence for waiting visibility, durable restart
recovery, concurrency, and practical operator value before daemon, transport,
or performance decisions are promoted to requirements.
