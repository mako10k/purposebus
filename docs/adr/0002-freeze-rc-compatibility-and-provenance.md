# ADR-0002: Freeze RC compatibility and artifact-bound verification

- Status: Accepted
- Date: 2026-09-08
- Decision Owner: PurposeBus owner
- Relevant Objective: move the accepted read-only MCP beta to `V0_9_RC_READY`
- Related Claims: C-001, C-002, C-003, C-004
- Related Evidence: E-001, E-002, E-003, E-004, E-005
- Related Actions: A-001, A-002, A-003, A-004
- Related Reviews: command-line LLMThink audit of `docs/rc-hardening.think`
- Supersedes: None
- Superseded by: None

## Context

The beta accepts independently versioned core, optional MCP, controller-policy,
and Skill-only Plugin packages. The roadmap milestone name `V0_9_RC_READY` is a
planning milestone, not evidence that every package should be renamed 0.9.0.
RC hardening must bind evidence to exact artifacts while preserving the accepted
public and authority boundaries.

Evidence:

- E-001: receipt `RCPT_V0_5_BETA_OWNER_20260908` binds the accepted beta to
  source-set SHA-256
  `003556204b04a5a24876ad568bdececa7ac9e80dc31e4d9bf61e946b66c30b1b`.
- E-002: the candidate uses core `0.2.0a1`, MCP `0.1.0a0`, controller policy
  `0.0.0a0`, Plugin `0.2.0+codex.20260904090953`, public success schema v2,
  error schema v1, and state schema 1.
- E-003: repository tests cover response projection, bounds, concurrency,
  permissions, corrupt and unknown state, Plugin structure, and MCP failure
  containment.
- E-004: the repository lacked a single artifact-bound, reproducible build and
  upgrade/rollback verifier before this decision.
- E-005: [official OpenAI Plugin packaging documentation](https://developers.openai.com/plugins/build/plugins)
  separates local and repository marketplaces from public publication, while
  [the testing guide](https://developers.openai.com/plugins/deploy/connect-chatgpt)
  requires local installation and a new conversation for complete behavioral
  Plugin testing.

Claims:

- C-001: a normalized source archive plus reproducible wheel hashes can identify
  the exact local RC candidate without a commit or publication.
- C-002: alpha `0.2.0a0` at `f089f0ed8cdad29f49d3ba593060728989783740`
  is an independently recoverable baseline for core and Plugin transitions.
- C-003: temporary Python environments, temporary Codex homes, and isolated
  PurposeBus state can verify packaging mechanics without changing the active
  user profile or live queue.
- C-004: active-profile fresh-conversation behavior and other OS or Codex
  versions remain separate evidence; artifact tests cannot establish them.

## Decision

Preserve the accepted package versions and freeze the exact public schema,
Plugin component, MCP tool, recovery, bound, and authority contract in
`release/rc-contract.json`. Do not add MCP or controller behavior to the Plugin.

Use `scripts/verify_rc_candidate.py` to create a normalized source archive,
build every Python wheel twice, require byte-identical wheel hashes, inspect
package metadata, and bind the results in `purposebus.rc-evidence.v1`. The same
run must verify alpha-to-candidate core upgrade and rollback against supported
state, corrupt-state fail-closed behavior and separate-root recovery, bounded
parallel reads, and Plugin install/update/rollback in a temporary Codex home.

Artifacts under `build/rc/<source-sha256>/` are immutable: an existing path may
be reused only when its bytes match. The verifier performs no package-index
lookup, active-profile installation, agent launch, commit, push, submission,
publication, release, or deployment.

The owner-facing `docs/rc-candidate-evidence-2026-09-08.md` record is excluded
from the normalized source archive so that it can quote the completed archive
and wheel digests without a self-referential hash. No runtime source, package
configuration, Plugin content, or normative contract is excluded.

## Alternatives

- Rename every package to 0.9.0: rejected because the roadmap milestone does
  not establish one shared package version and the later 1.0 Plugin package is
  still a separate task.
- Documentation-only hardening: rejected because it cannot establish artifact,
  transition, load, corruption, or permission behavior.
- Install into the active profile now: deferred because profile mutation and a
  new agent conversation are not authorized by starting this repository task.

## Consequences

Good:

- One command produces candidate-bound, repeatable local evidence.
- Upgrade and rollback use a historical immutable baseline rather than a mock.
- Active user profiles and live PurposeBus state remain untouched.

Bad / Risk:

- The verifier depends on local Git history, Python `pip`/`venv`, and the Codex
  CLI for the full matrix.
- Only the observed WSL/Linux, Python, and Codex versions become current runtime
  evidence.

Neutral:

- Existing public response and state schemas remain unchanged.
- RC readiness remains distinct from owner acceptance and publication.

## Implementation Notes

- A-001: add the machine-readable contract and static regression tests.
- A-002: add the immutable source/wheel and transition verifier.
- A-003: document the corruption recovery and evidence boundaries.
- A-004: run core, integration, Plugin, ADR, and RC checks before presenting an
  exact owner-acceptance candidate.

## Review

- Review question: does the procedure cover each `T_RC_HARDENING` mechanism
  without crossing into later Plugin packaging or external publication?
- Selected evidence: exact beta receipt, immutable alpha Git revision, source
  and artifact hashes, temporary-environment transitions, and existing tests.
- Known limitation: a new live Codex/ChatGPT conversation is not created by the
  verifier; prior exact-artifact evidence may be cited, but current live pickup
  must be separately authorized if required.

## Follow-ups

- Present the exact RC source and artifact digests for owner acceptance.
- Keep `T_V1_PLUGIN_PACKAGE` and all public directory work downstream of the RC
  owner gate.
