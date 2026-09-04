from __future__ import annotations

import json
import os
import sqlite3
import stat
import subprocess
import sys
import tempfile
import time
import unittest
from pathlib import Path

from purposebus.partition import resolve_partition


REPO_ROOT = Path(__file__).resolve().parents[1]


class PurposeBusCliTest(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.root = Path(self.temporary.name)
        self.state = self.root / "state"
        self.project_a = self.root / "project-a"
        self.project_b = self.root / "project-b"
        self.project_a.mkdir()
        self.project_b.mkdir()
        self.environment = dict(os.environ)
        self.environment["PYTHONPATH"] = str(REPO_ROOT / "src")

    def tearDown(self):
        self.temporary.cleanup()

    def command(self, partition: Path, *arguments: str, at: str | None = None) -> list[str]:
        command = [
            sys.executable,
            "-m",
            "purposebus",
            "--partition",
            str(partition),
            "--state-dir",
            str(self.state),
            "--format",
            "json",
        ]
        if at:
            command.extend(["--at", at])
        command.extend(arguments)
        return command

    def run_purposebus(
        self,
        partition: Path,
        *arguments: str,
        at: str | None = None,
        expected: int = 0,
    ) -> dict:
        result = subprocess.run(
            self.command(partition, *arguments, at=at),
            cwd=REPO_ROOT,
            env=self.environment,
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            timeout=15,
        )
        self.assertEqual(
            result.returncode,
            expected,
            msg=f"command={arguments}\nstdout={result.stdout}\nstderr={result.stderr}",
        )
        stream = result.stdout if result.returncode == 0 else result.stderr
        return json.loads(stream)

    def run_human(
        self,
        partition: Path,
        *arguments: str,
        at: str | None = None,
        expected: int = 0,
    ) -> subprocess.CompletedProcess[str]:
        command = self.command(partition, *arguments, at=at)
        command[command.index("--format") + 1] = "human"
        result = subprocess.run(
            command,
            cwd=REPO_ROOT,
            env=self.environment,
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            timeout=15,
        )
        self.assertEqual(
            result.returncode,
            expected,
            msg=f"command={arguments}\nstdout={result.stdout}\nstderr={result.stderr}",
        )
        return result

    def init(self, partition: Path | None = None, *, at: str | None = None) -> dict:
        return self.run_purposebus(partition or self.project_a, "init", at=at)

    def register(self, agent_id: str, *, kind: str = "ai", partition: Path | None = None, at=None):
        return self.run_purposebus(
            partition or self.project_a,
            "agent",
            "register",
            agent_id,
            "--kind",
            kind,
            "--description",
            f"{agent_id} description",
            at=at,
        )["result"]

    def start(self, agent_id: str, instance_id: str, *, partition: Path | None = None, at=None):
        return self.run_purposebus(
            partition or self.project_a,
            "instance",
            "start",
            agent_id,
            "--id",
            instance_id,
            "--objective",
            f"{agent_id} objective",
            "--lease",
            "1h",
            at=at,
        )["result"]

    def bootstrap_three(self, *, at=None):
        self.init(at=at)
        for agent in ("producer", "alice", "carol"):
            self.register(agent, at=at)
            self.start(agent, agent + "1", at=at)

    def database_for(self, partition: Path) -> Path:
        return resolve_partition(str(partition), str(self.state)).database

    def logical_state(self, partition: Path) -> dict[str, list[tuple]]:
        database = self.database_for(partition)
        connection = sqlite3.connect(f"file:{database}?mode=ro", uri=True)
        try:
            tables = (
                "metadata",
                "agents",
                "instances",
                "subscriptions",
                "offers",
                "messages",
                "retained",
                "deliveries",
                "events",
            )
            return {
                table: connection.execute(f"SELECT * FROM {table} ORDER BY rowid").fetchall()
                for table in tables
            }
        finally:
            connection.close()

    def wait_until_waiting(self, instance_id: str, timeout: float = 4) -> dict:
        deadline = time.monotonic() + timeout
        while time.monotonic() < deadline:
            status = self.run_purposebus(self.project_a, "status")["result"]
            instance = next(
                item
                for item in status["instances"]["items"]
                if item["instance_id"] == instance_id
            )
            if instance["activity"] == "waiting" and instance["wait_valid"]:
                return instance
            time.sleep(0.05)
        self.fail("Instance never became visibly waiting")

    def test_registry_match_and_schema_unmet(self):
        self.init()
        self.register("requester")
        self.register("provider")
        self.start("requester", "requester1")
        self.start("provider", "provider1")
        self.run_purposebus(
            self.project_a,
            "subscription",
            "add",
            "test/+",
            "--instance",
            "requester1",
            "--purpose",
            "validate build",
            "--schema",
            "test.result.v1",
            "--id",
            "sub1",
        )
        self.run_purposebus(
            self.project_a,
            "subscription",
            "add",
            "artifact/#",
            "--instance",
            "requester1",
            "--purpose",
            "consume artifact",
            "--schema",
            "artifact.v2",
            "--id",
            "sub2",
        )
        self.run_purposebus(
            self.project_a,
            "offer",
            "add",
            "test/#",
            "--instance",
            "provider1",
            "--purpose",
            "provide test results",
            "--schema",
            "test.result.v1",
            "--id",
            "off1",
        )
        result = self.run_purposebus(self.project_a, "match")["result"]
        match = result["matches"]["items"][0]
        self.assertEqual(match["subscription_id"], "sub1")
        self.assertEqual(match["subscriber_agent_id"], "requester")
        self.assertEqual(match["subscription_purpose"], "validate build")
        self.assertEqual(match["offer_purpose"], "provide test results")
        self.assertTrue(match["facts"]["topic_filters_overlap"])
        self.assertTrue(match["facts"]["schemas_compatible"])
        self.assertTrue(match["provider_live"])
        self.assertNotIn("unavailable", result)
        unmet = result["unmet"]["items"]
        self.assertEqual([item["subscription_id"] for item in unmet], ["sub2"])
        self.assertEqual(unmet[0]["classification"], "topic_filter_mismatch")
        self.assertIn(
            "topic_filter_mismatch",
            unmet[0]["candidates"]["items"][0]["mismatch_reasons"],
        )

    def test_durable_fanout_ack_and_idempotency(self):
        self.bootstrap_three()
        for owner, subscription in (("alice1", "suba"), ("carol1", "subc")):
            self.run_purposebus(
                self.project_a,
                "subscription",
                "add",
                "build/result",
                "--instance",
                owner,
                "--purpose",
                "observe build",
                "--id",
                subscription,
            )
        first = self.run_purposebus(
            self.project_a,
            "publish",
            "build/result",
            "--instance",
            "producer1",
            "--purpose",
            "report build",
            "--json-payload",
            '{"ok":true}',
            "--idempotency-key",
            "build-1",
        )["result"]
        second = self.run_purposebus(
            self.project_a,
            "publish",
            "build/result",
            "--instance",
            "producer1",
            "--purpose",
            "report build",
            "--json-payload",
            '{"ok":true}',
            "--idempotency-key",
            "build-1",
        )["result"]
        self.assertEqual(first["message_id"], second["message_id"])
        self.assertFalse(first["deduplicated"])
        self.assertTrue(second["deduplicated"])
        self.assertEqual(first["delivery_count"], 2)
        readback = self.run_purposebus(
            self.project_a,
            "message",
            "list",
            "--producer",
            "producer1",
            "--idempotency-key",
            "build-1",
        )["result"]["items"]
        self.assertEqual([item["message_id"] for item in readback], [first["message_id"]])
        self.assertNotIn("payload_text", readback[0])
        self.assertNotIn("payload", readback[0])
        message = self.run_purposebus(
            self.project_a, "message", "show", first["message_id"], "--include-payload"
        )["result"]
        self.assertEqual(message["payload"], {"ok": True})

        alice_delivery = self.run_purposebus(
            self.project_a, "poll", "--instance", "alice1", "--lease", "10s"
        )["result"]["deliveries"]["items"][0]
        self.run_purposebus(
            self.project_a, "ack", alice_delivery["delivery_id"], "--instance", "alice1"
        )
        deliveries = self.run_purposebus(self.project_a, "delivery", "list")["result"]["items"]
        self.assertTrue(all("payload" not in item for item in deliveries))
        states = {item["subscription_id"]: item["effective_state"] for item in deliveries}
        self.assertEqual(states, {"suba": "acked", "subc": "queued"})

    def test_idempotency_key_rejects_changed_content(self):
        self.init()
        self.register("producer")
        self.start("producer", "producer1")
        base = (
            "publish",
            "state/current",
            "--instance",
            "producer1",
            "--purpose",
            "report state",
            "--idempotency-key",
            "same-key",
        )
        self.run_purposebus(self.project_a, *base, "--text", "one")
        error = self.run_purposebus(self.project_a, *base, "--text", "two", expected=5)
        self.assertEqual(error["error"], "conflict")

    def test_lease_expiry_redelivers_same_delivery(self):
        t0 = "2026-01-01T00:00:00Z"
        self.init(at=t0)
        self.register("producer", at=t0)
        self.register("consumer", at=t0)
        self.start("producer", "producer1", at=t0)
        self.start("consumer", "consumer1", at=t0)
        self.run_purposebus(
            self.project_a,
            "subscription",
            "add",
            "event/one",
            "--instance",
            "consumer1",
            "--purpose",
            "consume",
            "--id",
            "sub1",
            at=t0,
        )
        self.run_purposebus(
            self.project_a,
            "publish",
            "event/one",
            "--instance",
            "producer1",
            "--purpose",
            "produce",
            "--text",
            "payload",
            at=t0,
        )
        first = self.run_purposebus(
            self.project_a,
            "poll",
            "--instance",
            "consumer1",
            "--lease",
            "1s",
            at=t0,
        )["result"]["deliveries"]["items"][0]
        second = self.run_purposebus(
            self.project_a,
            "poll",
            "--instance",
            "consumer1",
            "--subscription",
            "sub1",
            "--lease",
            "1s",
            at="2026-01-01T00:00:02Z",
        )["result"]["deliveries"]["items"][0]
        self.assertEqual(first["delivery_id"], second["delivery_id"])
        self.assertEqual(second["attempt"], 2)

    def test_explicit_poll_distinguishes_empty_missing_and_owner_mismatch(self):
        self.init()
        self.register("consumer")
        self.start("consumer", "consumer1")
        self.start("consumer", "consumer2")
        self.run_purposebus(
            self.project_a,
            "subscription",
            "add",
            "owned/value",
            "--instance",
            "consumer1",
            "--purpose",
            "keep exact Instance ownership",
            "--id",
            "owned1",
        )

        empty = self.run_purposebus(
            self.project_a,
            "poll",
            "--instance",
            "consumer1",
            "--subscription",
            "owned1",
            expected=4,
        )
        self.assertEqual(empty["error"], "no_message")
        self.assertIn("purposebus poll --instance consumer1", empty["hint"])
        self.assertIn("purposebus next --instance consumer1", empty["hint"])
        missing = self.run_purposebus(
            self.project_a,
            "poll",
            "--instance",
            "consumer1",
            "--subscription",
            "missing",
            expected=3,
        )
        self.assertEqual(missing["error"], "not_found")
        mismatch = self.run_purposebus(
            self.project_a,
            "poll",
            "--instance",
            "consumer2",
            "--subscription",
            "owned1",
            expected=5,
        )
        self.assertEqual(mismatch["error"], "ownership_mismatch")
        self.assertIn("consumer1", mismatch["message"])
        self.assertIn("Agent-owned durable Subscription", mismatch["hint"])

    def test_agent_owned_delivery_recovers_through_successor_instance(self):
        start = "2026-01-01T00:00:00Z"
        self.init(at=start)
        self.register("producer", at=start)
        self.register("consumer", at=start)
        self.start("producer", "producer1", at=start)
        self.start("consumer", "consumer1", at=start)
        self.start("consumer", "consumer2", at=start)
        self.run_purposebus(
            self.project_a,
            "subscription",
            "add",
            "recovery/value",
            "--agent",
            "consumer",
            "--purpose",
            "allow successor Instance recovery",
            "--id",
            "agent-owned",
            at=start,
        )
        self.run_purposebus(
            self.project_a,
            "publish",
            "recovery/value",
            "--instance",
            "producer1",
            "--purpose",
            "exercise successor recovery",
            "--text",
            "recover",
            at=start,
        )
        first = self.run_purposebus(
            self.project_a,
            "poll",
            "--instance",
            "consumer1",
            "--subscription",
            "agent-owned",
            "--lease",
            "1s",
            at=start,
        )["result"]["deliveries"]["items"][0]
        second = self.run_purposebus(
            self.project_a,
            "poll",
            "--instance",
            "consumer2",
            "--subscription",
            "agent-owned",
            at="2026-01-01T00:00:02Z",
        )["result"]["deliveries"]["items"][0]
        self.assertEqual(first["delivery_id"], second["delivery_id"])
        self.assertEqual(second["attempt"], 2)
        acknowledged = self.run_purposebus(
            self.project_a,
            "ack",
            second["delivery_id"],
            "--instance",
            "consumer2",
            at="2026-01-01T00:00:03Z",
        )["result"]
        self.assertEqual(acknowledged["state"], "acked")

    def test_request_becomes_fulfilled_only_after_ack(self):
        self.init()
        self.register("requester")
        self.register("provider")
        self.start("requester", "requester1")
        self.start("provider", "provider1")
        request = self.run_purposebus(
            self.project_a,
            "request",
            "create",
            "answer/value",
            "--instance",
            "requester1",
            "--purpose",
            "answer question",
            "--schema",
            "answer.v1",
            "--id",
            "req1",
        )["result"]
        self.run_purposebus(
            self.project_a,
            "offer",
            "add",
            "answer/#",
            "--instance",
            "provider1",
            "--purpose",
            "provide answer",
            "--schema",
            "answer.v1",
            "--id",
            "off1",
        )
        next_result = self.run_purposebus(self.project_a, "next", "--instance", "provider1")["result"]
        self.assertIn(
            "req1", [item["entity_id"] for item in next_result["items"]["items"]]
        )
        self.run_purposebus(
            self.project_a,
            "publish",
            "answer/value",
            "--instance",
            "provider1",
            "--purpose",
            "respond",
            "--text",
            "42",
            "--schema",
            "answer.v1",
            "--correlation-id",
            request["correlation_id"],
        )
        response_available = self.run_purposebus(self.project_a, "request", "show", "req1")["result"]
        self.assertEqual(response_available["effective_request_state"], "response_available")
        delivery = self.run_purposebus(
            self.project_a, "poll", "--instance", "requester1", "--subscription", "req1"
        )["result"]["deliveries"]["items"][0]
        self.run_purposebus(
            self.project_a, "ack", delivery["delivery_id"], "--instance", "requester1"
        )
        fulfilled = self.run_purposebus(self.project_a, "request", "show", "req1")["result"]
        self.assertEqual(fulfilled["effective_request_state"], "fulfilled")

    def test_retained_message_reaches_late_subscriber(self):
        self.init()
        self.register("producer")
        self.register("consumer")
        self.start("producer", "producer1")
        self.start("consumer", "consumer1")
        publication = self.run_purposebus(
            self.project_a,
            "publish",
            "state/current",
            "--instance",
            "producer1",
            "--purpose",
            "publish current state",
            "--json-payload",
            '{"state":"ready"}',
            "--schema",
            "state.v1",
            "--retain",
        )["result"]
        self.assertEqual(publication["delivery_count"], 0)
        self.run_purposebus(
            self.project_a,
            "subscription",
            "add",
            "state/#",
            "--instance",
            "consumer1",
            "--purpose",
            "read current state",
            "--schema",
            "state.v1",
            "--id",
            "sub1",
        )
        delivery = self.run_purposebus(self.project_a, "poll", "--instance", "consumer1")[
            "result"
        ]["deliveries"]["items"][0]
        self.assertTrue(delivery["retained"])
        self.assertEqual(delivery["payload"], {"state": "ready"})
        self.assertEqual(delivery["next"]["action"], "ack")
        self.assertEqual(
            delivery["next"]["command"],
            f"purposebus ack {delivery['delivery_id']} --instance consumer1",
        )

    def test_human_agent_has_offline_mailbox(self):
        self.init()
        self.register("producer")
        self.register("operator", kind="human")
        self.start("producer", "producer1")
        self.run_purposebus(
            self.project_a,
            "subscription",
            "add",
            "notice/operator",
            "--agent",
            "operator",
            "--purpose",
            "receive notice later",
            "--id",
            "humanbox",
        )
        self.run_purposebus(
            self.project_a,
            "publish",
            "notice/operator",
            "--instance",
            "producer1",
            "--purpose",
            "notify operator",
            "--text",
            "ready",
        )
        self.start("operator", "operator1")
        delivery = self.run_purposebus(self.project_a, "poll", "--instance", "operator1")[
            "result"
        ]["deliveries"]["items"][0]
        self.assertEqual(delivery["subscription_id"], "humanbox")
        acknowledged = self.run_purposebus(
            self.project_a, "ack", delivery["delivery_id"], "--instance", "operator1"
        )["result"]
        self.assertEqual(acknowledged["state"], "acked")

    def test_human_agent_can_inspect_and_ack_offline_mailbox_directly(self):
        self.init()
        self.register("producer")
        self.register("operator", kind="human")
        self.start("producer", "producer1")
        self.run_purposebus(
            self.project_a,
            "subscription",
            "add",
            "notice/operator",
            "--agent",
            "operator",
            "--purpose",
            "receive notice while offline",
            "--id",
            "humanbox",
        )
        self.run_purposebus(
            self.project_a,
            "publish",
            "notice/operator",
            "--instance",
            "producer1",
            "--purpose",
            "notify operator",
            "--text",
            "ready",
        )
        delivery = self.run_purposebus(self.project_a, "delivery", "list")["result"]["items"][0]
        message = self.run_purposebus(
            self.project_a, "message", "show", delivery["message_id"], "--include-payload"
        )["result"]
        self.assertEqual(message["payload"], "ready")
        denied = self.run_purposebus(
            self.project_a, "ack", delivery["delivery_id"], "--agent", "producer", expected=5
        )
        self.assertEqual(denied["error"], "conflict")
        acknowledged = self.run_purposebus(
            self.project_a, "ack", delivery["delivery_id"], "--agent", "operator"
        )
        self.assertEqual(acknowledged["actor"], {"type": "agent", "id": "operator"})
        duplicate = self.run_purposebus(
            self.project_a, "ack", delivery["delivery_id"], "--agent", "operator"
        )["result"]
        self.assertTrue(duplicate["deduplicated"])

    def test_direct_agent_ack_does_not_steal_active_instance_lease(self):
        start = "2026-08-31T00:00:00Z"
        self.init(at=start)
        self.register("producer", at=start)
        self.register("operator", kind="human", at=start)
        self.start("producer", "producer1", at=start)
        self.start("operator", "operator1", at=start)
        self.run_purposebus(
            self.project_a,
            "subscription",
            "add",
            "notice/operator",
            "--agent",
            "operator",
            "--purpose",
            "receive notice",
            "--id",
            "humanbox",
            at=start,
        )
        self.run_purposebus(
            self.project_a,
            "publish",
            "notice/operator",
            "--instance",
            "producer1",
            "--purpose",
            "notify operator",
            "--text",
            "ready",
            at=start,
        )
        delivery = self.run_purposebus(
            self.project_a,
            "poll",
            "--instance",
            "operator1",
            "--lease",
            "10s",
            at=start,
        )["result"]["deliveries"]["items"][0]
        denied = self.run_purposebus(
            self.project_a,
            "ack",
            delivery["delivery_id"],
            "--agent",
            "operator",
            at="2026-08-31T00:00:05Z",
            expected=5,
        )
        self.assertEqual(denied["error"], "conflict")
        acknowledged = self.run_purposebus(
            self.project_a,
            "ack",
            delivery["delivery_id"],
            "--agent",
            "operator",
            at="2026-08-31T00:00:11Z",
        )["result"]
        self.assertEqual(acknowledged["state"], "acked")

    def test_ephemeral_subscription_requires_instance_and_stops_with_it(self):
        self.init()
        self.register("consumer")
        self.register("producer")
        self.start("consumer", "consumer1")
        self.start("producer", "producer1")
        self.run_purposebus(
            self.project_a,
            "subscription",
            "add",
            "temporary/#",
            "--agent",
            "consumer",
            "--purpose",
            "invalid agent-scoped ephemeral need",
            "--ephemeral",
            expected=2,
        )
        self.run_purposebus(
            self.project_a,
            "subscription",
            "add",
            "temporary/#",
            "--instance",
            "consumer1",
            "--purpose",
            "need data only during this run",
            "--ephemeral",
            "--id",
            "ephemeral1",
        )
        self.run_purposebus(
            self.project_a,
            "publish",
            "temporary/value",
            "--instance",
            "producer1",
            "--purpose",
            "exercise ephemeral cleanup",
            "--text",
            "value",
        )
        self.run_purposebus(self.project_a, "instance", "stop", "consumer1")
        subscription = self.run_purposebus(
            self.project_a, "subscription", "show", "ephemeral1"
        )["result"]
        self.assertEqual(subscription["state"], "cancelled")
        delivery = self.run_purposebus(self.project_a, "delivery", "list")["result"]["items"][0]
        self.assertEqual(delivery["state"], "expired")
        event_types = [
            item["event_type"]
            for item in self.run_purposebus(self.project_a, "events")["result"]["items"]
        ]
        self.assertIn("cancelled", event_types)

    def test_delivery_expires_and_redelivery_is_bounded(self):
        start = "2026-08-31T00:00:00Z"
        self.bootstrap_three(at=start)
        self.run_purposebus(
            self.project_a,
            "subscription",
            "add",
            "bounded/value",
            "--instance",
            "alice1",
            "--purpose",
            "exercise delivery attempts",
            "--id",
            "bounded1",
            at=start,
        )
        self.run_purposebus(
            self.project_a,
            "publish",
            "bounded/value",
            "--instance",
            "producer1",
            "--purpose",
            "exercise delivery attempts",
            "--text",
            "retry me",
            at=start,
        )
        for second in (0, 2, 4, 6, 8):
            delivery = self.run_purposebus(
                self.project_a,
                "poll",
                "--instance",
                "alice1",
                "--lease",
                "1s",
                at=f"2026-08-31T00:00:{second:02d}Z",
            )["result"]["deliveries"]["items"][0]
        self.assertEqual(delivery["attempt"], 5)
        self.run_purposebus(
            self.project_a,
            "poll",
            "--instance",
            "alice1",
            "--lease",
            "1s",
            at="2026-08-31T00:00:10Z",
            expected=4,
        )
        dead_letter = self.run_purposebus(
            self.project_a, "delivery", "list", at="2026-08-31T00:00:10Z"
        )["result"]["items"][0]
        self.assertEqual(dead_letter["state"], "dead_letter")
        self.assertEqual(dead_letter["attempt"], 5)

        self.run_purposebus(
            self.project_a,
            "publish",
            "bounded/value",
            "--instance",
            "producer1",
            "--purpose",
            "exercise expiry",
            "--text",
            "expire me",
            "--expires-in",
            "1s",
            at="2026-08-31T00:00:20Z",
        )
        self.run_purposebus(
            self.project_a,
            "poll",
            "--instance",
            "alice1",
            at="2026-08-31T00:00:22Z",
            expected=4,
        )
        deliveries = self.run_purposebus(
            self.project_a, "delivery", "list", at="2026-08-31T00:00:22Z"
        )["result"]["items"]
        self.assertEqual([item["state"] for item in deliveries], ["dead_letter", "expired"])

    def test_existing_unknown_schema_is_not_modified_by_init(self):
        self.init()
        database = self.database_for(self.project_a)
        connection = sqlite3.connect(database)
        connection.execute("UPDATE metadata SET value='99' WHERE key='schema_version'")
        connection.execute("DROP TABLE offers")
        connection.commit()
        connection.close()

        result = self.run_purposebus(self.project_a, "init", expected=5)
        self.assertEqual(result["error"], "conflict")
        connection = sqlite3.connect(database)
        try:
            schema_version = connection.execute(
                "SELECT value FROM metadata WHERE key='schema_version'"
            ).fetchone()[0]
            offer_table = connection.execute(
                "SELECT name FROM sqlite_master WHERE type='table' AND name='offers'"
            ).fetchone()
        finally:
            connection.close()
        self.assertEqual(schema_version, "99")
        self.assertIsNone(offer_table)

    def test_supported_state_reopens_without_migration_or_mutation(self):
        self.init(at="2026-01-01T00:00:00Z")
        before = self.logical_state(self.project_a)
        reopened = self.init(at="2026-01-02T00:00:00Z")
        after = self.logical_state(self.project_a)

        self.assertFalse(reopened["result"]["created"])
        self.assertEqual(reopened["result"]["metadata"]["schema_version"], "1")
        self.assertEqual(before, after)

    def test_corrupt_sqlite_state_fails_closed(self):
        self.init()
        database = self.database_for(self.project_a)
        database.write_bytes(b"not a sqlite database")
        result = self.run_purposebus(self.project_a, "status", expected=5)
        self.assertIn(result["error"], {"conflict", "storage_failure"})

    def test_parser_errors_follow_requested_json_format(self):
        result = subprocess.run(
            [sys.executable, "-m", "purposebus", "--format", "json", "--not-a-command"],
            cwd=REPO_ROOT,
            env=self.environment,
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            timeout=15,
        )
        self.assertEqual(result.returncode, 2)
        document = json.loads(result.stderr)
        self.assertEqual(document["schema"], "purposebus.error.v1")
        self.assertEqual(document["error"], "invalid_input")

    def test_json_status_is_deterministic_at_a_fixed_time(self):
        fixed = "2026-08-31T00:00:00Z"
        self.init(at=fixed)
        self.register("agent-a", at=fixed)
        command = self.command(self.project_a, "status", at=fixed)
        first = subprocess.run(
            command,
            cwd=REPO_ROOT,
            env=self.environment,
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            timeout=15,
        )
        second = subprocess.run(
            command,
            cwd=REPO_ROOT,
            env=self.environment,
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            timeout=15,
        )
        self.assertEqual(first.returncode, 0, msg=first.stderr)
        self.assertEqual(second.returncode, 0, msg=second.stderr)
        self.assertEqual(first.stdout, second.stdout)

    def test_global_options_are_accepted_after_nested_subcommands(self):
        self.init(at="2026-08-31T00:00:00Z")
        self.register("provider", at="2026-08-31T00:00:00Z")
        self.start("provider", "provider1", at="2026-08-31T00:00:00Z")
        command = [
            sys.executable,
            "-m",
            "purposebus",
            "next",
            "--instance",
            "provider1",
            "--partition",
            str(self.project_a),
            "--state-dir",
            str(self.state),
            "--at",
            "2026-08-31T00:00:01Z",
            "--format",
            "json",
        ]
        result = subprocess.run(
            command,
            cwd=REPO_ROOT,
            env=self.environment,
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            timeout=15,
        )
        self.assertEqual(result.returncode, 0, msg=result.stderr)
        document = json.loads(result.stdout)
        self.assertEqual(document["schema"], "purposebus.next.v2")
        self.assertEqual(document["actor"], {"type": "instance", "id": "provider1"})

    def test_mutations_expose_actor_and_enforce_owner_family(self):
        initialized = self.init()
        self.assertIsNone(initialized["actor"])
        registered = self.run_purposebus(
            self.project_a,
            "agent",
            "register",
            "alice",
            "--kind",
            "ai",
            "--description",
            "alice description",
        )
        self.assertEqual(registered["actor"], {"type": "agent", "id": "alice"})
        self.register("carol")
        started = self.run_purposebus(
            self.project_a,
            "instance",
            "start",
            "alice",
            "--id",
            "alice1",
            "--objective",
            "alice objective",
        )
        self.assertEqual(started["actor"], {"type": "instance", "id": "alice1"})
        self.start("carol", "carol1")
        added = self.run_purposebus(
            self.project_a,
            "subscription",
            "add",
            "owned/value",
            "--instance",
            "alice1",
            "--purpose",
            "own a value",
            "--id",
            "owned1",
        )
        self.assertEqual(added["actor"], {"type": "instance", "id": "alice1"})
        missing = self.run_purposebus(
            self.project_a, "subscription", "pause", "owned1", expected=2
        )
        self.assertEqual(missing["error"], "invalid_input")
        ambiguous = self.run_purposebus(
            self.project_a,
            "subscription",
            "pause",
            "owned1",
            "--agent",
            "alice",
            "--instance",
            "alice1",
            expected=2,
        )
        self.assertEqual(ambiguous["error"], "invalid_input")
        denied = self.run_purposebus(
            self.project_a,
            "subscription",
            "pause",
            "owned1",
            "--instance",
            "carol1",
            expected=5,
        )
        self.assertEqual(denied["error"], "conflict")
        paused = self.run_purposebus(
            self.project_a, "subscription", "pause", "owned1", "--agent", "alice"
        )
        self.assertEqual(paused["actor"], {"type": "agent", "id": "alice"})
        self.run_purposebus(
            self.project_a, "subscription", "resume", "owned1", "--instance", "alice1"
        )
        self.run_purposebus(self.project_a, "instance", "stop", "alice1")
        stopped = self.run_purposebus(
            self.project_a,
            "subscription",
            "cancel",
            "owned1",
            "--instance",
            "alice1",
            expected=5,
        )
        self.assertEqual(stopped["error"], "conflict")

    def test_request_delivery_requires_exact_correlation(self):
        self.init()
        self.register("requester")
        self.register("provider")
        self.start("requester", "requester1")
        self.start("provider", "provider1")
        request = self.run_purposebus(
            self.project_a,
            "request",
            "create",
            "answer/value",
            "--instance",
            "requester1",
            "--purpose",
            "need the exact response",
            "--schema",
            "answer.v1",
            "--correlation-id",
            "corr-exact",
            "--id",
            "request1",
        )["result"]
        self.assertEqual(request["correlation_id"], "corr-exact")
        for correlation in (None, "corr-other"):
            arguments = [
                "publish",
                "answer/value",
                "--instance",
                "provider1",
                "--purpose",
                "respond",
                "--text",
                "not accepted",
            ]
            if correlation:
                arguments.extend(["--correlation-id", correlation])
            publication = self.run_purposebus(self.project_a, *arguments)["result"]
            self.assertEqual(publication["delivery_count"], 0)
            state = self.run_purposebus(self.project_a, "request", "show", "request1")["result"]
            self.assertEqual(state["effective_request_state"], "open")
        wrong_schema = self.run_purposebus(
            self.project_a,
            "publish",
            "answer/value",
            "--instance",
            "provider1",
            "--purpose",
            "respond with wrong schema",
            "--text",
            "not accepted",
            "--schema",
            "answer.v2",
            "--correlation-id",
            "corr-exact",
        )["result"]
        self.assertEqual(wrong_schema["delivery_count"], 0)
        accepted = self.run_purposebus(
            self.project_a,
            "publish",
            "answer/value",
            "--instance",
            "provider1",
            "--purpose",
            "respond",
            "--text",
            "accepted",
            "--schema",
            "answer.v1",
            "--correlation-id",
            "corr-exact",
        )["result"]
        self.assertEqual(accepted["delivery_count"], 1)
        state = self.run_purposebus(self.project_a, "request", "show", "request1")["result"]
        self.assertEqual(state["effective_request_state"], "response_available")

    def test_retained_request_correlation_and_artifact_digest_rules(self):
        self.init()
        self.register("requester")
        self.register("provider")
        self.start("requester", "requester1")
        self.start("provider", "provider1")
        self.run_purposebus(
            self.project_a,
            "publish",
            "answer/retained",
            "--instance",
            "provider1",
            "--purpose",
            "retain unrelated answer",
            "--text",
            "wrong",
            "--correlation-id",
            "corr-wrong",
            "--retain",
        )
        request = self.run_purposebus(
            self.project_a,
            "request",
            "create",
            "answer/retained",
            "--instance",
            "requester1",
            "--purpose",
            "need retained answer",
            "--correlation-id",
            "corr-right",
            "--id",
            "retained-request",
        )["result"]
        self.assertEqual(request["effective_request_state"], "open")
        self.run_purposebus(
            self.project_a,
            "publish",
            "answer/retained",
            "--instance",
            "provider1",
            "--purpose",
            "retain correlated answer",
            "--text",
            "right",
            "--correlation-id",
            "corr-right-2",
            "--retain",
        )
        retained_match = self.run_purposebus(
            self.project_a,
            "request",
            "create",
            "answer/retained",
            "--instance",
            "requester1",
            "--purpose",
            "need matching retained answer",
            "--correlation-id",
            "corr-right-2",
            "--id",
            "retained-request-2",
        )["result"]
        self.assertEqual(retained_match["effective_request_state"], "response_available")
        invalid = self.run_purposebus(
            self.project_a,
            "publish",
            "artifact/value",
            "--instance",
            "provider1",
            "--purpose",
            "invalid digest placement",
            "--text",
            "inline",
            "--artifact-digest",
            "sha256:abc",
            expected=2,
        )
        self.assertEqual(invalid["error"], "invalid_input")
        reference = self.run_purposebus(
            self.project_a,
            "publish",
            "artifact/value",
            "--instance",
            "provider1",
            "--purpose",
            "valid opaque artifact",
            "--reference",
            "artifact://build/42",
            "--artifact-digest",
            "sha256:abc",
        )["result"]
        shown = self.run_purposebus(
            self.project_a, "message", "show", reference["message_id"]
        )["result"]
        self.assertEqual(shown["artifact_digest"], "sha256:abc")

    def test_expired_request_rejects_a_late_correlated_response(self):
        start = "2026-08-31T00:00:00Z"
        self.init(at=start)
        self.register("requester", at=start)
        self.register("provider", at=start)
        self.start("requester", "requester1", at=start)
        self.start("provider", "provider1", at=start)
        self.run_purposebus(
            self.project_a,
            "request",
            "create",
            "answer/late",
            "--instance",
            "requester1",
            "--purpose",
            "need a timely response",
            "--correlation-id",
            "corr-late",
            "--expires-in",
            "1s",
            "--id",
            "late-request",
            at=start,
        )
        publication = self.run_purposebus(
            self.project_a,
            "publish",
            "answer/late",
            "--instance",
            "provider1",
            "--purpose",
            "late response",
            "--text",
            "too late",
            "--correlation-id",
            "corr-late",
            at="2026-08-31T00:00:02Z",
        )["result"]
        self.assertEqual(publication["delivery_count"], 0)
        request = self.run_purposebus(
            self.project_a,
            "request",
            "show",
            "late-request",
            at="2026-08-31T00:00:02Z",
        )["result"]
        self.assertEqual(request["effective_request_state"], "expired")

    def test_partition_isolation_and_private_permissions(self):
        first = self.init(self.project_a)
        second = self.init(self.project_b)
        self.assertNotEqual(first["partition"]["partition_id"], second["partition"]["partition_id"])
        first_database = self.database_for(self.project_a)
        first_dir = first_database.parent
        self.assertEqual(stat.S_IMODE(first_dir.stat().st_mode), 0o700)
        self.assertEqual(stat.S_IMODE(first_database.stat().st_mode), 0o600)
        for partition in (self.project_a, self.project_b):
            self.register("producer", partition=partition)
            self.register("consumer", partition=partition)
            self.start("producer", "producer1", partition=partition)
            self.start("consumer", "consumer1", partition=partition)
            self.run_purposebus(
                partition,
                "offer",
                "add",
                "shared/value",
                "--instance",
                "producer1",
                "--purpose",
                "provide local value",
                "--id",
                "offer1",
            )
        self.run_purposebus(
            self.project_a,
            "publish",
            "shared/value",
            "--instance",
            "producer1",
            "--purpose",
            "publish only in project A",
            "--text",
            "A",
            "--retain",
        )
        self.run_purposebus(
            self.project_b,
            "subscription",
            "add",
            "shared/value",
            "--instance",
            "consumer1",
            "--purpose",
            "receive only project B values",
            "--id",
            "subscription1",
        )
        self.assertEqual(
            self.run_purposebus(self.project_b, "message", "list")["result"]["items"], []
        )
        self.assertEqual(
            self.run_purposebus(self.project_b, "delivery", "list")["result"]["items"], []
        )
        self.run_purposebus(
            self.project_b, "poll", "--instance", "consumer1", expected=4
        )
        for partition_dir in (
            self.database_for(self.project_a).parent,
            self.database_for(self.project_b).parent,
        ):
            for state_file in partition_dir.iterdir():
                if state_file.is_file():
                    self.assertEqual(stat.S_IMODE(state_file.stat().st_mode), 0o600)

    def test_public_v2_projection_excludes_persistence_and_process_internals(self):
        initialized = self.init()
        self.assertEqual(initialized["schema"], "purposebus.init.v2")
        self.assertEqual(
            set(initialized["partition"]),
            {"partition_id", "path", "source", "display_name"},
        )
        self.assertEqual(initialized["partition"]["path"], str(self.project_a))
        self.assertEqual(initialized["partition"]["display_name"], "project-a")
        self.assertNotIn("partition_id", initialized["result"]["metadata"])

        self.register("producer")
        started = self.run_purposebus(
            self.project_a,
            "instance",
            "start",
            "producer",
            "--id",
            "producer1",
            "--objective",
            "publish bounded results",
            "--pid",
            str(os.getpid()),
        )["result"]
        for field in (
            "host",
            "boot_id",
            "pid",
            "process_start",
            "wait_pid",
            "wait_boot_id",
            "wait_process_start",
            "waiting_since",
            "waiting_until",
            "waiting_selector",
        ):
            self.assertNotIn(field, started)

        publication = self.run_purposebus(
            self.project_a,
            "publish",
            "projection/value",
            "--instance",
            "producer1",
            "--purpose",
            "prove internal values stay internal",
            "--text",
            "value",
            "--idempotency-key",
            "projection-1",
        )["result"]
        self.assertNotIn("command_digest", publication)
        self.assertNotIn("payload_text", publication)

        messages = self.run_purposebus(self.project_a, "message", "list")["result"]
        self.assertNotIn("command_digest", messages["items"][0])
        status = self.run_purposebus(self.project_a, "status")["result"]
        self.assertNotIn("partition", status)
        self.assertEqual(
            set(status["storage"]),
            {
                "health",
                "state_schema_version",
                "max_delivery_attempts",
                "max_event_rows",
                "event_rows",
                "events_pruned",
            },
        )
        self.assertEqual(status["storage"]["health"], "ok")
        self.assertEqual(status["storage"]["state_schema_version"], "1")

    def test_resource_collections_have_a_bounded_result_contract(self):
        self.init()
        for agent_id in ("agent-a", "agent-b", "agent-c"):
            self.register(agent_id)

        result = self.run_purposebus(
            self.project_a, "agent", "list", "--limit", "2"
        )["result"]
        self.assertEqual([item["agent_id"] for item in result["items"]], ["agent-a", "agent-b"])
        self.assertEqual(
            result["page"],
            {"limit": 2, "returned": 2, "total": 3, "truncated": True},
        )
        invalid = self.run_purposebus(
            self.project_a, "agent", "list", "--limit", "1001", expected=2
        )
        self.assertEqual(invalid["error"], "invalid_input")
        invalid_candidates = self.run_purposebus(
            self.project_a, "match", "--candidate-limit", "101", expected=2
        )
        self.assertEqual(invalid_candidates["error"], "invalid_input")

        for subscription_id, topic in (
            ("matching", "common/value"),
            ("unmet", "missing/value"),
        ):
            self.run_purposebus(
                self.project_a,
                "subscription",
                "add",
                topic,
                "--agent",
                "agent-a",
                "--purpose",
                f"exercise {subscription_id} bound",
                "--id",
                subscription_id,
            )
        for agent_id in ("agent-b", "agent-c"):
            self.run_purposebus(
                self.project_a,
                "offer",
                "add",
                "common/value",
                "--agent",
                agent_id,
                "--purpose",
                "exercise match bound",
                "--id",
                f"offer-{agent_id}",
            )

        matched = self.run_purposebus(
            self.project_a,
            "match",
            "--limit",
            "1",
            "--candidate-limit",
            "1",
        )["result"]
        self.assertEqual(matched["matches"]["page"]["total"], 2)
        self.assertTrue(matched["matches"]["page"]["truncated"])
        candidates = matched["unmet"]["items"][0]["candidates"]
        self.assertEqual(candidates["page"]["total"], 2)
        self.assertTrue(candidates["page"]["truncated"])

        events = self.run_purposebus(self.project_a, "events", "--limit", "1")["result"]
        self.assertEqual(events["page"]["returned"], 1)
        self.assertGreater(events["page"]["total"], 1)
        self.assertTrue(events["page"]["truncated"])

    def test_payload_and_query_bounds_fail_as_invalid_input(self):
        self.init()
        self.register("producer")
        self.start("producer", "producer1")
        oversized = self.run_purposebus(
            self.project_a,
            "publish",
            "bounded/payload",
            "--instance",
            "producer1",
            "--purpose",
            "exercise payload bound",
            "--text",
            "x" * (64 * 1024 + 1),
            expected=2,
        )
        self.assertEqual(oversized["error"], "invalid_input")
        poll_bound = self.run_purposebus(
            self.project_a, "poll", "--instance", "producer1", "--limit", "0", expected=2
        )
        self.assertEqual(poll_bound["error"], "invalid_input")
        event_bound = self.run_purposebus(
            self.project_a, "events", "--limit", "0", expected=2
        )
        self.assertEqual(event_bound["error"], "invalid_input")

    def test_human_and_json_registry_views(self):
        self.init()
        self.register("agent-a")
        self.register("agent-b")
        self.register("operator", kind="human")
        json_agents = self.run_purposebus(self.project_a, "agent", "list")["result"]["items"]
        self.assertEqual([item["agent_id"] for item in json_agents], ["agent-a", "agent-b", "operator"])
        command = [
            sys.executable,
            "-m",
            "purposebus",
            "--partition",
            str(self.project_a),
            "--state-dir",
            str(self.state),
            "agent",
            "list",
        ]
        result = subprocess.run(
            command,
            cwd=REPO_ROOT,
            env=self.environment,
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            timeout=15,
        )
        self.assertEqual(result.returncode, 0, msg=result.stderr)
        self.assertIn("agent-a", result.stdout)
        self.assertIn("operator", result.stdout)
        self.assertIn("human", result.stdout)
        self.assertIn("Agents: 3 of 3", result.stdout)
        self.assertNotIn("database", result.stdout)
        self.assertNotIn("state_root", result.stdout)
        self.assertNotIn("result:", result.stdout)

    def test_human_read_surfaces_use_command_specific_renderers(self):
        self.init()
        self.register("producer")
        self.register("consumer")
        self.start("producer", "producer1")
        self.start("consumer", "consumer1")
        self.run_purposebus(
            self.project_a,
            "subscription",
            "add",
            "render/value",
            "--instance",
            "consumer1",
            "--purpose",
            "consume rendered value",
            "--id",
            "render-sub",
        )
        self.run_purposebus(
            self.project_a,
            "offer",
            "add",
            "render/value",
            "--instance",
            "producer1",
            "--purpose",
            "provide rendered value",
            "--id",
            "render-offer",
        )
        request = self.run_purposebus(
            self.project_a,
            "request",
            "create",
            "render/request",
            "--instance",
            "consumer1",
            "--purpose",
            "request rendered value",
            "--id",
            "render-request",
        )["result"]
        message = self.run_purposebus(
            self.project_a,
            "publish",
            "render/value",
            "--instance",
            "producer1",
            "--purpose",
            "render one value",
            "--text",
            "visible payload",
        )["result"]

        read_commands = (
            ("status",),
            ("agent", "list"),
            ("agent", "show", "producer"),
            ("instance", "list"),
            ("instance", "show", "producer1"),
            ("subscription", "list"),
            ("subscription", "show", "render-sub"),
            ("offer", "list"),
            ("offer", "show", "render-offer"),
            ("request", "list"),
            ("request", "show", request["subscription_id"]),
            ("message", "list"),
            ("message", "show", message["message_id"], "--include-payload"),
            ("delivery", "list"),
            ("match",),
            ("next", "--instance", "consumer1"),
            ("events", "--limit", "10"),
        )
        for command in read_commands:
            with self.subTest(command=command):
                result = self.run_human(self.project_a, *command)
                self.assertTrue(result.stdout.strip())
                for internal in (
                    "command_digest",
                    "database",
                    "payload_text",
                    "state_root",
                    "result:",
                ):
                    self.assertNotIn(internal, result.stdout)

        shown = self.run_human(
            self.project_a,
            "message",
            "show",
            message["message_id"],
            "--include-payload",
        )
        self.assertIn('Payload: "visible payload"', shown.stdout)

    def test_human_poll_prints_payload_and_exact_ack_step(self):
        self.init()
        self.register("producer")
        self.register("consumer")
        self.start("producer", "producer1")
        self.start("consumer", "consumer1")
        self.run_purposebus(
            self.project_a,
            "subscription",
            "add",
            "human/value",
            "--instance",
            "consumer1",
            "--purpose",
            "handle one value",
            "--id",
            "human-sub",
        )
        self.run_purposebus(
            self.project_a,
            "publish",
            "human/value",
            "--instance",
            "producer1",
            "--purpose",
            "provide one value",
            "--text",
            "ready",
        )
        result = subprocess.run(
            [
                sys.executable,
                "-m",
                "purposebus",
                "--partition",
                str(self.project_a),
                "--state-dir",
                str(self.state),
                "poll",
                "--instance",
                "consumer1",
            ],
            cwd=REPO_ROOT,
            env=self.environment,
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            timeout=15,
        )
        self.assertEqual(result.returncode, 0, msg=result.stderr)
        self.assertIn("Leased Deliveries: 1 of 1", result.stdout)
        self.assertIn('Payload: "ready"', result.stdout)
        self.assertRegex(
            result.stdout,
            r"Next: purposebus ack del_[a-f0-9]+ --instance consumer1",
        )
        for internal in ("command_digest", "database", "state_root", "result:"):
            self.assertNotIn(internal, result.stdout)

    def test_next_reports_matching_request_heartbeat_and_stale_warning(self):
        start = "2026-08-31T00:00:00Z"
        self.init(at=start)
        self.register("requester", at=start)
        self.register("provider", at=start)
        self.start("requester", "requester1", at=start)
        self.start("provider", "provider1", at=start)
        self.run_purposebus(
            self.project_a,
            "offer",
            "add",
            "answer/value",
            "--instance",
            "provider1",
            "--purpose",
            "provide answers",
            "--id",
            "offer1",
            at=start,
        )
        self.run_purposebus(
            self.project_a,
            "request",
            "create",
            "answer/value",
            "--instance",
            "requester1",
            "--purpose",
            "need an answer",
            "--expires-in",
            "2h",
            "--id",
            "request1",
            at=start,
        )
        near_expiry = self.run_purposebus(
            self.project_a,
            "next",
            "--instance",
            "provider1",
            at="2026-08-31T00:59:50Z",
        )["result"]
        self.assertIn(
            "consider_request", [item["kind"] for item in near_expiry["items"]["items"]]
        )
        self.assertIn(
            "heartbeat", [item["kind"] for item in near_expiry["items"]["items"]]
        )
        stale = self.run_purposebus(
            self.project_a,
            "next",
            "--instance",
            "provider1",
            at="2026-08-31T01:00:01Z",
        )["result"]
        self.assertTrue(stale["warnings"]["items"])
        self.assertEqual(stale["instance"]["liveness"], "stale")

    def test_help_routes_expose_catalog_and_integration_contract(self):
        top = subprocess.run(
            [sys.executable, "-m", "purposebus", "--help"],
            cwd=REPO_ROOT,
            env=self.environment,
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            timeout=15,
        )
        self.assertEqual(top.returncode, 0, msg=top.stderr)
        for command in (
            "agent",
            "instance",
            "subscription",
            "offer",
            "request",
            "message",
            "publish",
            "poll",
            "ack",
            "match",
            "status",
            "next",
            "events",
        ):
            self.assertIn(command, top.stdout)
        for topic, phrase in (
            ("usecases", "Publish and receive"),
            ("concepts", "never authorize unrelated work"),
            ("partitions", "no implicit cross-Partition"),
            ("agent", "purposebus.*.v2"),
        ):
            document = self.run_purposebus(self.project_a, "help", topic)
            self.assertIn(phrase, document["result"]["text"])

    def test_next_and_status_are_read_only(self):
        self.init()
        self.register("producer")
        self.register("consumer")
        self.start("producer", "producer1")
        self.start("consumer", "consumer1")
        self.run_purposebus(
            self.project_a,
            "subscription",
            "add",
            "data/one",
            "--instance",
            "consumer1",
            "--purpose",
            "consume data",
            "--id",
            "sub1",
        )
        publication = self.run_purposebus(
            self.project_a,
            "publish",
            "data/one",
            "--instance",
            "producer1",
            "--purpose",
            "provide data",
            "--text",
            "value",
        )
        before = self.logical_state(self.project_a)
        next_result = self.run_purposebus(self.project_a, "next", "--instance", "consumer1")["result"]
        self.run_purposebus(self.project_a, "status")
        self.run_purposebus(self.project_a, "match")
        after = self.logical_state(self.project_a)
        self.assertEqual(before, after)
        self.assertIn(
            "read_delivery", [item["kind"] for item in next_result["items"]["items"]]
        )

    def test_blocking_poll_is_visible_and_clears_after_message(self):
        self.init()
        self.register("producer")
        self.register("consumer")
        self.start("producer", "producer1")
        self.start("consumer", "consumer1")
        self.run_purposebus(
            self.project_a,
            "subscription",
            "add",
            "wait/value",
            "--instance",
            "consumer1",
            "--purpose",
            "wait for value",
            "--id",
            "sub1",
        )
        process = subprocess.Popen(
            self.command(self.project_a, "poll", "--instance", "consumer1", "--wait", "3s"),
            cwd=REPO_ROOT,
            env=self.environment,
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        )
        waiting = self.wait_until_waiting("consumer1")
        self.assertEqual(waiting["liveness"], "alive")
        self.run_purposebus(
            self.project_a,
            "publish",
            "wait/value",
            "--instance",
            "producer1",
            "--purpose",
            "provide waited value",
            "--text",
            "arrived",
        )
        stdout, stderr = process.communicate(timeout=5)
        self.assertEqual(process.returncode, 0, msg=stderr)
        self.assertEqual(
            json.loads(stdout)["result"]["deliveries"]["items"][0]["payload"],
            "arrived",
        )
        status = self.run_purposebus(self.project_a, "status")["result"]
        instance = next(
            item
            for item in status["instances"]["items"]
            if item["instance_id"] == "consumer1"
        )
        self.assertEqual(instance["activity"], "idle")
        self.assertIsNone(instance["wait_valid"])

    def test_killed_wait_is_not_projected_as_waiting(self):
        self.init()
        self.register("consumer")
        self.start("consumer", "consumer1")
        process = subprocess.Popen(
            self.command(self.project_a, "poll", "--instance", "consumer1", "--wait", "5s"),
            cwd=REPO_ROOT,
            env=self.environment,
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        )
        self.wait_until_waiting("consumer1")
        process.kill()
        process.communicate(timeout=5)
        status = self.run_purposebus(self.project_a, "status")["result"]
        instance = next(
            item
            for item in status["instances"]["items"]
            if item["instance_id"] == "consumer1"
        )
        self.assertEqual(instance["declared_activity"], "waiting")
        self.assertEqual(instance["activity"], "idle")
        self.assertFalse(instance["wait_valid"])

    def test_concurrent_publications_are_serialized(self):
        self.init()
        self.register("producer")
        self.register("consumer")
        self.start("producer", "producer1")
        self.start("consumer", "consumer1")
        self.run_purposebus(
            self.project_a,
            "subscription",
            "add",
            "concurrent/+",
            "--instance",
            "consumer1",
            "--purpose",
            "receive concurrent events",
            "--id",
            "sub1",
        )
        processes = []
        for index in range(5):
            processes.append(
                subprocess.Popen(
                    self.command(
                        self.project_a,
                        "publish",
                        f"concurrent/{index}",
                        "--instance",
                        "producer1",
                        "--purpose",
                        "concurrency test",
                        "--text",
                        str(index),
                        "--idempotency-key",
                        f"concurrent-{index}",
                    ),
                    cwd=REPO_ROOT,
                    env=self.environment,
                    text=True,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE,
                )
            )
        for process in processes:
            stdout, stderr = process.communicate(timeout=10)
            self.assertEqual(process.returncode, 0, msg=f"{stdout}\n{stderr}")
        deliveries = self.run_purposebus(self.project_a, "delivery", "list")["result"]["items"]
        self.assertEqual(len(deliveries), 5)


if __name__ == "__main__":
    unittest.main()
