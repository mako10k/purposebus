# PurposeBus 1.0.0 candidate evidence

Status: local release preparation complete; publication authorization pending

Date: 2026-09-08

## Exact candidate

- Base Git HEAD: `2a2b3a68c8f44a4107268e4fd51949106a37d486`
- Final normalized source SHA-256:
  `8b66354367caa66a5a34e2630b91480affbc4702c1ab76e90dd9777d07b0b54a`
- Core: `purposebus 1.0.0`
- Plugin: `purposebus@purposebus-local`
  `1.0.0+codex.20260908103255`, Skill only
- MCP adapter: `purposebus-mcp 0.1.0a0`, read only
- Controller policy package: `purposebus-codex-controller 0.0.0a0`, non-runnable
- Release contract SHA-256:
  `8144f381cceb47ce725dd3864b1d09e4d5ad6601d9ebc44de77a21092978a705`
- Final PERT document digest:
  `sha256:9c539c71f14b3f2733b375e212f547358d94fe5633f0e4886a277ac3704dcb8c`

The base HEAD is the independently read-back local and GitHub
`feature/local-mvp` revision. The candidate itself remains uncommitted and is
therefore identified by the normalized source digest, not by a commit, tag, or
server-side candidate ref.

## Immutable local artifacts

The final release directory is
`build/v1/8b66354367caa66a5a34e2630b91480affbc4702c1ab76e90dd9777d07b0b54a/`.

| Artifact | SHA-256 |
| --- | --- |
| source TAR | `8b66354367caa66a5a34e2630b91480affbc4702c1ab76e90dd9777d07b0b54a` |
| core wheel | `d5617dbd3caf33ba93d48a9b76248767fa76717bba0c1c4cd159d493590a8dcd` |
| MCP wheel | `06de86293564a42e48fdfab0546e76d0edd003704a28e702fd461b097217ef8d` |
| controller wheel | `d4797e1463c0bf5cd977f216e390ec98cf5000847aaba3fa4e1a1040a2017273` |
| Plugin ZIP | `d039d8f5d3276d0c3def88a743a886d139cb1d66e093025843831c5253d5b884` |
| rollback core wheel | `195de2c97bd21a25580d966e762999459e81208d26e65225802c899aa8405cb8` |
| rollback Plugin ZIP | `7484ab48059bbdc95b87169486c78ce147ae8734a04613989968cc34f4743874` |
| release manifest | `522b372038af45f617f8d303d77c00c3249a92b9bc85fd294977ace23bebc4fe` |
| release evidence | `1432ff7e384f551bc6cc198e0e515096455678b8b77c1c12f9fdcb452750ce51` |

The three candidate wheels reproduced byte-for-byte across two builds. The
Plugin ZIP was also deterministic.

## Acceptance results

- Plugin Creator manifest validation: passed
- Skill structural validation: passed
- Core source suite: 65 tests passed
- MCP integration suite: 14 tests passed
- Controller policy suite: 2 tests passed
- Bounded load: 20 processes over 4 workers completed within the timeout
- Corrupt state: failed closed, preserved corrupt bytes, and recovered only in
  a separate empty state root
- Core transition: `0.2.0a1 -> 1.0.0 -> 0.2.0a1 -> 1.0.0` preserved schema-1
  state without migration or mutation
- Plugin transition: predecessor install, candidate upgrade, uninstall,
  reinstall, rollback, and final removal all passed in an isolated profile
- Active Codex profile hashes and installed Plugin version remained unchanged

The fresh-session matrix in `release/v1-plugin-evaluations.json` passed direct
request/response, same-thread follow-up, indirect Skill activation, a negative
control, and the cross-host refusal boundary. The direct evaluation performed
exactly ten PurposeBus mutations and ended with Request `release-request-1`
fulfilled, Message `msg_4a4f057bc8534ca8a03173a7bd0b67b6`, and Delivery
`del_02339e27d6e3422f9098d3cf131bc6d5` acknowledged. The one harness attempt
whose work-time prerequisite was misrouted remains explicitly excluded.

## Completion and authority boundary

`T_V1_RELEASE_PREP` is complete. `T_PUBLISH_V1_0_0` remains behind the pending
`V1_RELEASE_AUTHORIZATION` owner criterion. This evidence does not authorize a
commit, push, tag, release, registry upload, active-profile installation,
marketplace or public-directory write, workspace publication, deployment,
Connector use, or PurposeBus mutation outside isolated tests.

The native Desktop GUI, public clean installation, signing, package registries,
workspace publication, and public Plugin Directory behavior remain unverified.
