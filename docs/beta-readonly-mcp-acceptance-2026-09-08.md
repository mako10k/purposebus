# PurposeBus 0.5.0 bounded read-only MCP beta candidate

Status: accepted by the owner for `T_BETA_BUILD`

Date: 2026-09-08

## Candidate identity

The `0.5.0` name identifies the roadmap beta scope. The independently built
package versions in this candidate are:

- core: `purposebus 0.2.0a1`;
- optional adapter: `purposebus-mcp 0.1.0a0`; and
- non-runnable policy package: `purposebus-codex-controller 0.0.0a0`.

The local branch and independently read remote branch both started from
`2a2b3a68c8f44a4107268e4fd51949106a37d486`. The candidate is uncommitted
workspace content on top of that revision. It has not been pushed, published,
or installed into a Codex or ChatGPT profile.

- Accepted pre-bookkeeping source-set SHA-256:
  `003556204b04a5a24876ad568bdececa7ac9e80dc31e4d9bf61e946b66c30b1b`
- Pre-acceptance active-roadmap document digest:
  `sha256:e85c5a9a0bdf10a626ddbbe6029220a0668ca4f2d6aafa6618fac3cc48743049`
- Accepted-roadmap document digest:
  `sha256:b4c5b8ad2178f3b39269b7200124432fdd4d8369aa238d40749616593db27b03`
- Post-acceptance bookkeeping source-set SHA-256:
  `18e51e82f240fb717b9ebcbe7b0c042d8f955452b1e1ec291cfc7e7cd64e0d1b`
- Core wheel SHA-256:
  `a2056e040674f5d3c1bb505a85f909642070945369918805a6554b76f18f26a0`
- MCP wheel SHA-256:
  `461fdecd14497c07395e93cb91857f2b2a87b51034cf10c90aece01985737bff`
- Controller wheel SHA-256:
  `8a0db0a602de4c1472174677391a555370189c52b0798a8d7b586e1baf824da4`

The source-set digest is the SHA-256 of the sorted `sha256sum` manifest for
`Makefile`, `README.md`, `pyproject.toml`, `src`, `tests`, `integrations`, the
current Plugin and repository marketplace, the two beta contracts, ADR-0001,
the implementation status, and the roadmap. Ignored bytecode and `egg-info`
build products are excluded. This acceptance record is excluded to avoid a
self-referential digest. The accepted digest identifies the exact snapshot
presented to the owner. The later bookkeeping digest differs only because the
roadmap, acceptance state, and status documentation record that decision; no
runtime code or package configuration was changed or rebuilt after acceptance.

## Owner acceptance

The owner accepted the exact candidate in the current thread. The roadmap
records this as criterion set `BETA_OWNER_ACCEPTANCE` revision `R1` and receipt
`RCPT_V0_5_BETA_OWNER_20260908`. The receipt's evidence revision is the accepted
source-set digest above and its verifier is `user`.

## Contract and implementation result

The public `purposebus.*.v2` response contract and the optional stdio adapter
were accepted by the owner as one bounded candidate. The adapter exposes
exactly these focused tools:

- `purposebus_status`;
- `purposebus_list_agents`;
- `purposebus_list_instances`;
- `purposebus_match`;
- `purposebus_next`; and
- `purposebus_get_request`.

Every tool has an action-oriented name, a human-readable title, an explicit
input schema, a generated structured-output schema, and annotations matching
its implemented behavior: read-only, non-destructive, idempotent, and closed to
public or external systems. These fields are part of the regression contract.

The operator binds aliases to existing absolute Partition paths at server
startup. Tool callers can supply only an alias and bounded semantic inputs.
The adapter invokes the resolved public CLI without a shell, forwards only an
allowlisted environment, requires exactly `purposebus 0.2.0a1`, checks the
command-specific v2 response schema and explicit Partition identity, and fails
closed without automatic retry.

This matches the current OpenAI MCP guidance to use focused tools, explicit
schemas, accurate safety annotations, structured results, and local tests for
initialization, advertised tools, normal results, invalid inputs, errors, and
annotations:
<https://developers.openai.com/plugins/build/mcp-server>.

## Requirement-to-evidence map

| Beta requirement | Evidence | Result |
| --- | --- | --- |
| Accept the `0.2.0a1` public response contract | Installed core suite exercises v2 allowlists, bounded results, deterministic output, error behavior, and supported-state reopen | 53 tests passed; owner accepted |
| Clean, non-editable optional package installation | Three wheels were built from isolated source copies and installed together into a fresh virtual environment | `pip check` passed |
| Six read-only tools | Real isolated CLI coverage exercises all six adapters; MCP client initializes, lists six tools, and calls structured status | 14 MCP tests passed |
| Explicit Partition bindings | Absolute existing paths and unique aliases are required; arbitrary, relative, duplicate, or tool-supplied paths are rejected | passed |
| Version and schema drift fail closed | Exact CLI version, expected v2 schema, top-level shape, explicit source, and canonical Partition path are checked | passed |
| Tool metadata matches behavior | Exact names and titles, structured output schemas, bounds, and four safety annotations are asserted | passed |
| Core and Plugin compatibility | Core remains dependency-free; current Plugin remains Skill-only with no MCP, app, or hook declaration | passed |
| Agent-neutral CLI fallback | The exact installed core wheel exposes `purposebus`, reports `0.2.0a1`, and does not depend on the MCP package | passed |
| Controller remains deferred | Its wheel contains policy code only and has no console entry point; expansion attempts are rejected by tests | 2 tests passed |

## Artifact and installed-environment evidence

The build used Python `3.12.3` and PEP 517 build isolation. The exact wheels
were then installed in a separate fresh environment, which resolved `mcp
2.2.0` and `pydantic 2.13.5` within the adapter's declared compatibility
ranges.

Wheel inspection confirmed:

- the core wheel contains only the core package plus its `purposebus` console
  entry point;
- the MCP wheel contains only the adapter package plus its `purposebus-mcp`
  console entry point; and
- the controller wheel contains only its policy package and no entry point.

The installed `purposebus-mcp --help` exposed only required repeatable
`--partition ALIAS=/ABSOLUTE/PATH` bindings and the bounded invocation timeout.
The test Partitions and state roots were temporary and isolated from the live
PurposeBus queue.

## Verification summary

- Installed core wheel: 53 tests passed.
- Installed MCP wheel and exact core wheel: 14 tests passed.
- Installed controller wheel: 2 tests passed.
- Dependency consistency: `pip check` passed.
- MCP stdio initialization, list-tools, and structured status call: passed.
- All six adapter operations through a real isolated CLI: passed.
- Wheel content and entry-point inspection: passed.
- Repository whitespace check: passed after all evidence edits.

## Acceptance and authority boundary

Owner acceptance of the exact bounded public response contract and local
read-only MCP candidate is satisfied. `T_BETA_BUILD` is complete and
`V0_5_BETA_ACCEPTED` is reached and accepted.

This acceptance does not install or enable the MCP server in any profile and
does not authorize Codex lifecycle control, PurposeBus writes, Connector use,
subagents, network transport, commit, push, publication, release, deployment,
production use, or starting the next roadmap task.
