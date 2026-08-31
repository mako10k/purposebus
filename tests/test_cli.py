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

    def logical_state(self, partition_document: dict) -> dict[str, list[tuple]]:
        database = Path(partition_document["database"])
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
            instance = next(item for item in status["instances"] if item["instance_id"] == instance_id)
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
        self.assertEqual(result["matches"][0]["subscription_id"], "sub1")
        self.assertTrue(result["matches"][0]["provider_live"])
        self.assertEqual([item["subscription_id"] for item in result["unmet"]], ["sub2"])

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
        )["result"]
        self.assertEqual([item["message_id"] for item in readback], [first["message_id"]])
        self.assertNotIn("payload_text", readback[0])
        message = self.run_purposebus(
            self.project_a, "message", "show", first["message_id"], "--include-payload"
        )["result"]
        self.assertEqual(message["payload"], {"ok": True})

        alice_delivery = self.run_purposebus(
            self.project_a, "poll", "--instance", "alice1", "--lease", "10s"
        )["result"][0]
        self.run_purposebus(
            self.project_a, "ack", alice_delivery["delivery_id"], "--instance", "alice1"
        )
        deliveries = self.run_purposebus(self.project_a, "delivery", "list")["result"]
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
        )["result"][0]
        second = self.run_purposebus(
            self.project_a,
            "poll",
            "--instance",
            "consumer1",
            "--lease",
            "1s",
            at="2026-01-01T00:00:02Z",
        )["result"][0]
        self.assertEqual(first["delivery_id"], second["delivery_id"])
        self.assertEqual(second["attempt"], 2)

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
        self.assertIn("req1", [item["entity_id"] for item in next_result["items"]])
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
        )["result"][0]
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
        delivery = self.run_purposebus(self.project_a, "poll", "--instance", "consumer1")["result"][0]
        self.assertTrue(delivery["retained"])
        self.assertEqual(delivery["payload"], {"state": "ready"})

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
        delivery = self.run_purposebus(self.project_a, "poll", "--instance", "operator1")["result"][0]
        self.assertEqual(delivery["subscription_id"], "humanbox")
        acknowledged = self.run_purposebus(
            self.project_a, "ack", delivery["delivery_id"], "--instance", "operator1"
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
        delivery = self.run_purposebus(self.project_a, "delivery", "list")["result"][0]
        self.assertEqual(delivery["state"], "expired")
        event_types = [item["event_type"] for item in self.run_purposebus(self.project_a, "events")["result"]]
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
            )["result"][0]
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
        )["result"][0]
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
        )["result"]
        self.assertEqual([item["state"] for item in deliveries], ["dead_letter", "expired"])

    def test_existing_unknown_schema_is_not_modified_by_init(self):
        initialized = self.init()
        database = Path(initialized["partition"]["database"])
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

    def test_partition_isolation_and_private_permissions(self):
        first = self.init(self.project_a)
        second = self.init(self.project_b)
        self.assertNotEqual(first["partition"]["partition_id"], second["partition"]["partition_id"])
        first_dir = Path(first["partition"]["database"]).parent
        self.assertEqual(stat.S_IMODE(first_dir.stat().st_mode), 0o700)
        self.assertEqual(stat.S_IMODE(Path(first["partition"]["database"]).stat().st_mode), 0o600)
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
        self.assertEqual(self.run_purposebus(self.project_b, "message", "list")["result"], [])
        self.assertEqual(self.run_purposebus(self.project_b, "delivery", "list")["result"], [])
        self.run_purposebus(
            self.project_b, "poll", "--instance", "consumer1", expected=4
        )
        for partition_dir in (
            Path(first["partition"]["database"]).parent,
            Path(second["partition"]["database"]).parent,
        ):
            for state_file in partition_dir.iterdir():
                if state_file.is_file():
                    self.assertEqual(stat.S_IMODE(state_file.stat().st_mode), 0o600)

    def test_human_and_json_registry_views(self):
        self.init()
        self.register("agent-a")
        self.register("agent-b")
        self.register("operator", kind="human")
        json_agents = self.run_purposebus(self.project_a, "agent", "list")["result"]
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
        self.assertIn("consider_request", [item["kind"] for item in near_expiry["items"]])
        self.assertIn("heartbeat", [item["kind"] for item in near_expiry["items"]])
        stale = self.run_purposebus(
            self.project_a,
            "next",
            "--instance",
            "provider1",
            at="2026-08-31T01:00:01Z",
        )["result"]
        self.assertTrue(stale["warnings"])
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
            ("agent", "purposebus.*.v1"),
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
        before = self.logical_state(publication["partition"])
        next_result = self.run_purposebus(self.project_a, "next", "--instance", "consumer1")["result"]
        self.run_purposebus(self.project_a, "status")
        self.run_purposebus(self.project_a, "match")
        after = self.logical_state(publication["partition"])
        self.assertEqual(before, after)
        self.assertIn("read_delivery", [item["kind"] for item in next_result["items"]])

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
        self.assertEqual(json.loads(stdout)["result"][0]["payload"], "arrived")
        status = self.run_purposebus(self.project_a, "status")["result"]
        instance = next(item for item in status["instances"] if item["instance_id"] == "consumer1")
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
        instance = next(item for item in status["instances"] if item["instance_id"] == "consumer1")
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
        deliveries = self.run_purposebus(self.project_a, "delivery", "list")["result"]
        self.assertEqual(len(deliveries), 5)


if __name__ == "__main__":
    unittest.main()
