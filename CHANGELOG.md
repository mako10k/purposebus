# Changelog

All notable changes to PurposeBus are recorded here.

## 1.0.0 - 2026-09-08

### Added

- A versioned, agent-neutral JSON response contract for every public CLI
  success result, with bounded collection metadata and explicit Partition and
  actor context.
- Purpose-aware `match` and `next` navigation, correlated one-shot Requests,
  durable delivery, retained messages, explicit ownership, and safe
  idempotency readback.
- A Skill-only Codex Plugin package with isolated fresh-session evidence.
- An optional, separately packaged local stdio read-only MCP adapter exposing
  six public-CLI-backed tools.
- Content-addressed release verification for reproducible wheels, deterministic
  Plugin archives, predecessor rollback, corrupt-state recovery, and bounded
  load.

### Compatibility

- The public success schema family remains `purposebus.*.v2`; public errors
  remain `purposebus.error.v1`.
- Durable state schema remains `1`. Upgrading from the accepted `0.2.0a1` RC
  to `1.0.0` requires no storage migration, and the same supported state can be
  reopened after rollback.
- The release Plugin and optional MCP adapter require exactly core `1.0.0`.

### Boundaries

- Coordination remains same-host and same-user inside one explicit local
  Partition.
- The Plugin remains Skill-only. Client installation, remote transport,
  Connector use, agent lifecycle control, publication, and deployment are not
  implied by this release package.

