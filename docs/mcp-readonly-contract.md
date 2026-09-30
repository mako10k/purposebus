# PurposeBus local read-only MCP contract

Status: accepted for the bounded 0.5.0 beta scope; not installed in a client profile

Date: 2026-09-08

## Boundary

`integrations/purposebus_mcp` is an optional local adapter. It communicates over
stdio and invokes the public `purposebus 1.0.0` CLI. It does not import
PurposeBus internals, access SQLite directly, mutate PurposeBus, listen on a
network socket, resolve secrets, use a Connector, or launch Codex or subagents.

The core package remains standard-library-only. The existing Codex Plugin stays
Skill-only and does not declare this server. Installing the package or changing
a client profile is a separate operation outside this contract.

## Server configuration

The operator must bind at least one tool-visible alias to an existing absolute
Partition path when the server starts:

```text
purposebus-mcp --partition project=/home/example/project
```

Aliases are lowercase identifiers. A tool caller supplies only an alias; no
tool accepts a filesystem path, executable, state directory, environment
variable, or arbitrary CLI argument. Duplicate aliases and duplicate resolved
paths are rejected. Instance and Request IDs use the pinned PurposeBus public
identifier syntax and cannot be parsed as CLI controls.

The server resolves `purposebus` from its startup environment, requires the
exact version string `purposebus 1.0.0`, and then invokes that resolved
executable without a shell. Child processes receive only the configured
Partition path and a small allowlist of non-secret environment variables.

## Tools

| Tool | Required inputs | Bounded optional inputs | Expected result schema |
| --- | --- | --- | --- |
| `purposebus_status` | `partition` | `limit` 1..1000 | `purposebus.status.v2` |
| `purposebus_list_agents` | `partition` | `limit` 1..1000 | `purposebus.agent-list.v2` |
| `purposebus_list_instances` | `partition` | `limit` 1..1000 | `purposebus.instance-list.v2` |
| `purposebus_match` | `partition` | `limit` 1..1000, `candidate_limit` 1..100 | `purposebus.match.v2` |
| `purposebus_next` | `partition`, `instance_id` | `limit` 1..1000 | `purposebus.next.v2` |
| `purposebus_get_request` | `partition`, `request_id` | none | `purposebus.request-show.v2` |

All tools advertise `readOnlyHint=true`, `destructiveHint=false`,
`idempotentHint=true`, and `openWorldHint=false`. These annotations describe the
implemented effects; they neither authorize follow-on work nor replace input,
identity, sandbox, or approval checks.

Each tool also publishes a stable human-readable title and an explicit input
schema. The server generates a structured-output schema from each typed result
contract. Names, titles, descriptions, schemas, and annotations are verified as
one public metadata surface.

Each tool returns the complete structured public CLI document. A successful
document must have exactly the top-level fields `schema`, `actor`, `partition`,
and `result`. Its schema must match the command, and its Partition path and
`source=explicit` must match the configured binding. Any mismatch fails closed.

## Failure contract

- An unknown alias, incompatible CLI version, timeout, execution failure,
  unexpected stderr, malformed JSON, unexpected success schema, added or
  missing top-level field, or Partition mismatch is an MCP tool error.
- A nonzero CLI result must be a `purposebus.error.v1` JSON object. Its public
  `error`, `message`, and `hint` are preserved in the tool error; any other
  schema fails closed.
- The server does not retry a command automatically. Read-only callers may make
  a new call after inspecting the error and current context.
- `purposebus_next` output remains guidance only. It is not permission to
  execute a recommended command or perform work outside the user's request.

## Verification contract

The integration suite must prove:

- all six adapters produce the expected v2 schema through a real isolated
  PurposeBus CLI and state root;
- MCP stdio initialization, tool discovery, and one structured status call
  succeed with the pinned SDK;
- advertised annotations, schemas and bounds match this document;
- arbitrary paths, duplicate bindings, unexpected versions, public schema
  drift, Partition drift and secret environment forwarding fail closed; and
- the core package remains dependency-free, the current Plugin manifest gains
  no MCP surface, and the controller package has no executable entry point.

Run the optional-package suite only in an environment where the three local
packages and the MCP dependency have been installed:

```text
make check-integrations PYTHON=/path/to/ephemeral-venv/bin/python
```

This test setup is not a Codex/ChatGPT client installation and does not prove
Connector or Codex lifecycle behavior.
