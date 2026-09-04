# PurposeBus Codex Plugin local acceptance

Status: accepted for `T_CODEX_PLUGIN_PROTOTYPE`

Date: 2026-09-04

## Accepted candidate

- Plugin: `purposebus@purposebus-local`
- Version: `0.1.0+codex.20260904012439`
- Compatible CLI observed: `purposebus 0.1.0a0`
- Manifest SHA-256:
  `2742224ca4255094cce380595eca8f65a041a5d15dfd5bae081a776a86a799ef`
- Skill SHA-256:
  `9beb305f749f8a0147b86bc466e860f6b12b67836325b025ab63e258dc0f982e`

The source files and the installed Linux and Windows cache copies had matching
hashes. At this 0.1 acceptance boundary, both profiles ended with this Plugin
version installed and enabled. Later acceptance records describe subsequent
profile-specific changes.

## Fresh-session behavior

The current candidate passed these independent new-session checks:

| Surface and prompt class | Thread | Result |
| --- | --- | --- |
| Linux CLI, direct mutation workflow | `01a06a05-6ec1-7ec2-80a4-8f35eaf3490b` | Loaded the installed Skill and completed exactly nine authorized mutations. |
| Linux CLI, indirect/paraphrased discovery | `01a06a08-60ee-7e22-ad41-a79ac7730e44` | Activated the Skill without naming it and used only explicit, read-only public CLI commands. |
| Linux CLI, unrelated negative prompt | `01a06a08-611f-7391-bb79-80087b053b05` | Returned only `323`; no Skill or tool was used. |
| Linux CLI, cross-host boundary | `01a06a08-6150-7de0-a3b6-42b3ee895b21` | Explained the unsupported boundary without probing a Partition or running PurposeBus. |
| Desktop-profile WSL fresh turn | `01a06a0b-1b1b-7b23-ac84-95464b6e5aad` | Loaded the Skill from the Windows Codex home and read the fulfilled Request through the public CLI. |

The Windows-native Codex app-server independently returned the Plugin as
installed and enabled from `plugin/list`, and returned the enabled
`purposebus:purposebus` Skill from `skills/list`. The native GUI window itself
was not automated or visually observed; the evidence covers native App
discovery and the configured Desktop-to-WSL execution path separately.

## Request-response-acknowledgement workflow

The accepted isolated Partition was
`path-sha256:dfa0d6da051fde168a199544358cb6a76fb3d63c94abe324bae8cb1288a8adf7`.
The fresh session used only the public CLI, explicit `--partition`, explicit
`--state-dir`, JSON output, and the named Instance actors.

- Agents: `accept-requester`, `accept-provider`
- Instances: `accept-requester-1`, `accept-provider-1`
- Request/subscription: `accept-request-1`
- Offer: `accept-offer-1`
- Correlation: `corr_c0ba94c1c97b492994864b08691d2e84`
- Message: `msg_6409803b82f3478a9cfda231c518970e`
- Delivery: `del_2c82c86cfc5941f9b4ca0ea1b28cdad5`
- Idempotency key: `accept-response-v1`
- Payload schema: `purposebus.acceptance.v1`
- Final public state: `request_state=fulfilled` and
  `effective_request_state=fulfilled`

The underlying subscription lifecycle state was `cancelled`, which is the
expected internal consequence of fulfilling the one-shot Request; acceptance
uses the public Request fields above. No mutation was retried.

## Disable, uninstall, and raw CLI fallback

The Windows profile was temporarily changed only for
`plugins."purposebus@purposebus-local".enabled`. With it set to `false`,
`plugin list` reported the Plugin disabled and fresh thread
`01a06a0d-25ad-7953-9d9b-fa91cec96e29` reported that the PurposeBus Skill was
not available. The setting was restored, and the complete config file SHA-256
returned to its pre-test value.

`codex plugin remove purposebus@purposebus-local` then removed the Plugin from
the installed list and removed its versioned cache. The ordinary
`purposebus request show` command still returned the fulfilled Request. The
same candidate was reinstalled once and read back as installed and enabled.

## Validation and corrections

- Plugin validator: passed.
- Skill validator: passed.
- Plugin package tests: 3 passed.
- Full repository suite: `make check`, 35 tests passed.
- `git diff --check`: passed.

An initial boundary prompt unnecessarily inspected local state before refusing
cross-host work. The Skill now performs its supported-scope gate before any CLI
use. An initial workflow prompt also guessed nonexistent nested command forms.
The Skill now states that `publish`, `poll`, and `ack` are top-level commands.
Both corrections received a new cache-busted Plugin version and were revalidated
before the accepted sessions above.

The Linux profile contains an unrelated invalid `llmthink-trial` marketplace
source. Linux acceptance invocations used a non-persistent config override that
made that source resolve to this repository; no `llmthink-trial` setting or
artifact was changed. The Windows/Desktop profile has a persistent
`purposebus-local` marketplace registration and does not need that override.

One empty Partition record was accidentally initialized under the default
PurposeBus state root before the isolated `--state-dir` was applied. It was not
used for acceptance and was not deleted through direct storage access. Its path
is
`~/.local/state/purposebus/partitions/dfa0d6da051fde168a199544358cb6a76fb3d63c94abe324bae8cb1288a8adf7/purposebus.sqlite3`.

## Authority boundary

This acceptance establishes the local Skill-first Plugin and its fallback. It
does not authorize or establish publication, Git push, a public or workspace
directory listing, multi-agent trials, remote coordination, deployment, or the
unrelated secdat migration.
