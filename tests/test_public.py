import unittest
from pathlib import Path

from purposebus.partition import Partition
from purposebus.public import (
    _project_unmet,
    partition_context,
    project_delivery,
    project_event,
    project_instance,
    project_message,
)


class PublicProjectionTest(unittest.TestCase):
    def test_partition_context_is_an_explicit_semantic_allowlist(self) -> None:
        partition = Partition(
            partition_id="path-sha256:abc",
            path=Path("/work/example"),
            source="explicit",
            state_root=Path("/private/state"),
            directory=Path("/private/state/partitions/abc"),
            database=Path("/private/state/partitions/abc/purposebus.sqlite3"),
        )

        self.assertEqual(
            partition_context(partition),
            {
                "partition_id": "path-sha256:abc",
                "path": "/work/example",
                "source": "explicit",
                "display_name": "example",
            },
        )

    def test_message_projection_drops_unknown_and_persistence_fields(self) -> None:
        projected = project_message(
            {
                "message_id": "msg_1",
                "producer_instance_id": "producer1",
                "topic": "build/result",
                "purpose": "report the build",
                "payload_kind": "text",
                "payload": "must-not-leak-by-default",
                "payload_text": "secret-by-default",
                "command_digest": "internal-digest",
                "future_database_column": "must-not-leak",
            }
        )

        self.assertEqual(
            projected,
            {
                "message_id": "msg_1",
                "producer_instance_id": "producer1",
                "topic": "build/result",
                "purpose": "report the build",
                "payload_kind": "text",
            },
        )

        self.assertEqual(
            project_message(
                {
                    "message_id": "msg_1",
                    "payload_kind": "text",
                    "payload": "explicit value",
                },
                include_payload=True,
            ),
            {
                "message_id": "msg_1",
                "payload_kind": "text",
                "payload": "explicit value",
            },
        )

    def test_instance_projection_drops_raw_process_observations(self) -> None:
        projected = project_instance(
            {
                "instance_id": "consumer1",
                "agent_id": "consumer",
                "objective": "consume results",
                "lifecycle_state": "active",
                "activity": "waiting",
                "liveness": "alive",
                "liveness_reason": "process_identity_matches",
                "host": "internal-host",
                "boot_id": "internal-boot",
                "pid": 123,
                "process_start": "internal-start",
                "waiting_since": "2026-09-04T00:00:00Z",
                "waiting_until": "2026-09-04T00:01:00Z",
                "waiting_selector": "sub-internal",
                "wait_valid": True,
                "wait_reason": "process_identity_matches",
                "future_observation": "must-not-leak",
            }
        )

        self.assertEqual(
            projected,
            {
                "instance_id": "consumer1",
                "agent_id": "consumer",
                "objective": "consume results",
                "lifecycle_state": "active",
                "activity": "waiting",
                "liveness": "alive",
                "liveness_reason": "process_identity_matches",
                "wait_valid": True,
                "wait_reason": "process_identity_matches",
            },
        )

    def test_delivery_payload_requires_an_explicit_payload_surface(self) -> None:
        record = {
            "delivery_id": "del-1",
            "state": "leased",
            "payload_kind": "text",
            "payload": "leased value",
        }

        self.assertNotIn("payload", project_delivery(record))
        self.assertEqual(
            project_delivery(record, include_payload=True)["payload"], "leased value"
        )

    def test_event_details_are_allowlisted_by_event_type(self) -> None:
        projected = project_event(
            {
                "sequence": 1,
                "entity_type": "instance",
                "entity_id": "consumer1",
                "event_type": "started",
                "at": "2026-09-04T00:00:00Z",
                "details": {
                    "agent_id": "consumer",
                    "objective": "consume values",
                    "pid": 123,
                    "future_detail": "must-not-leak",
                },
            }
        )

        self.assertEqual(
            projected["details"],
            {"agent_id": "consumer", "objective": "consume values"},
        )

    def test_nested_match_candidate_has_an_explicit_allowlist(self) -> None:
        projected = _project_unmet(
            {
                "subscription_id": "sub-1",
                "classification": "schema_mismatch",
                "reason": "schema differs",
                "candidates": [
                    {
                        "offer_id": "off-1",
                        "provider_agent_id": "provider",
                        "offer_purpose": "provide value",
                        "offer_topic_filter": "value/+",
                        "offer_schema_id": "schema-a",
                        "facts": {
                            "topic_filters_overlap": True,
                            "schemas_compatible": False,
                            "future_internal_fact": "must-not-leak",
                        },
                        "mismatch_reasons": ["schema_mismatch"],
                        "future_offer_column": "must-not-leak",
                    }
                ],
            },
            25,
        )

        candidate = projected["candidates"]["items"][0]
        self.assertNotIn("future_offer_column", candidate)
        self.assertEqual(
            candidate["facts"],
            {"topic_filters_overlap": True, "schemas_compatible": False},
        )


if __name__ == "__main__":
    unittest.main()
