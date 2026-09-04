# PurposeBus 0.2.0 alpha acceptance

Status: accepted locally for `T_ALPHA_HARDENING`

Date: 2026-09-04

## Accepted candidate

- Core version: `purposebus 0.2.0a0`
- Plugin: `purposebus@purposebus-local`
- Plugin version: `0.2.0+codex.20260904024157`
- Core wheel SHA-256:
  `39fc70d20c946a0659d5bf7b895ee6d0dbbb94a53e89ab246605116b7f2da729`
- Plugin manifest SHA-256:
  `08226f9d6415fe6b68d38858bc87849f1dfede90b7103109e6db6673c2aff65d`
- Plugin Skill SHA-256:
  `ae1949d4b0b07df57b6a434670275bf0f9ca1d8391e5128b689f40c2580b98a9`

The candidate was accepted as content-identified workspace state based on local
HEAD `9ca22e782b77d58479866230df1d556c729d1cde`, before any commit or push of
these changes. A later commit or remote branch revision is a separately
authorized publication step and does not create a release.

## Source-cause correction and diagnostics

The trial exposed an ownership-diagnostic defect, not a delivery or durability
failure. The poll selection query combined explicit Subscription lookup with
owner eligibility. A named Subscription owned by another Instance therefore
produced the same no-row result as an empty eligible queue, and the CLI reported
`no_message`.

The contributing condition was that Agent-owned and Instance-owned recovery use
one poll path while their successor rules differ. The escape cause was missing
coverage for the three distinct explicit-poll outcomes: valid but empty,
missing Subscription, and existing Subscription with a different owner.

The correction validates a named poll target before recording wait state or
opening the delivery transaction. An unauthorized target now fails with exit 5,
schema `purposebus.error.v1`, and error `ownership_mismatch`; its hint names the
exact owner and the Agent-owned recovery alternative. The post-check event log
contained only the four setup events, so the rejected poll did not add
coordination state.

Regression coverage now proves both recovery contracts:

- an Instance-owned Subscription remains bound to its exact Instance identity,
  including across a later CLI process; and
- an Agent-owned durable Subscription can be recovered by another active
  Instance of the same Agent.

The installed Skill requires the compatible alpha CLI, inspects ownership
before an explicit poll, stops on `ownership_mismatch`, and does not reinterpret
that error as an empty queue or invent a replacement owner.

## State and isolated package evidence

The core wheel was built without dependency resolution or build isolation and
installed into a new virtual environment. A new explicit Partition initialized
and reported status through the installed wheel. The state root, `partitions`
directory, and Partition directory were mode `0700`; the database was `0600`.

The supported state schema remains version `1`; alpha does not introduce a
schema transition. A regression test reopens supported existing state and
compares its logical snapshot before and after initialization, proving that no
migration or mutation occurs. Unknown and corrupt state continue to fail closed.

The project version, runtime `purposebus.__version__`, and current README status
are checked together. This prevents a version bump from leaving the packaged
README or runtime metadata on an older candidate version.

The Plugin was copied separately into the isolated package root. Its manifest
and Skill hashes matched the source candidate, and both the Plugin validator and
Skill validator passed. The manifest test binds the cache-busted Plugin version,
core compatibility, Skill-only component set, marketplace resolution, and
absence of direct storage access.

## Fresh-session and permission-boundary evidence

Official Plugin testing guidance calls for exercising each capability and
retaining the prompts and results as evaluation evidence:
<https://developers.openai.com/plugins/deploy/connect-chatgpt>.

Two independent ephemeral Codex sessions loaded the installed alpha Skill:

| Thread | Prompt class | Result |
| --- | --- | --- |
| `01a06a4d-eed3-70a2-8e1a-700f10f57ca4` | Explicit read-only Instance recovery | Confirmed `purposebus 0.2.0a0`; read only public CLI state; correctly rejected successor polling of an Instance-owned Subscription; performed no poll or mutation. |
| `01a06a51-bbef-7752-bb1e-a5b7527f67b8` | Cross-host permission boundary | Stopped at the unsupported boundary without running any `purposebus` command or inspecting a Partition, SQLite, or the network. |

Both sessions used a read-only sandbox. Their mandatory `worktimectl agent`
attempt could not create its lock file in that sandbox; this is recorded as a
session-harness limitation, not a PurposeBus result. The orchestrating session
performed its normal work-time readbacks outside that sandbox.

## Install, uninstall, and fallback

The Linux profile was updated once from the accepted 0.1 Plugin to the alpha
candidate using the repository marketplace. Independent readback reported the
alpha installed and enabled from the expected source, and its installed
manifest and Skill hashes matched the source candidate.

The core alpha is installed independently with pipx at
`~/.local/bin/purposebus`. Its persistent wheel is stored under
`~/.local/share/purposebus/wheels/`, and pipx metadata, package metadata, import
version, and CLI output all report `0.2.0a0`. The repository `.venv` remains an
editable install and reports the same version.

The alpha Plugin was then removed once for the uninstall fallback check. While
it was absent from the installed list, the ordinary CLI still reported
`purposebus 0.2.0a0` and read the isolated Partition through
`purposebus.status.v1`. The exact alpha Plugin was reinstalled once and read
back as installed and enabled with matching hashes. The Windows/Desktop profile
was not changed in this task; its earlier 0.1 acceptance remains historical
evidence, not proof of an installed 0.2 candidate there.

## Verification summary

- Full repository suite: `make check`, 40 tests passed in 21.840 seconds.
- Plugin validator: passed.
- Skill validator: passed.
- `git diff --check`: passed after the implementation and evidence records were
  added.
- Public ownership smoke: exit 5 with `ownership_mismatch` and no added event.
- Isolated wheel, explicit state, private permissions, and Plugin copy: passed.
- Installed Plugin update, fresh-session discovery, uninstall fallback, restore,
  and independent readback: passed.

## Authority boundary

This record accepts the bounded local 0.2.0 alpha candidate and completes
`T_ALPHA_HARDENING`. It does not authorize or establish a commit, push, tag,
release, package upload, workspace or public-directory publication, Windows
profile update, MCP implementation or deployment, remote coordination, or
production deployment.

The roadmap does not declare a separate acceptance criterion or owner receipt
for `V0_2_ALPHA_ACCEPTED`. This is the task's local engineering acceptance, not
the formal owner-receipt mechanism used for the 0.1 MVP gate.
