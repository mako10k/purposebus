# PurposeBus Codex Plugin 1.0 candidate evidence

Status: locally verified; no publication or active-profile installation

Date: 2026-09-08

## Exact candidate

- Plugin: `purposebus@purposebus-local`
- Version: `1.0.0+codex.20260908092104`
- Components: Skill only
- Core compatibility: exactly `==0.2.0a1`
- Contract SHA-256:
  `38e80b49a735e7c8fad46027ad1fb0de7f3b4c91d5ac047c3b71f46d680f6c03`
- Plugin tree SHA-256:
  `2b02d722e3ce949164fff2398884d4f71150cf1fc710c1062c0f2defa144c383`
- Deterministic ZIP SHA-256:
  `7484ab48059bbdc95b87169486c78ce147ae8734a04613989968cc34f4743874`
- Package evidence SHA-256:
  `facc2c5398d4bced03133d7b48c76fa5826c224a604d835d0cb4f73bb300c55d`

The package evidence is stored locally at
`build/plugin-v1/2b02d722e3ce949164fff2398884d4f71150cf1fc710c1062c0f2defa144c383/evidence.json`.
It records Codex CLI `0.153.4`, PurposeBus `0.2.0a1`, Python `3.12.3`, manifest
and Skill validation, the three-file allowlist, credential-pattern absence,
deterministic archive generation, isolated installation and cache comparison,
uninstall readback, and raw CLI fallback.

## Fresh-session matrix

All sessions used a temporary `HOME`, `CODEX_HOME`, marketplace, working
directory, and PurposeBus state root. The candidate was installed from a copied
repo marketplace and removed afterward.

| Evaluation | Thread | Result | PurposeBus mutations |
| --- | --- | --- | ---: |
| Direct and request response | `01a0806d-1c76-71d2-9474-75da823efecb` | Skill activated; exact ten-call flow passed | 10 |
| Follow-up | same thread | Preserved request and correlation IDs; read `fulfilled` | 0 |
| Indirect | `01a08071-820e-7342-8dbe-da81a32d23b9` | Activated from a purpose-oriented prompt without the Plugin name | 0 |
| Negative | `01a08072-fe2a-7300-ab41-676aa8854ad9` | Returned `323`; no Plugin Skill or PurposeBus CLI use | 0 |
| Cross-host boundary | `01a08073-ac03-7fe1-9080-b0b632babe96` | Refused before PurposeBus CLI, Partition inspection, or network access | 0 |

The direct flow registered `v1-requester` and `v1-provider`, started
`v1-requester-1` and `v1-provider-1`, created request `v1-request-1` and offer
`v1-offer-1`, confirmed the provider's read-only `next` result contained the
request, and published text `42` with schema
`purposebus.plugin-v1.answer.v1`, correlation ID
`corr-plugin-v1-20260908`, and idempotency key
`plugin-v1-response-20260908`. The requester leased and acknowledged Delivery
`del_2373c4f389be449d8245a896cd1e5c02`; the response Message was
`msg_8e2d31e1a5ce449d8d7c6718ca1bd690`.

At evaluation time, public `request show` returned effective request state
`fulfilled`. Independent later readback returned durable `request_state` as
`fulfilled` and Delivery state as `acked`; its time-derived `effective_state`
had become `expired` after the request's five-minute expiry. The public event
list contained the nine post-initialization domain events in order. Together
with the command log's successful `init`, this accounts for all ten authorized
state-changing CLI calls and no retry.

## Log identities and isolation readback

The ignored local evaluation root is
`build/plugin-v1/evaluations/eval-2b02d722-cwNjycnW/`. Relevant SHA-256 values:

- direct JSONL: `12e480d8a3ae21d23b4c7bb03dce2f3058ab276867b4808497182dc845d0f350`
- direct final: `fe287b9a4a0df05b618b0833181cb1f6f0d5a5a0e074774b9b5e09613a8318a6`
- follow-up JSONL: `df84e9eb38de43e4c989b14b720d832a10a851fa30e9cc32ef17be63144ce025`
- indirect JSONL: `a53b052c717ef43433cedb798dddb68c8da020452212efe3d27c57ad60aa8dcf`
- negative JSONL: `d8b33ce839f53f1ee39c0c6e3bcdfae3569d7d7b23195c337e0e35abbc987e19`
- boundary JSONL: `bfea2715579b5fe2e4dd04c1c8d04f3ac3627aeff8805d33b87c34e77e01cd22`

The isolated Plugin and marketplace removal both read back empty, while the raw
`purposebus` CLI still reported `purposebus 0.2.0a1` and read the test request.
Before and after the run, the active profile retained these exact SHA-256 values:

- `.codex/config.toml`:
  `1223e3ea96d6199f237c0e987ba692b6588df3e8eb3ffd83d92dc480861dea23`
- installed Plugin manifest:
  `7592284c42cf39c52197734274523ec5e713cf84d24c0bbd26df6acd52bcd740`
- installed Plugin Skill:
  `ea1aed311df0def59f246b4e78a83eb909b2e3874fe374148f4f3f8c2fa868c2`

The active installed Plugin therefore remains
`0.2.0+codex.20260904090953`. Authentication was referenced by a read-only
symlink into the isolated `CODEX_HOME`; its content was neither copied nor
printed. A credential-pattern scan across the captured logs passed.

## Excluded harness attempt and remaining boundaries

Thread `01a08069-ee2e-7e50-86e2-019568a456e5` stopped with zero PurposeBus
mutations because the temporary home lacked an LLMThink storage directory. The
next fresh session used an explicit workspace-local storage path and passed its
audit before making any mutation. The stopped attempt is diagnostic harness
evidence, not part of the passing behavior matrix.

The resumed follow-up session could read PurposeBus state but could not acquire
the shared worktimectl lock because resumed `codex exec` did not preserve the
additional writable-directory setting. The parent session independently read
the shared work-time state before and after this phase; this sandbox limitation
does not establish a PurposeBus or Plugin failure.

No native Desktop GUI window was automated or visually observed. No active
profile was updated, and no workspace or public Plugin Directory submission,
marketplace publication, MCP or app addition, Connector use, commit, push,
release, deployment, remote transport, or cross-user coordination was attempted.
