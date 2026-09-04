# PurposeBus Codex Plugin post-trial surface decision

Status: accepted; Skill-only local surface frozen

Date: 2026-09-04

## Decision

PurposeBus retains a Skill-only Codex Plugin over the public `purposebus` CLI
for the 0.2 alpha. The package does not add an MCP server, `.mcp.json`,
`.app.json`, custom UI, authentication flow, or remotely operated service.

This is a post-trial selection, not a claim that PurposeBus must never use MCP.
MCP becomes a candidate only when measured requirements need a controlled tool
service, service-backed authentication or authorization, shared or remote state,
or another capability that cannot be met by the local CLI-backed Skill without
weakening its simpler lifecycle and failure boundary.

## Evidence boundary

The decision combines two different evidence classes:

- Observed PurposeBus evidence comes from the accepted local Plugin candidate
  and the bounded multi-agent trial. It covers two AI Agents, one human Agent,
  public CLI workflows, same-host durable state, failure recovery, fresh-session
  Plugin discovery, and the configured Desktop-to-WSL path.
- MCP capabilities come from current official OpenAI documentation. No
  PurposeBus MCP server was built or benchmarked, so MCP latency, reliability,
  approval behavior, and surface reach remain unmeasured for PurposeBus.

Official OpenAI documentation says to use Skills when instructions and existing
tools are sufficient, while an MCP server is appropriate when a Plugin must
connect to a service, expose controlled tools, authenticate users, or run on
operated infrastructure. It also states that MCP tools have input and optional
output schemas and that production servers use stable HTTPS endpoints with
authorization for private data or user actions:

- <https://developers.openai.com/plugins/concepts/plugins>
- <https://developers.openai.com/plugins/concepts/mcp-server>
- <https://developers.openai.com/plugins/build/plugins>

## Comparison

| Dimension | CLI-backed Skill | Optional MCP-backed integration | Decision basis |
| --- | --- | --- | --- |
| Supported surfaces | Verified in fresh Codex CLI sessions and through the configured ChatGPT desktop-to-WSL path when a compatible local CLI is available. | The Plugin architecture can expose server tools and structured results, but individual capability availability can remain surface-specific. PurposeBus surface reach was not tested. | Keep the verified local surfaces; do not infer broader support from the protocol or directory. |
| Authentication | PurposeBus adds no user-authentication layer. Access is bounded by the local OS, explicit Partition and state root, and the host sandbox and approval policy. | Can define authentication and authorization for a service and protect private data or actions. | No remote service or cross-user requirement was accepted, so an added authentication service has no current functional target. |
| Shared or remote state | Shares one durable local Partition only with processes that can access its explicit local state root. | Can place behavior behind operated infrastructure and a stable HTTPS endpoint. | The trial established same-host coordination only and explicitly excluded remote transport, federation, and cross-user authorization. |
| Typed tool schemas | Uses versioned `purposebus.*.v1` JSON results and CLI option validation, but invocation remains shell-command composition rather than MCP tool calls. | Tools declare names, descriptions, input schemas, and optional output schemas; the server validates requests. | Typed invocation would be useful but did not correct a measured failure. The Skill already prevented the raw CLI command-selection error. |
| Latency | One same-host publish-to-lease observation was 62 ms; concurrent CLI processes completed without lock failures, although per-command latency rose. | Adds at least a client/server boundary; no PurposeBus MCP implementation was benchmarked, so neither improvement nor regression is established. | Do not substitute architectural expectation for measured need. |
| Approvals and permissions | The host sandbox and approval policy remain authoritative. The trial's authorized writes completed without an extra prompt in the explicit writable state root. | Could add server-side authorization, while client approval and workspace policy would remain separate controls. PurposeBus behavior was not tested. | Preserve the already verified boundary; do not add a second authorization plane without an accepted use case. |
| Failure containment | Short-lived CLI calls, explicit Partition selection, public-only access, bounded polling, versioned results, and read-before-retry rules fail closed without a resident PurposeBus process. | Central validation and request observability are possible, but endpoint, transport, authentication, deployment, and server lifecycle failures would also enter scope. | Trial failures were ownership-diagnostic gaps, not missing service containment. Address those gaps directly in alpha hardening. |
| Distribution | Repo marketplace package for local testing and controlled team source use; availability can vary by surface. | Public Plugins can use the universal directory, and packages may include local or remote MCP dependencies. | No workspace or public-directory distribution proposal is accepted by this task. |

## Frozen supported surface

The accepted 0.2-alpha surface is:

1. A repo-packaged Skill that invokes only the public, versioned `purposebus`
   CLI.
2. Codex CLI with a compatible local executable and explicit Partition path.
3. The ChatGPT desktop app only through the verified Plugin discovery and
   configured local-to-WSL execution path. The native GUI interaction itself
   remains unobserved.
4. Deterministic JSON reads and explicitly authorized mutations with exact
   Agent or Instance identity.
5. The ordinary CLI as the independent fallback when the Plugin is disabled or
   uninstalled.

The following surfaces and capabilities are unsupported and unverified for this
candidate: Codex IDE, Codex web or cloud, mobile, remote environments without
the accepted local CLI path, ChatGPT without local shell access, cross-host or
cross-user coordination, remote transport, federation, automatic delegation,
secret resolution, custom UI, and MCP tools or resources.

Unsupported means outside this accepted contract; it does not mean the surface
is impossible. Adding any item requires a separate requirement and evidence.

## Alpha handoff

`T_ALPHA_HARDENING` may implement only the accepted Skill-only surface and the
bounded trial findings. Its Plugin-specific work is limited to ownership
diagnostics and guidance, the two verified recovery cases, package and
compatibility checks, fresh-session behavior, permission-boundary checks, and
disable or uninstall fallback. An MCP scaffold is not an alpha intermediate or
deliverable.

## Distribution and authority boundary

The current distribution is the repository marketplace source. This decision
does not propose or authorize workspace distribution, a public Plugin Directory
submission, installation outside the accepted test scope, an MCP deployment,
commit, push, release, or deployment. Any later distribution proposal must name
the target surface, audience, package revision, authentication model, and
read-back procedure, and must receive separate implementation and publication
authority.

This record completes `T_CODEX_PLUGIN_SURFACE_DECISION` and freezes
`CODEX_PLUGIN_SURFACE_FROZEN`.
