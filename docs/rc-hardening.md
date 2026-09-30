# PurposeBus local RC hardening

Status: locally verified RC candidate; owner acceptance pending

The RC hardening target is the accepted, independently versioned beta package
set. `V0_9_RC_READY` is a roadmap milestone; it does not silently rename the
core, MCP, controller-policy, or Plugin packages.

## Frozen contract

`release/rc-contract.json` is the machine-readable compatibility boundary. It
pins package versions, all successful CLI schema identifiers, the error and
state schemas, six MCP tools, the Skill-only Plugin component set, critical
source hashes, load bounds, corruption behavior, and excluded authority.

The historical transition baseline is Git revision
`f089f0ed8cdad29f49d3ba593060728989783740`, containing core `0.2.0a0` and the
accepted alpha Plugin. The candidate remains core `0.2.0a1` with the accepted
read-only MCP beta additions.

## Run the local verifier

```sh
make verify-rc
```

The command creates a normalized source archive, builds the core, MCP, and
controller-policy wheels twice, compares their hashes, installs only from those
local wheels, and emits `build/rc/<source-sha256>/evidence.json`. Existing
immutable outputs are never overwritten with different bytes.

The same run uses a temporary Python environment and a temporary Codex home to
verify core and Plugin upgrade and rollback. It performs 20 status processes
with at most four concurrent workers and a ten-second per-process timeout.

## Corrupt-state recovery

PurposeBus does not rewrite, migrate, delete, or guess at a corrupt database.
It fails closed and preserves the corrupt bytes. The bounded operator recovery
path is:

1. stop using the affected state root;
2. preserve it for diagnosis or an explicitly authorized restore;
3. select a separate empty state root;
4. initialize that separate root and read back schema 1; and
5. import or reconstruct data only under a separately reviewed recovery plan.

The verifier proves steps 1 through 4 against isolated test data. It does not
claim data recovery from corrupt bytes.

## Environment and authority boundary

Each evidence manifest records the exact WSL/Linux, machine, Python, and Codex
versions exercised. It does not generalize that result to other distributions,
architectures, Python versions, Codex versions, or ChatGPT surfaces.

The verifier does not touch an active client profile, start a conversation or
agent, use a Connector, mutate a live PurposeBus Partition, contact a package
index, commit, push, submit, publish, release, or deploy. Current live
fresh-conversation pickup remains a separately authorized check when needed.

The owner-facing evidence record is intentionally excluded from the normalized
source snapshot so it can contain the completed snapshot and artifact hashes
without changing those hashes. That exclusion does not apply to runtime source,
package configuration, Plugin content, this runbook, or the machine-readable
contract.
