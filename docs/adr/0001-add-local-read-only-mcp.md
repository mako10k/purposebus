# ADR-0001: Add an optional local read-only MCP adapter

- Status: Accepted
- Date: 2026-09-08
- Decision Owner: PurposeBus owner
- Relevant Objective: O-001 establish a local channel through which a client can observe PurposeBus before adding Codex lifecycle control
- Related Claims: C-001, C-002, C-003, C-004
- Related Evidence: E-001, E-002, E-003, E-004, E-005
- Related Actions: A-001, A-002, A-003
- Related Reviews: `docs/requirements.think`; command-line LLMThink audit `purposebus-local-readonly-mcp-implementation-20260908`
- Supersedes: None
- Superseded by: None

## Context

The desired later workflow is a local PurposeBus channel through which one
client can instruct a Codex process and, only after separate authorization,
allow that process to use configured MCP/Connector capabilities and launch
bounded agents. The current task accepts only the prerequisite through Phase 2:
freeze the boundary, create separated packages, and implement same-host local
read-only PurposeBus MCP over stdio.

Evidence:

- E-001: `docs/public-response-contract.md` defines versioned `purposebus.*.v2`
  successful documents, `purposebus.error.v1`, explicit Partition context, and
  bounded list shapes.
- E-002: the existing Codex Plugin is Skill-first and invokes only the public
  CLI; its manifest deliberately has no MCP server.
- E-003: the accepted 2026-09-08 implementation scope is Phase 0 through Phase
  2; Plugin installation, PurposeBus writes, Codex lifecycle control, subagent
  launch, remote transport, commit, push, and publication remain excluded.
- E-004: [OpenAI's MCP server guidance](https://developers.openai.com/plugins/build/mcp-server)
  recommends focused tools with explicit schemas, accurate annotations,
  server-side authorization and validation, and structured output; annotations
  are descriptive hints rather than an authorization mechanism.
- E-005: isolated integration tests exercise the real `purposebus 0.2.0a1` CLI,
  MCP tool advertisement, stdio initialization and tool invocation, fail-closed
  compatibility checks, and the controller authority ceiling.

Claims:

- C-001: a read-only adapter can reuse PurposeBus's public semantic boundary
  without importing storage or changing the core package.
- C-002: binding aliases to absolute Partition paths at server startup prevents
  a tool caller from selecting an arbitrary filesystem path.
- C-003: an MCP tool result or `purposebus next` recommendation is observation
  and guidance; it does not grant authority for a subsequent side effect.
- C-004: Codex lifecycle ownership is materially different from PurposeBus
  observation and therefore requires a separate contract and implementation
  phase.

## Decision

Add `integrations/purposebus_mcp` as an optional Python distribution pinned to
the MCP 2.x API and its directly imported Pydantic schema dependency. It exposes
exactly six read-only tools over local stdio:
status, Agent list, Instance list, match, next, and exact Request lookup. Every
tool invokes the public `purposebus 0.2.0a1` CLI with `--format json` and an
operator-configured explicit Partition. The adapter validates the exact success
schema and returned Partition context and fails closed on drift.

Do not add the MCP server to the existing Plugin manifest or to a user profile.
Keep the core PurposeBus package dependency-free. The MCP dependency belongs
only to the optional integration package.

Add `integrations/purposebus_codex_controller` as a non-runnable policy-only
skeleton. Its first-proof ceiling is one session, read-only filesystem, no
network, no subagents, and no experimental App Server API. The skeleton neither
starts Codex nor implements controller behavior.

Actions:

- A-001: publish the six-tool input/output and failure contract in
  `docs/mcp-readonly-contract.md`.
- A-002: enforce the public-CLI, Partition, environment, version, schema, and
  stdio boundaries in tests.
- A-003: require a new ADR and explicit authorization before adding PurposeBus
  mutations, Codex lifecycle control, network transport, Plugin/profile
  installation, Connector use, or subagents.

## Alternatives

- Extend the existing Skill-only Plugin immediately: not selected because it
  would combine package creation with client-profile installation and change a
  previously accepted Plugin surface.
- Read SQLite directly: rejected because storage records and paths are not the
  public contract and direct access would duplicate core compatibility logic.
- Add write tools now: rejected because read-only observation is the accepted
  first boundary and tool annotations cannot authorize mutations.
- Add a local or remote HTTP listener: rejected because same-host stdio is
  sufficient for this phase and has a smaller exposure and lifecycle surface.
- Implement Codex App Server control now: deferred because lifecycle schema,
  ownership, recovery, journal, approval and capability-ceiling decisions are
  not part of Phase 0 through Phase 2.

## Consequences

Good:

- Clients gain a typed local observation surface without weakening the existing
  PurposeBus public response contract.
- The core CLI and Skill-only Plugin remain independently usable.
- Partition selection and compatibility drift fail closed at the integration
  boundary.

Bad / Risk:

- The optional MCP package introduces third-party dependencies and must track
  MCP 2.x compatibility.
- A subprocess per tool call adds latency relative to direct library access.
- Read-only MCP alone cannot perform the requested later Codex coordination
  workflow.

Neutral:

- The PurposeBus state schema stays at version 1 and direct SQLite remains the
  core's internal implementation.
- Installation and client configuration remain separate owner-authorized work.

## Implementation Notes

The server resolves the `purposebus` executable once, passes a small non-secret
environment allowlist, uses argument vectors rather than a shell, imposes a
per-call timeout, and accepts tool-visible Partition aliases rather than paths.
Successful output must contain exactly `schema`, `actor`, `partition`, and
`result`. Public CLI errors retain `purposebus.error.v1` semantics and are
reported as MCP tool errors.

Validation runs in an ephemeral virtual environment. It does not install either
package into the user's Codex or Python profile.

## Review

- Review question: Does this slice establish the smallest useful local channel
  while preserving the later controller and authority decisions?
- Selected independent scope and material risk: public CLI adapter boundaries,
  Partition confinement, advertised tool effects, dependency isolation, and
  the explicit absence of lifecycle execution.
- Primary-source findings and unknowns: the MCP package API and tool guidance
  are confirmed for the pinned 2.x dependency; the future Codex App Server
  lifecycle and client installation configuration are intentionally unresolved.
- Owner disposition: Phase 0 through Phase 2 authorized by the 2026-09-08
  instruction to proceed; later phases remain unapproved.

## Follow-ups

- Design Phase 3 around the version-matched Codex App Server schema, explicit
  process ownership, bounded recovery, an audit journal, and a one-session
  capability ceiling.
- Decide separately whether and how a client profile or Plugin should register
  this MCP server.
- Add write tools only after defining actor binding, idempotency, confirmation,
  read-back, and maximum-write rules for each action.
