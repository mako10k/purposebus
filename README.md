# PurposeBus

PurposeBus is a purpose-aware coordination bus for human and AI agents. It combines
agent discovery, purpose-bearing subscriptions and offers, observable instance
state, and durable publish/ack delivery inside an explicit project partition.

Status: locally verified PurposeBus core package (`1.0.0`) and compatible Codex
Plugin release package; publication authorization pending. The package remains
a same-host, same-user local coordination system, not a production deployment
claim.

## Run the prototype

PurposeBus requires Python 3.11 or newer and has no runtime dependencies outside the
standard library.

```sh
python3 -m venv .venv
.venv/bin/pip install -e .
. .venv/bin/activate
purposebus --format json init
purposebus help usecases
```

The default Partition is the canonical Git worktree containing the current
directory. State is written outside the checkout under the XDG state directory.
Use `--partition PATH` and `--state-dir PATH` for explicit integration or test
boundaries.

One minimal information exchange is:

```sh
purposebus agent register producer --kind ai --description "publishes build results"
purposebus agent register consumer --kind ai --description "reads build results"
purposebus instance start producer --id producer-1 --objective "report the build"
purposebus instance start consumer --id consumer-1 --objective "inspect the build"
purposebus subscription add build/result --instance consumer-1 \
  --purpose "decide whether the build is usable" --id build-consumer
purposebus offer add build/result --instance producer-1 \
  --purpose "provide the current build result" --id build-provider
purposebus publish build/result --instance producer-1 --purpose "report the build" \
  --json-payload '{"ok":true}' --idempotency-key build-42
purposebus poll --instance consumer-1 --wait 5s
```

After handling the leased payload, run the exact `Next:` acknowledgement command
printed by human output. JSON integrations use
`.result.deliveries.items[].next.command` while preserving the same Partition and
state configuration.

Use `--format json` before or after a subcommand for versioned
`purposebus.*.v2` documents. Each document exposes the resolved Partition and
the explicit acting identity, or `null` for an operator-style read. If a
publish response is lost, do not blindly resend. Resolve the result first:

```sh
purposebus --format json message list --producer producer-1 --idempotency-key build-42
```

Raw secrets must not be placed in payloads. An opaque artifact reference is
transported as metadata only; PurposeBus never resolves it or grants authority to read
it. `--artifact-digest` is valid only together with `--reference`.

Lifecycle changes name their actor explicitly, for example
`purposebus subscription pause SUBSCRIPTION_ID --agent AGENT_ID`. An Agent-owned
queued or lease-expired Delivery can be acknowledged without inventing a live
Instance by using the exact ID from inspection with
`purposebus ack ID --agent AGENT_ID`; an active
Instance lease cannot be taken this way.

## Requirements baseline

- [Intent and assumptions](docs/intent.md)
- [Normative requirements](docs/requirements.md)
- [Public response contract](docs/public-response-contract.md)
- [Use cases and effect checks](docs/use-cases.md)
- [Reviewable LLMThink reasoning](docs/requirements.think)
- [Requirements self-review](docs/reviews/requirements-baseline-review-2026-08-31.md)

The normative source of truth is `docs/requirements.md`. The `.think` document
records how the initial decisions were reached; it does not override the
requirements.

## CLI navigation

PurposeBus exposes an English, agent-neutral CLI with human-readable output and
versioned JSON results. Start with:

```text
purposebus --help
purposebus help usecases
purposebus help concepts
purposebus help partitions
purposebus help agent
purposebus COMMAND --help
```

`purposebus next` is the primary read-only navigation command for an agent. It reports
unread deliveries, matching requests, acknowledgements, heartbeat work, and
stale-state warnings without authorizing unrelated work.

The direct SQLite architecture, verified behavior, and remaining experiment
frontier are recorded in [the implementation status](docs/implementation-status.md).

## Codex Plugin prototype

The repository includes a local, Skill-first Codex Plugin under
`plugins/purposebus/` and a repo marketplace at
`.agents/plugins/marketplace.json`. The Plugin uses only the public
`purposebus` CLI and does not access SQLite or add an MCP server. Its supported
surfaces, identity and permission rules, installation boundary, and validation
status are defined in [the Codex Plugin contract](docs/codex-plugin.md).

Creating the repository package does not install or publish the Plugin. A new
Codex or ChatGPT desktop session is required after a separately authorized
local installation.

The exact release Plugin candidate is
`1.0.0+codex.20260908103255`, compatible with exactly PurposeBus `1.0.0`.
Build and exercise the complete core and Plugin release package with:

```sh
make verify-v1
```

The deterministic archive identity, fresh Codex CLI session matrix, request
response identifiers, and unchanged-profile readback are in
[the 1.0.0 release preparation record](docs/v1-release-prep.md).
No active-profile installation or publication is implied.

## Optional local read-only MCP adapter

An experimental, separately packaged MCP server is available under
`integrations/purposebus_mcp/`. It exposes six bounded read-only tools over
local stdio and invokes only the public `purposebus 1.0.0` CLI against
operator-configured Partition aliases. It does not modify the existing Plugin,
open SQLite directly, mutate PurposeBus, use a network listener, or launch
Codex or subagents.

The exact tool, compatibility, Partition, failure, and installation boundaries
are defined in [the local read-only MCP contract](docs/mcp-readonly-contract.md)
and [ADR-0001](docs/adr/0001-add-local-read-only-mcp.md). A separate
`purposebus_codex_controller` package is policy-only and non-runnable; Codex
lifecycle control remains a later, separately authorized phase.

The exact non-editable package hashes, test results, exclusions, and owner
acceptance receipt are recorded in
[the beta candidate evidence](docs/beta-readonly-mcp-acceptance-2026-09-08.md).

## Local RC hardening

The locally verified RC candidate freezes the accepted package, public JSON,
MCP, and Skill-only Plugin boundaries in `release/rc-contract.json`. Its verifier
creates a normalized source snapshot, reproducible wheels, isolated core and
Plugin upgrade/rollback evidence, bounded-load results, and fail-closed
corruption recovery evidence without changing an active profile:

```sh
make verify-rc
```

See [the RC hardening runbook](docs/rc-hardening.md) and
[ADR-0002](docs/adr/0002-freeze-rc-compatibility-and-provenance.md). Receipt
`RCPT_V0_9_RC_OWNER_20260908` records owner acceptance of the local RC contract;
it does not authorize installation, publication, release, or deployment.

## Development checks

```sh
make check
```

Optional integration checks require an isolated environment with the local
integration packages and their declared dependencies installed:

```sh
make check-integrations PYTHON=/path/to/ephemeral-venv/bin/python
```

The acceptance suite uses isolated temporary Partitions and state roots; it
does not touch the developer's live queue.

## Provenance checks

The requirements baseline is represented in the local SealGraph repository.
After the baseline has been sealed, use:

```text
sealgraph fsck
sealgraph graph
sealgraph stale --frontier
```

`.sealgraph/` is generated by `sealgraph`; do not edit it manually.
