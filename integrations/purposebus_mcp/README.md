# PurposeBus local read-only MCP server

This optional package exposes six read-only PurposeBus tools over local stdio.
Every operation invokes the public `purposebus 1.0.0` CLI with an explicit,
operator-configured Partition path. It does not import PurposeBus internals,
open SQLite, listen on a network socket, mutate bus state, or launch agents.

The server must be configured with one or more aliases:

```text
purposebus-mcp --partition project=/absolute/path/to/project
```

Tool callers see only `project`, not a path parameter. Configuration and use in
a Codex or ChatGPT client are separate installation and profile changes; this
repository package does not perform either action.

See [`../../docs/mcp-readonly-contract.md`](../../docs/mcp-readonly-contract.md)
for the normative integration boundary.
