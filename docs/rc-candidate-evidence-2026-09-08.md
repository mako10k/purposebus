# PurposeBus RC Candidate Evidence (2026-09-08)

## Decision status

- Candidate result: ready for the separate owner-acceptance gate.
- Owner acceptance: pending.
- PERT task: `T_RC_HARDENING` is `done`.
- PERT milestone: `V0_9_RC_READY` is reached; this does not itself grant acceptance, installation, publication, or deployment authority.

## Immutable evidence

- Candidate source digest: `sha256:ab3af220b964f55d7272d765ffdece1bf9f32f96b7abf67c047103fe3fda346d`
- Evidence manifest: `build/rc/ab3af220b964f55d7272d765ffdece1bf9f32f96b7abf67c047103fe3fda346d/evidence.json`
- Evidence manifest digest: `sha256:b0141b8d4693977519a65fd0fa55677c6e6d0de1fc6d1a5f17b3eaee2aa666bb`
- RC contract digest: `sha256:c658784e2bb649c6dfb094719f0e028dd52f4759b5e573cc3695f4404f0f43a6`
- PERT document digest after task completion: `sha256:ef2de2e1712108ca33622d45bafa0d88b5d5f91c1fe01f36faf532839929dede`
- Base repository HEAD: `2a2b3a68c8f44a4107268e4fd51949106a37d486`
- Historical baseline revision: `f089f0ed8cdad29f49d3ba593060728989783740`

This evidence document is the single exact exclusion from the normalized source
snapshot. That exclusion avoids a self-referential digest. Re-running
`make verify-rc` must therefore reproduce the source and evidence digests above.

## Candidate artifacts

| Artifact | Version | SHA-256 | Reproducibility |
| --- | --- | --- | --- |
| Baseline core wheel | `0.2.0a0` | `5f67ffb95b4eddf14fbdaeeb1478dee44b4b1ea55a4ca2778264f65b316cb84d` | Historical transition input |
| Candidate core wheel | `0.2.0a1` | `195de2c97bd21a25580d966e762999459e81208d26e65225802c899aa8405cb8` | Byte-identical across two builds |
| Read-only MCP wheel | `0.1.0a0` | `9c5fc9701fd9c0746118c11cae7f63f176b9a14335b9cedb5e44641579ee4f7b` | Byte-identical across two builds |
| Controller policy wheel | `0.0.0a0` | `d4797e1463c0bf5cd977f216e390ec98cf5000847aaba3fa4e1a1040a2017273` | Byte-identical across two builds |

The component versions are independent package versions frozen by the RC
contract. The roadmap milestone name does not rewrite them to `0.9`.

## Verification results

- Core suite: 57 tests passed.
- MCP integration suite: 14 tests passed against the exact final local wheels.
- Controller policy suite: 2 tests passed against the exact final local wheels.
- RC contract tests: 4 tests passed.
- Dependency integrity: `pip check` reported no broken requirements in the isolated integration environment.
- Core transition: baseline `0.2.0a0` to candidate `0.2.0a1`, rollback to baseline, and re-upgrade all passed while preserving the registered state record.
- Plugin transition: baseline `0.2.0+codex.20260904024157` to candidate `0.2.0+codex.20260904090953` and rollback passed in isolated `HOME` and `CODEX_HOME` directories; cache-tree readback passed.
- Corrupt-state behavior: the candidate failed closed with `purposebus.error.v1`, preserved the corrupt bytes, and initialized a separate recovery root with directory mode `0700` and database mode `0600`.
- Bounded load: 20 status processes completed within their timeouts using at most 4 workers.
- Public contract: critical-file bindings, all 30 successful v2 CLI schemas, the v1 error schema, and the six read-only MCP operations passed the freeze checks.
- Plugin structure and Skill structure validators passed.
- LLMThink audit: zero fatal findings, zero errors, and zero warnings; the remaining informational finding records the explicit limitations below.

## Environment exercised

- Codex CLI: `codex-cli 0.153.4`
- Python: CPython `3.12.3`
- Platform: Linux WSL2 `6.18.33.2`, x86_64, glibc `2.39`
- Distribution: Ubuntu `24.04.4 LTS`

## Limitations and authority boundary

- No active Codex or ChatGPT profile was changed.
- No new conversation or agent run was started.
- Only the recorded WSL2, Ubuntu, Python, and Codex CLI environment was exercised.
- Public Plugin Directory review, signing, publication, and deployment were not exercised.
- No Connector account, remote host, or cross-user PurposeBus surface was exercised.
- This local RC evidence does not authorize profile installation, agent launch, commit, push, PR, merge, release, publication, deployment, or any PurposeBus mutation.

## Owner gate

Owner acceptance remains the only open criterion for `V0_9_RC_ACCEPTED`.
Acceptance should bind to the candidate source digest and evidence manifest digest
listed above. If either digest changes, the owner gate must use the replacement
evidence rather than this document.
