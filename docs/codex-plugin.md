# PurposeBus Codex Plugin contract

Status: Skill-only local 0.2 alpha accepted

Date: 2026-09-04

## Purpose and architecture

The Plugin helps Codex discover and coordinate human and AI Agents inside one
explicit local PurposeBus Partition. It packages one Skill over the public,
versioned `purposebus` CLI. It does not embed PurposeBus, open its SQLite files,
or add an MCP server, app connection, hook, credential, or background daemon.

This follows the OpenAI Plugin package contract: the package has a required
`.codex-plugin/plugin.json`, bundles workflows under `skills/`, and is listed by
the repo marketplace in `.agents/plugins/marketplace.json`.

Official packaging reference:
<https://developers.openai.com/plugins/build/plugins>

## Supported surface

The prototype targets Codex CLI and Codex in the ChatGPT desktop app when the
session has a local environment containing a compatible `purposebus`
executable. Installation must be followed by a new session before acceptance
testing.

Codex IDE, web, mobile, cloud, remote environments, ChatGPT without local shell
access, cross-host coordination, and cross-user authorization are not supported
or verified by this candidate. The post-trial comparison found no measured need
for MCP and froze the Skill-only local surface for the 0.2 alpha. See
[the surface decision](codex-plugin-surface-decision-2026-09-04.md).

## Partition, identity, and authority

- Every command uses an explicit canonical Partition path. The Plugin never
  searches across Partitions or silently changes the selected Partition.
- Read-only `status`, registry list/show, `match`, and `next` results expose
  navigation evidence. They do not authorize work, acknowledgement, publication,
  or delegation.
- A mutation is attempted only for an explicit user objective and names exactly
  one accepted Agent or Instance actor where the CLI requires it.
- The Plugin does not invent an Instance to bypass lifecycle, lease, ownership,
  or acknowledgement checks.
- The host sandbox and approval policy remain authoritative. Plugin availability
  grants no filesystem, network, credential, or external-service permission.

## CLI and failure contract

The Plugin requires `purposebus --version` and versioned `purposebus.*.v1` JSON
documents. Unknown schemas, unknown state versions, corrupt state, missing CLI,
nonzero exits, ambiguous writes, and actor or ownership errors fail closed. A
named Subscription with the wrong polling identity reports
`ownership_mismatch`; it is not an empty queue and must not be retried as one.

The Plugin freezes write inputs and uses at most the explicitly intended number
of writes. A lost publish response is resolved through read-only lookup by
producer and idempotency key before any retry. Polling is bounded, and a Delivery
is acknowledged only after actual processing by its owning actor.

Payloads must not contain raw secrets. External artifacts use opaque references;
an artifact digest is accepted only with a reference, and the reference itself
does not grant access.

## Package and compatibility

- Plugin identity and accepted alpha version: `purposebus`
  `0.2.0+codex.20260904024157`.
- Compatible alpha core: PurposeBus `0.2.0a0` with `purposebus.*.v1` JSON.
- Components: one Skill and repo marketplace entry.
- Explicitly absent: `.mcp.json`, `.app.json`, hooks, embedded credentials, and
  direct database access.
- Ordinary PurposeBus CLI use remains available when the Plugin is disabled or
  uninstalled.

## Acceptance boundary

The 0.2 alpha acceptance covers manifest ingestion, Skill structure,
marketplace resolution, compatibility and permission-boundary assertions, the
core test suite, an isolated package, installed Linux CLI fresh sessions,
ownership recovery guidance, and uninstall fallback. See
[the alpha acceptance record](alpha-acceptance-2026-09-04.md). The earlier 0.1
Linux and Windows/Desktop checks remain in
[the prototype acceptance record](codex-plugin-acceptance-2026-09-04.md).

The native GUI window was not automated or visually observed, and the 0.2 alpha
was not installed into the Windows/Desktop profile. The local multi-agent trial
and surface comparison retain the Skill-only Plugin. No acceptance record
authorizes publication to a workspace or public directory, Git push, remote
coordination, MCP deployment, release, or deployment.
