# PurposeBus 1.0.0 release preparation

Status: local release package verified; publication authorization pending

Date: 2026-09-08

## Frozen candidate

- Core: `purposebus 1.0.0`
- Plugin: `purposebus@purposebus-local`
  `1.0.0+codex.20260908103255`, Skill only
- Plugin and read-only MCP core compatibility: exactly `==1.0.0`
- Public success schemas: `purposebus.*.v2`
- Public error schema: `purposebus.error.v1`
- Durable state schema: `1`
- Machine contract: `release/v1-contract.json`
- Fresh-session manifest: `release/v1-plugin-evaluations.json`

The candidate is identified by content digests and the recorded base HEAD. It
is not yet identified by a candidate commit, tag, or server-side ref because no
commit or remote write is authorized.

## Build and verify

Run the complete local release verifier from the repository root:

```sh
make verify-v1
```

The verifier creates a normalized source snapshot, builds the core, optional
MCP adapter, and controller-policy wheels twice, compares wheel bytes, runs the
core suite from the snapshot, and emits a content-addressed directory under
`build/v1/<source-sha256>/`. Existing output bytes are immutable.

It installs only local wheels into temporary environments. A temporary Codex
home verifies predecessor Plugin installation, candidate upgrade, candidate
uninstall and reinstall, rollback, and final removal. The verifier does not
contact a package index or change the active Codex profile.

## Upgrade, migration, and rollback

The accepted predecessor is core `0.2.0a1` from the immutable RC artifact. The
release verifier performs this sequence against one isolated Partition and
state root:

1. install `0.2.0a1`, initialize state schema `1`, and register a probe;
2. install `1.0.0` and reopen the same state without migration or mutation;
3. reinstall `0.2.0a1` and reopen the same state;
4. reinstall `1.0.0` and confirm the v2 status contract.

There is no storage-migration command for this transition. Unknown or corrupt
state still fails closed without rewriting its bytes. Recovery uses a separate
empty state root; reconstruction or import requires a separately reviewed plan.

Rollback material in the release directory includes the accepted `0.2.0a1`
core wheel and the accepted predecessor Plugin ZIP. Rollback is a deliberate
operator action, not an automatic repair.

## Supported install and uninstall surface

Supported evidence covers Python 3.11 or newer on the recorded WSL/Linux
environment, Codex CLI with the same local environment, and the Skill-only repo
marketplace. The Plugin requires a new conversation after installation. The
agent-neutral `purposebus` CLI remains usable after Plugin removal.

The native Desktop GUI was not automated or visually observed for this exact
candidate. Codex cloud, web, mobile, cross-host, cross-user, remote transport,
workspace publication, and the public Plugin Directory remain unsupported or
unverified.

For an authorized local test, use a temporary `HOME` and `CODEX_HOME`, add a
copied repo marketplace, install `purposebus@purposebus-local`, start a new
conversation, remove the Plugin, remove the copied marketplace, and read back
the installed list. Do not apply this procedure to an active profile without a
separate explicit instruction.

## Release artifacts and authorization inputs

`release-manifest.json` records SHA-256 values for the source archive, core,
MCP, and controller wheels, deterministic Plugin ZIP, rollback core wheel,
rollback Plugin ZIP, and release contract. `evidence.json` binds the clean-room
checks, environment, limitations, and release manifest.

Known and unresolved publication inputs are kept distinct:

| Surface | Known candidate destination | Still requires explicit authorization |
| --- | --- | --- |
| Git source | `https://github.com/mako10k/purposebus.git` | exact branch, commit, tag, release, and maximum writes |
| Core wheel/source | content-addressed local release directory | any package registry or GitHub Release target |
| Codex Plugin | repo marketplace `purposebus-local` at `./plugins/purposebus` | active-profile install, workspace publication, or public-directory submission |

No destination, tag, release, package upload, marketplace write, installation,
commit, or push is performed by release preparation.

