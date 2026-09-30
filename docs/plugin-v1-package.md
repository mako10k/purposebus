# PurposeBus Codex Plugin 1.0 package contract

Status: locally verified package candidate; no publication or active-profile installation

Date: 2026-09-08

This document describes the immutable predecessor package. The 1.0.0 core
release successor and its new Plugin cachebuster are documented separately in
[the release preparation record](v1-release-prep.md).

## Package identity

- Plugin: `purposebus@purposebus-local`
- Version: `1.0.0+codex.20260908092104`
- Components: one Skill under `./skills/`
- Compatible core specifier: `==0.2.0a1`
- Required CLI output: `purposebus 0.2.0a1`
- Required response contracts: successful `purposebus.*.v2`, errors
  `purposebus.error.v1`, state schema `1`
- Machine contract: `release/plugin-v1-contract.json`

The exact core specifier is intentional. Only `0.2.0a1` has current package and
end-to-end evidence. The package does not claim that an untested later 0.2 or
1.0 core is compatible; final release preparation may revise the specifier only
after testing an exact replacement candidate.

## Surface and component boundary

The package remains a Skill-only adapter over the installed public CLI. It has
no bundled MCP server, app connection, hook, authentication implementation,
background service, credential, or direct SQLite access.

Supported:

- Codex CLI with access to the same local environment and compatible CLI.
- Codex in the ChatGPT desktop app when its local environment resolves the same
  compatible CLI and explicit Partition.

Unsupported:

- Codex cloud and IDE environments without that same local environment.
- ChatGPT web or mobile without the local shell boundary.
- Cross-host or cross-user coordination and authorization.

The host sandbox and approval policy remain authoritative. Plugin installation
does not grant permission to mutate PurposeBus, start an Agent or Instance,
acknowledge a Delivery, access a referenced artifact, or perform external work.

## Marketplace and install surface

The repo marketplace remains `purposebus-local`. Its entry points to
`./plugins/purposebus` and retains `AVAILABLE`, `ON_INSTALL`, and `Productivity`.
The marketplace is an authoring and local test source, not a public or workspace
publication record.

The install copy describes one same-host, same-user Partition and uses starter
prompts the Skill can complete. Publisher metadata is limited to facts already
present in the repository. Public privacy, terms, signing, review, and directory
metadata remain future publication inputs rather than invented local values.

## Acceptance matrix

The candidate is complete only when all of these are recorded against the exact
package:

1. Direct: an explicit PurposeBus read or coordination request activates the
   Skill and uses the public CLI with explicit paths and identities.
2. Indirect: a purpose-oriented local coordination request activates without
   requiring the Plugin name in the prompt.
3. Follow-up: a second turn reuses identifiers from the first result without
   inventing or changing them.
4. Negative: an unrelated request does not use PurposeBus.
5. Boundary: a cross-host request stops before local Partition inspection or a
   PurposeBus command.
6. Request response: an isolated request, response publication, poll, and
   acknowledgement reaches the public fulfilled state with no blind retry.

Package checks additionally cover manifest and Skill validation, marketplace
resolution, deterministic archive bytes, file allowlisting, credential-pattern
absence, isolated install and cache readback, uninstall, and independent raw CLI
fallback.

All six behavioral evaluations and the package checks passed against the exact
candidate above. Exact threads, artifact hashes, request and Delivery IDs,
isolation readback, and the one excluded harness attempt are recorded in
[the 2026-09-08 candidate evidence](plugin-v1-candidate-evidence-2026-09-08.md).

## Authority boundary

All installation, removal, state, and fresh-session tests use temporary homes,
Codex homes, marketplaces, working directories, and PurposeBus state. The active
Plugin profile and live PurposeBus state remain unchanged. This package work
does not authorize commit, push, workspace or public-directory publication,
release, deployment, MCP or Connector use, or downstream release preparation.
