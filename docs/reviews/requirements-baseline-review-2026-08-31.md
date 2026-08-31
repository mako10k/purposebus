# PurposeBus requirements baseline self-review

Status: review complete; suitable for the bounded MVP architecture experiment

Date: 2026-08-31

## Scope

This review covers the initial intent, reasoning, normative requirements, and
effect-oriented use cases. It did not review the later implementation. It does
not establish performance, remote-operation, security, or production-readiness
evidence.

Reviewed file SHA-256 values:

| File | SHA-256 |
| --- | --- |
| `docs/intent.md` | `e3bb64359e3f88edd0c7f4a269a75d19000b0d83fc50dc4d3ea200b01a489eb0` |
| `docs/requirements.think` | `58f44b33ef274852c9011dbcfb8b4efcc1e4d011747792c33985c760c82adc49` |
| `docs/requirements.md` | `d3322e7c4b599c4694ca2754369a196d992a70374d1a2d934d1695bd906c6086` |
| `docs/use-cases.md` | `87cb27a09a1a86bf27d353d035ce25b5151b0b683d6aff3728985f70245047ed` |

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
| `intent/purposebus-mvp` | `9d7ac116836e0b22ac17dd2d0cf9c1830ef4cb109ca222ad7d700af7a5bf394e` | root |
| `reasoning/purposebus-mvp` | `74e25da61d7cb9179c57f63ea224c9c6f079c03d2237bd94074f3fd2fdbdb02e` | intent |
| `requirements/purposebus-mvp` | `44e381c76729fe9b8639f4d14a86ec53a28924dd213650579035446127b34261` | reasoning |
| `usecases/purposebus-mvp` | `e7a92aa0be716828b2f44993d65c996c4496782c421f014f82d04a863f90f8f9` | requirements |

This review is sealed separately as `review/purposebus-mvp` against all four reviewed
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
