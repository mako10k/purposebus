# PurposeBus 0.1.0 MVP acceptance map

Status: accepted by the owner for candidate
`09cdd3e491587380484ab1d2a9a36b1bfacea5f9`

Date: 2026-08-31

This map binds the twelve normative acceptance conditions that existed at the
0.1 acceptance boundary to isolated executable evidence. Condition 13 was added
later for the unaccepted 0.2.0a1 public-response candidate and does not
retroactively change the owner receipt. Owner
acceptance is recorded in `plans/purposebus-roadmap.pert` as receipt
`RCPT_MVP_0_1_OWNER_20260831`. That receipt does not grant publication
authority or claim production readiness.

| Condition | Primary executable evidence |
| --- | --- |
| 1. AI and human Agent registry views | `test_human_and_json_registry_views` |
| 2. Partition-local purpose/schema matching and explained mismatch | `test_registry_match_and_schema_unmet`, `test_partition_isolation_and_private_permissions` |
| 3. Independent durable fan-out and acknowledgement | `test_durable_fanout_ack_and_idempotency` |
| 4. Lease-expiry recovery across processes | `test_lease_expiry_redelivers_same_delivery` |
| 5. Visible bounded wait and killed-process invalidation | `test_blocking_poll_is_visible_and_clears_after_message`, `test_killed_wait_is_not_projected_as_waiting` |
| 6. PID reuse does not acquire an old Instance | `test_wrong_start_identity_detects_pid_reuse` |
| 7. Human offline mailbox and acknowledgement | `test_human_agent_can_inspect_and_ack_offline_mailbox_directly`, `test_direct_agent_ack_does_not_steal_active_instance_lease` |
| 8. No cross-Partition discovery or delivery | `test_partition_isolation_and_private_permissions` |
| 9. Producer-scoped idempotent publication | `test_durable_fanout_ack_and_idempotency`, `test_idempotency_key_rejects_changed_content` |
| 10. Read-only, explained `next --format json` | `test_next_reports_matching_request_heartbeat_and_stale_warning`, `test_next_and_status_are_read_only`, `test_global_options_are_accepted_after_nested_subcommands` |
| 11. Complete help and remediation routes | `test_help_routes_expose_catalog_and_integration_contract`, `test_parser_errors_follow_requested_json_format` |
| 12. Corrupt or unsupported state fails closed | `test_existing_unknown_schema_is_not_modified_by_init`, `test_corrupt_sqlite_state_fails_closed` |

Development evidence for condition 13 is
`test_public_v2_projection_excludes_persistence_and_process_internals`,
`test_resource_collections_have_a_bounded_result_contract`, and
the strict projection tests in `tests/test_public.py`, plus
`test_human_read_surfaces_use_command_specific_renderers` and
`test_human_poll_prints_payload_and_exact_ack_step`. It requires separate
candidate acceptance.

The same suite also verifies explicit mutation actors and ownership denial,
ordinary and retained Request correlation, Request expiry, artifact-digest
placement, deterministic JSON at a fixed time, payload and query bounds,
private state permissions, bounded redelivery, concurrency, and retained
delivery.

Run the source-tree acceptance evidence with:

```sh
make check
```

The clean-install smoke check creates an isolated virtual environment, installs
the repository candidate, verifies `purposebus --version`, and initializes a
temporary explicit Partition and state directory through the installed console
entry point. It was rerun successfully for the accepted candidate before the
owner acceptance receipt was recorded.
