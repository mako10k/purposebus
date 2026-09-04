from __future__ import annotations

import json
import os
import sqlite3
from contextlib import contextmanager
from datetime import datetime
from pathlib import Path

from .errors import Conflict, InvalidInput, NotFound, OwnershipMismatch
from .partition import Partition
from .util import (
    add_seconds,
    canonical_json,
    command_digest,
    ensure_private_file,
    filters_overlap,
    iso,
    new_id,
    process_matches,
    process_observation,
    schema_compatible,
    topic_matches,
)


SCHEMA_VERSION = "1"
MAX_DELIVERY_ATTEMPTS = 5
MAX_EVENT_ROWS = 10_000

SCHEMA = """
CREATE TABLE IF NOT EXISTS metadata (
    key TEXT PRIMARY KEY,
    value TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS agents (
    agent_id TEXT PRIMARY KEY,
    kind TEXT NOT NULL CHECK (kind IN ('human', 'ai')),
    description TEXT NOT NULL,
    capabilities_json TEXT NOT NULL,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS instances (
    instance_id TEXT PRIMARY KEY,
    agent_id TEXT NOT NULL REFERENCES agents(agent_id),
    objective TEXT NOT NULL,
    activity TEXT NOT NULL CHECK (activity IN ('idle', 'busy', 'waiting', 'draining', 'stopped')),
    lifecycle_state TEXT NOT NULL CHECK (lifecycle_state IN ('active', 'stopped')),
    heartbeat_at TEXT NOT NULL,
    lease_expires_at TEXT NOT NULL,
    lease_seconds REAL NOT NULL,
    host TEXT,
    boot_id TEXT,
    pid INTEGER,
    process_start TEXT,
    wait_pid INTEGER,
    wait_boot_id TEXT,
    wait_process_start TEXT,
    waiting_since TEXT,
    waiting_until TEXT,
    waiting_selector TEXT,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS subscriptions (
    subscription_id TEXT PRIMARY KEY,
    owner_type TEXT NOT NULL CHECK (owner_type IN ('agent', 'instance')),
    owner_id TEXT NOT NULL,
    topic_filter TEXT NOT NULL,
    purpose TEXT NOT NULL,
    schema_id TEXT,
    durable INTEGER NOT NULL CHECK (durable IN (0, 1)),
    state TEXT NOT NULL CHECK (state IN ('active', 'paused', 'cancelled')),
    expires_at TEXT,
    kind TEXT NOT NULL CHECK (kind IN ('subscription', 'request')),
    request_state TEXT CHECK (request_state IN ('open', 'response_available', 'fulfilled', 'cancelled')),
    correlation_id TEXT,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS offers (
    offer_id TEXT PRIMARY KEY,
    owner_type TEXT NOT NULL CHECK (owner_type IN ('agent', 'instance')),
    owner_id TEXT NOT NULL,
    topic_filter TEXT NOT NULL,
    purpose TEXT NOT NULL,
    schema_id TEXT,
    state TEXT NOT NULL CHECK (state IN ('active', 'paused', 'cancelled')),
    expires_at TEXT,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS messages (
    message_id TEXT PRIMARY KEY,
    producer_instance_id TEXT NOT NULL REFERENCES instances(instance_id),
    topic TEXT NOT NULL,
    purpose TEXT NOT NULL,
    payload_kind TEXT NOT NULL CHECK (payload_kind IN ('text', 'json', 'reference')),
    payload_text TEXT NOT NULL,
    artifact_digest TEXT,
    schema_id TEXT,
    correlation_id TEXT,
    causation_id TEXT,
    expires_at TEXT,
    idempotency_key TEXT,
    command_digest TEXT NOT NULL,
    retained INTEGER NOT NULL CHECK (retained IN (0, 1)),
    advertised INTEGER NOT NULL CHECK (advertised IN (0, 1)),
    created_at TEXT NOT NULL,
    UNIQUE (producer_instance_id, idempotency_key)
);

CREATE TABLE IF NOT EXISTS retained (
    topic TEXT NOT NULL,
    schema_key TEXT NOT NULL,
    message_id TEXT NOT NULL REFERENCES messages(message_id),
    PRIMARY KEY (topic, schema_key)
);

CREATE TABLE IF NOT EXISTS deliveries (
    delivery_id TEXT PRIMARY KEY,
    message_id TEXT NOT NULL REFERENCES messages(message_id),
    subscription_id TEXT NOT NULL REFERENCES subscriptions(subscription_id),
    state TEXT NOT NULL CHECK (state IN ('queued', 'leased', 'acked', 'expired', 'dead_letter')),
    attempt INTEGER NOT NULL DEFAULT 0,
    leased_by_instance_id TEXT REFERENCES instances(instance_id),
    lease_until TEXT,
    acked_at TEXT,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    UNIQUE (message_id, subscription_id)
);

CREATE TABLE IF NOT EXISTS events (
    sequence INTEGER PRIMARY KEY AUTOINCREMENT,
    event_id TEXT NOT NULL UNIQUE,
    entity_type TEXT NOT NULL,
    entity_id TEXT NOT NULL,
    event_type TEXT NOT NULL,
    actor_instance_id TEXT,
    at TEXT NOT NULL,
    details_json TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS deliveries_state_idx ON deliveries(state, lease_until);
CREATE INDEX IF NOT EXISTS subscriptions_state_idx ON subscriptions(state, expires_at);
CREATE INDEX IF NOT EXISTS offers_state_idx ON offers(state, expires_at);
CREATE INDEX IF NOT EXISTS messages_topic_idx ON messages(topic, created_at);
CREATE INDEX IF NOT EXISTS events_entity_idx ON events(entity_type, entity_id, sequence);
"""


def _dict(row: sqlite3.Row | None) -> dict | None:
    return None if row is None else dict(row)


def _not_expired(expires_at: str | None, now_text: str) -> bool:
    return expires_at is None or expires_at > now_text


def _project_subscription(row: dict, now_text: str) -> dict:
    result = dict(row)
    result["durable"] = bool(result["durable"])
    if result.get("expires_at") and result["expires_at"] <= now_text:
        result["effective_state"] = "expired"
        if result.get("kind") == "request" and result.get("request_state") not in {"fulfilled", "cancelled"}:
            result["effective_request_state"] = "expired"
    else:
        result["effective_state"] = result["state"]
        if result.get("kind") == "request":
            result["effective_request_state"] = result["request_state"]
    return result


def _project_offer(row: dict, now_text: str) -> dict:
    result = dict(row)
    result["effective_state"] = (
        "expired" if result.get("expires_at") and result["expires_at"] <= now_text else result["state"]
    )
    return result


def project_instance(row: dict, now: datetime) -> dict:
    result = dict(row)
    now_text = iso(now)
    process_state, process_reason = process_matches(
        row.get("host"), row.get("boot_id"), row.get("pid"), row.get("process_start")
    )
    if row["lifecycle_state"] == "stopped":
        liveness = "dead"
        liveness_reason = "explicit_stop"
    elif process_state is False:
        liveness = "dead"
        liveness_reason = process_reason
    elif process_state is True:
        liveness = "alive"
        liveness_reason = process_reason
    elif row["lease_expires_at"] > now_text:
        liveness = "alive"
        liveness_reason = "heartbeat_lease_current"
    elif row.get("heartbeat_at"):
        liveness = "stale"
        liveness_reason = "heartbeat_lease_expired"
    else:
        liveness = "unknown"
        liveness_reason = process_reason

    activity = row["activity"]
    wait_valid = None
    wait_reason = None
    if activity == "waiting":
        wait_state, wait_reason = process_matches(
            row.get("host"), row.get("wait_boot_id"), row.get("wait_pid"), row.get("wait_process_start")
        )
        wait_valid = wait_state is True and (row.get("waiting_until") is None or row["waiting_until"] > now_text)
        if not wait_valid:
            activity = "idle" if row["lifecycle_state"] == "active" else "stopped"

    result.update(
        {
            "declared_activity": row["activity"],
            "activity": activity,
            "liveness": liveness,
            "liveness_reason": liveness_reason,
            "wait_valid": wait_valid,
            "wait_reason": wait_reason,
        }
    )
    return result


class Store:
    def __init__(self, partition: Partition, *, readonly: bool = False):
        self.partition = partition
        self.readonly = readonly
        if not partition.database.exists():
            raise NotFound("PurposeBus partition is not initialized", hint="run purposebus init")
        if readonly:
            uri = f"file:{partition.database}?mode=ro"
            self.connection = sqlite3.connect(uri, uri=True, timeout=5)
        else:
            old_umask = os.umask(0o077)
            try:
                self.connection = sqlite3.connect(partition.database, timeout=5)
                self.connection.execute("PRAGMA journal_mode=WAL")
            finally:
                os.umask(old_umask)
            ensure_private_file(partition.database)
        self.connection.row_factory = sqlite3.Row
        self.connection.execute("PRAGMA foreign_keys=ON")
        self.connection.execute("PRAGMA busy_timeout=5000")
        if readonly:
            self.connection.execute("PRAGMA query_only=ON")
        self._verify_metadata()

    @classmethod
    def initialize(cls, partition: Partition, now: datetime) -> tuple["Store", bool]:
        partition.state_root.mkdir(mode=0o700, parents=True, exist_ok=True)
        os.chmod(partition.state_root, 0o700)
        (partition.state_root / "partitions").mkdir(mode=0o700, exist_ok=True)
        os.chmod(partition.state_root / "partitions", 0o700)
        partition.directory.mkdir(mode=0o700, exist_ok=True)
        os.chmod(partition.directory, 0o700)
        if partition.database.exists():
            return cls(partition, readonly=True), False

        old_umask = os.umask(0o077)
        connection = None
        try:
            connection = sqlite3.connect(partition.database, timeout=5)
            connection.execute("PRAGMA journal_mode=WAL")
            connection.executescript(SCHEMA)
            values = {
                "schema_version": SCHEMA_VERSION,
                "partition_id": partition.partition_id,
                "partition_path": str(partition.path),
                "created_at": iso(now),
                "events_pruned": "0",
            }
            for key, value in values.items():
                connection.execute("INSERT OR IGNORE INTO metadata(key, value) VALUES (?, ?)", (key, value))
            connection.commit()
        finally:
            if connection is not None:
                connection.close()
            os.umask(old_umask)
        ensure_private_file(partition.database)
        return cls(partition), True

    def close(self) -> None:
        self.connection.close()

    def __enter__(self) -> "Store":
        return self

    def __exit__(self, exc_type, exc, traceback) -> None:
        self.close()

    def _verify_metadata(self) -> None:
        try:
            rows = self.connection.execute("SELECT key, value FROM metadata").fetchall()
        except sqlite3.DatabaseError as exc:
            raise Conflict("PurposeBus state is corrupt or uses an unsupported schema") from exc
        metadata = {row["key"]: row["value"] for row in rows}
        if metadata.get("schema_version") != SCHEMA_VERSION:
            raise Conflict(
                f"unsupported PurposeBus state schema: {metadata.get('schema_version')!r}",
                hint="use a compatible PurposeBus version; state is not reset automatically",
            )
        if metadata.get("partition_id") != self.partition.partition_id:
            raise Conflict("state partition identity does not match the resolved Partition")

    @contextmanager
    def transaction(self):
        if self.readonly:
            raise RuntimeError("read-only Store cannot start a mutation transaction")
        self.connection.execute("BEGIN IMMEDIATE")
        try:
            yield self.connection
        except Exception:
            self.connection.rollback()
            raise
        else:
            self.connection.commit()

    def _event(
        self,
        connection: sqlite3.Connection,
        *,
        entity_type: str,
        entity_id: str,
        event_type: str,
        at: str,
        actor_instance_id: str | None = None,
        details: dict | None = None,
    ) -> None:
        connection.execute(
            """
            INSERT INTO events(event_id, entity_type, entity_id, event_type, actor_instance_id, at, details_json)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (
                new_id("evt"),
                entity_type,
                entity_id,
                event_type,
                actor_instance_id,
                at,
                canonical_json(details or {}),
            ),
        )
        event_count = connection.execute("SELECT COUNT(*) FROM events").fetchone()[0]
        excess = event_count - MAX_EVENT_ROWS
        if excess > 0:
            connection.execute(
                """
                DELETE FROM events
                WHERE sequence IN (SELECT sequence FROM events ORDER BY sequence LIMIT ?)
                """,
                (excess,),
            )
            connection.execute(
                """
                INSERT INTO metadata(key, value) VALUES ('events_pruned', ?)
                ON CONFLICT(key) DO UPDATE
                SET value=CAST(CAST(metadata.value AS INTEGER) + ? AS TEXT)
                """,
                (str(excess), excess),
            )

    def metadata(self) -> dict:
        rows = self.connection.execute("SELECT key, value FROM metadata ORDER BY key").fetchall()
        return {row["key"]: row["value"] for row in rows}

    def _expire_subscription_deliveries(
        self,
        connection: sqlite3.Connection,
        subscription_ids: list[str],
        *,
        at: str,
        reason: str,
        actor_instance_id: str | None = None,
    ) -> None:
        for subscription_id in subscription_ids:
            delivery_ids = [
                row["delivery_id"]
                for row in connection.execute(
                    """
                    SELECT delivery_id FROM deliveries
                    WHERE subscription_id=? AND state IN ('queued', 'leased')
                    ORDER BY delivery_id
                    """,
                    (subscription_id,),
                ).fetchall()
            ]
            connection.execute(
                """
                UPDATE deliveries
                SET state='expired', leased_by_instance_id=NULL, lease_until=NULL, updated_at=?
                WHERE subscription_id=? AND state IN ('queued', 'leased')
                """,
                (at, subscription_id),
            )
            for delivery_id in delivery_ids:
                self._event(
                    connection,
                    entity_type="delivery",
                    entity_id=delivery_id,
                    event_type="expired",
                    at=at,
                    actor_instance_id=actor_instance_id,
                    details={"reason": reason, "subscription_id": subscription_id},
                )

    def register_agent(self, agent_id: str, kind: str, description: str, capabilities: list[str], now: datetime) -> dict:
        at = iso(now)
        try:
            with self.transaction() as connection:
                connection.execute(
                    """
                    INSERT INTO agents(agent_id, kind, description, capabilities_json, created_at, updated_at)
                    VALUES (?, ?, ?, ?, ?, ?)
                    """,
                    (agent_id, kind, description, canonical_json(capabilities), at, at),
                )
                self._event(
                    connection,
                    entity_type="agent",
                    entity_id=agent_id,
                    event_type="registered",
                    at=at,
                    details={
                        "kind": kind,
                        "capabilities": capabilities,
                        "actor_type": "agent",
                        "actor_id": agent_id,
                    },
                )
        except sqlite3.IntegrityError as exc:
            raise Conflict(f"agent already exists in this Partition: {agent_id}") from exc
        return self.get_agent(agent_id)

    def get_agent(self, agent_id: str) -> dict:
        row = self.connection.execute("SELECT * FROM agents WHERE agent_id=?", (agent_id,)).fetchone()
        if row is None:
            raise NotFound(f"agent not found: {agent_id}")
        result = dict(row)
        result["capabilities"] = json.loads(result.pop("capabilities_json"))
        return result

    def list_agents(self) -> list[dict]:
        rows = self.connection.execute("SELECT * FROM agents ORDER BY agent_id").fetchall()
        result = []
        for row in rows:
            item = dict(row)
            item["capabilities"] = json.loads(item.pop("capabilities_json"))
            result.append(item)
        return result

    def start_instance(
        self,
        agent_id: str,
        instance_id: str,
        objective: str,
        activity: str,
        lease_seconds: float,
        pid: int | None,
        now: datetime,
    ) -> dict:
        self.get_agent(agent_id)
        at = iso(now)
        lease_until = iso(add_seconds(now, lease_seconds))
        observation = process_observation(pid)
        try:
            with self.transaction() as connection:
                connection.execute(
                    """
                    INSERT INTO instances(
                        instance_id, agent_id, objective, activity, lifecycle_state,
                        heartbeat_at, lease_expires_at, lease_seconds, host, boot_id,
                        pid, process_start, created_at, updated_at
                    ) VALUES (?, ?, ?, ?, 'active', ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        instance_id,
                        agent_id,
                        objective,
                        activity,
                        at,
                        lease_until,
                        lease_seconds,
                        observation["host"],
                        observation["boot_id"],
                        observation["pid"],
                        observation["process_start"],
                        at,
                        at,
                    ),
                )
                self._event(
                    connection,
                    entity_type="instance",
                    entity_id=instance_id,
                    event_type="started",
                    at=at,
                    actor_instance_id=instance_id,
                    details={"agent_id": agent_id, "objective": objective, "pid": pid},
                )
        except sqlite3.IntegrityError as exc:
            raise Conflict(f"instance already exists: {instance_id}") from exc
        return self.get_instance(instance_id, now)

    def _instance_row(self, instance_id: str) -> dict:
        row = self.connection.execute("SELECT * FROM instances WHERE instance_id=?", (instance_id,)).fetchone()
        if row is None:
            raise NotFound(f"instance not found: {instance_id}")
        return dict(row)

    def get_instance(self, instance_id: str, now: datetime) -> dict:
        return project_instance(self._instance_row(instance_id), now)

    def list_instances(self, now: datetime) -> list[dict]:
        rows = self.connection.execute("SELECT * FROM instances ORDER BY instance_id").fetchall()
        return [project_instance(dict(row), now) for row in rows]

    def heartbeat_instance(
        self,
        instance_id: str,
        now: datetime,
        *,
        activity: str | None = None,
        objective: str | None = None,
    ) -> dict:
        row = self._instance_row(instance_id)
        if row["lifecycle_state"] == "stopped":
            raise Conflict(f"instance is stopped: {instance_id}")
        at = iso(now)
        lease_until = iso(add_seconds(now, float(row["lease_seconds"])))
        next_activity = activity or row["activity"]
        next_objective = objective if objective is not None else row["objective"]
        with self.transaction() as connection:
            connection.execute(
                """
                UPDATE instances
                SET heartbeat_at=?, lease_expires_at=?, activity=?, objective=?, updated_at=?
                WHERE instance_id=?
                """,
                (at, lease_until, next_activity, next_objective, at, instance_id),
            )
            self._event(
                connection,
                entity_type="instance",
                entity_id=instance_id,
                event_type="heartbeat",
                at=at,
                actor_instance_id=instance_id,
                details={"activity": next_activity},
            )
        return self.get_instance(instance_id, now)

    def stop_instance(self, instance_id: str, now: datetime) -> dict:
        self._instance_row(instance_id)
        at = iso(now)
        with self.transaction() as connection:
            ephemeral_ids = [
                row["subscription_id"]
                for row in connection.execute(
                    """
                    SELECT subscription_id FROM subscriptions
                    WHERE owner_type='instance' AND owner_id=? AND durable=0
                      AND state IN ('active', 'paused')
                    ORDER BY subscription_id
                    """,
                    (instance_id,),
                ).fetchall()
            ]
            connection.execute(
                """
                UPDATE instances
                SET activity='stopped', lifecycle_state='stopped', wait_pid=NULL,
                    wait_boot_id=NULL, wait_process_start=NULL, waiting_since=NULL,
                    waiting_until=NULL, waiting_selector=NULL, updated_at=?
                WHERE instance_id=?
                """,
                (at, instance_id),
            )
            connection.execute(
                """
                UPDATE subscriptions
                SET state='cancelled', updated_at=?
                WHERE owner_type='instance' AND owner_id=? AND durable=0
                  AND state IN ('active', 'paused')
                """,
                (at, instance_id),
            )
            self._expire_subscription_deliveries(
                connection,
                ephemeral_ids,
                at=at,
                reason="owner_instance_stopped",
                actor_instance_id=instance_id,
            )
            for subscription_id in ephemeral_ids:
                self._event(
                    connection,
                    entity_type="subscription",
                    entity_id=subscription_id,
                    event_type="cancelled",
                    at=at,
                    actor_instance_id=instance_id,
                    details={"reason": "owner_instance_stopped"},
                )
            self._event(
                connection,
                entity_type="instance",
                entity_id=instance_id,
                event_type="stopped",
                at=at,
                actor_instance_id=instance_id,
            )
        return self.get_instance(instance_id, now)

    def set_wait(
        self,
        instance_id: str,
        now: datetime,
        until: datetime,
        selector: str | None,
        wait_pid: int,
    ) -> str:
        row = self._instance_row(instance_id)
        if row["lifecycle_state"] == "stopped":
            raise Conflict(f"instance is stopped: {instance_id}")
        observation = process_observation(wait_pid)
        at = iso(now)
        lease_until = iso(add_seconds(now, float(row["lease_seconds"])))
        with self.transaction() as connection:
            connection.execute(
                """
                UPDATE instances
                SET activity='waiting', heartbeat_at=?, lease_expires_at=?, wait_pid=?,
                    wait_boot_id=?, wait_process_start=?, waiting_since=?, waiting_until=?,
                    waiting_selector=?, updated_at=?
                WHERE instance_id=?
                """,
                (
                    at,
                    lease_until,
                    observation["pid"],
                    observation["boot_id"],
                    observation["process_start"],
                    at,
                    iso(until),
                    selector,
                    at,
                    instance_id,
                ),
            )
            self._event(
                connection,
                entity_type="instance",
                entity_id=instance_id,
                event_type="wait_started",
                at=at,
                actor_instance_id=instance_id,
                details={"until": iso(until), "selector": selector},
            )
        return row["activity"]

    def refresh_wait(self, instance_id: str, now: datetime) -> None:
        row = self._instance_row(instance_id)
        if row["activity"] != "waiting" or row["lifecycle_state"] != "active":
            return
        at = iso(now)
        lease_until = iso(add_seconds(now, float(row["lease_seconds"])))
        with self.transaction() as connection:
            connection.execute(
                "UPDATE instances SET heartbeat_at=?, lease_expires_at=?, updated_at=? WHERE instance_id=?",
                (at, lease_until, at, instance_id),
            )

    def clear_wait(self, instance_id: str, now: datetime, restore_activity: str) -> None:
        row = self._instance_row(instance_id)
        if row["lifecycle_state"] != "active":
            return
        at = iso(now)
        with self.transaction() as connection:
            connection.execute(
                """
                UPDATE instances
                SET activity=?, wait_pid=NULL, wait_boot_id=NULL, wait_process_start=NULL,
                    waiting_since=NULL, waiting_until=NULL, waiting_selector=NULL, updated_at=?
                WHERE instance_id=?
                """,
                (restore_activity if restore_activity != "waiting" else "idle", at, instance_id),
            )
            self._event(
                connection,
                entity_type="instance",
                entity_id=instance_id,
                event_type="wait_ended",
                at=at,
                actor_instance_id=instance_id,
            )

    def _validate_owner(self, owner_type: str, owner_id: str) -> str:
        if owner_type == "agent":
            self.get_agent(owner_id)
            return owner_id
        if owner_type == "instance":
            instance = self._instance_row(owner_id)
            if instance["lifecycle_state"] != "active":
                raise Conflict(f"acting instance is stopped: {owner_id}")
            return instance["agent_id"]
        raise InvalidInput(f"invalid owner type: {owner_type}")

    def _authorize_owner(
        self,
        owner_type: str,
        owner_id: str,
        actor_type: str,
        actor_id: str,
    ) -> str | None:
        owner_agent_id = self._owner_agent(owner_type, owner_id)
        if actor_type == "agent":
            self.get_agent(actor_id)
            actor_agent_id = actor_id
            actor_instance_id = None
        elif actor_type == "instance":
            actor = self._instance_row(actor_id)
            if actor["lifecycle_state"] != "active":
                raise Conflict(f"acting instance is stopped: {actor_id}")
            actor_agent_id = actor["agent_id"]
            actor_instance_id = actor_id
        else:
            raise InvalidInput(f"invalid actor type: {actor_type}")
        if actor_agent_id != owner_agent_id:
            raise Conflict("acting identity does not own this resource")
        return actor_instance_id

    def add_subscription(
        self,
        *,
        subscription_id: str,
        owner_type: str,
        owner_id: str,
        topic_filter: str,
        purpose: str,
        schema_id: str | None,
        durable: bool,
        expires_at: str | None,
        kind: str,
        correlation_id: str | None,
        now: datetime,
    ) -> dict:
        self._validate_owner(owner_type, owner_id)
        if not durable and owner_type != "instance":
            raise InvalidInput("an ephemeral Subscription must be owned by an Instance")
        at = iso(now)
        request_state = "open" if kind == "request" else None
        delivery_count = 0
        try:
            with self.transaction() as connection:
                connection.execute(
                    """
                    INSERT INTO subscriptions(
                        subscription_id, owner_type, owner_id, topic_filter, purpose,
                        schema_id, durable, state, expires_at, kind, request_state,
                        correlation_id, created_at, updated_at
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, 'active', ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        subscription_id,
                        owner_type,
                        owner_id,
                        topic_filter,
                        purpose,
                        schema_id,
                        int(durable),
                        expires_at,
                        kind,
                        request_state,
                        correlation_id,
                        at,
                        at,
                    ),
                )
                retained_rows = connection.execute(
                    """
                    SELECT m.* FROM retained r JOIN messages m ON m.message_id=r.message_id
                    WHERE m.expires_at IS NULL OR m.expires_at>?
                    ORDER BY m.topic, m.created_at
                    """,
                    (at,),
                ).fetchall()
                for retained in retained_rows:
                    if not topic_matches(topic_filter, retained["topic"]):
                        continue
                    if not schema_compatible(schema_id, retained["schema_id"]):
                        continue
                    if kind == "request" and retained["correlation_id"] != correlation_id:
                        continue
                    connection.execute(
                        """
                        INSERT OR IGNORE INTO deliveries(
                            delivery_id, message_id, subscription_id, state, created_at, updated_at
                        ) VALUES (?, ?, ?, 'queued', ?, ?)
                        """,
                        (new_id("del"), retained["message_id"], subscription_id, at, at),
                    )
                    if connection.execute("SELECT changes()").fetchone()[0]:
                        delivery_count += 1
                if kind == "request" and delivery_count:
                    connection.execute(
                        "UPDATE subscriptions SET request_state='response_available', updated_at=? WHERE subscription_id=?",
                        (at, subscription_id),
                    )
                self._event(
                    connection,
                    entity_type=kind,
                    entity_id=subscription_id,
                    event_type="created",
                    at=at,
                    actor_instance_id=owner_id if owner_type == "instance" else None,
                    details={
                        "owner_type": owner_type,
                        "owner_id": owner_id,
                        "actor_type": owner_type,
                        "actor_id": owner_id,
                        "retained_deliveries": delivery_count,
                    },
                )
        except sqlite3.IntegrityError as exc:
            raise Conflict(f"{kind} already exists: {subscription_id}") from exc
        return self.get_subscription(subscription_id, now)

    def get_subscription(self, subscription_id: str, now: datetime) -> dict:
        row = self.connection.execute(
            "SELECT * FROM subscriptions WHERE subscription_id=?", (subscription_id,)
        ).fetchone()
        if row is None:
            raise NotFound(f"subscription or request not found: {subscription_id}")
        return _project_subscription(dict(row), iso(now))

    def list_subscriptions(self, now: datetime, *, kind: str | None = None) -> list[dict]:
        if kind:
            rows = self.connection.execute(
                "SELECT * FROM subscriptions WHERE kind=? ORDER BY subscription_id", (kind,)
            ).fetchall()
        else:
            rows = self.connection.execute("SELECT * FROM subscriptions ORDER BY subscription_id").fetchall()
        return [_project_subscription(dict(row), iso(now)) for row in rows]

    def change_subscription(
        self,
        subscription_id: str,
        action: str,
        actor_type: str,
        actor_id: str,
        now: datetime,
    ) -> dict:
        row = self.get_subscription(subscription_id, now)
        actor_instance_id = self._authorize_owner(
            row["owner_type"], row["owner_id"], actor_type, actor_id
        )
        if action == "pause":
            if row["effective_state"] != "active":
                raise Conflict(f"only an active subscription can be paused: {subscription_id}")
            state = "paused"
        elif action == "resume":
            if row["effective_state"] != "paused":
                raise Conflict(f"only a paused, unexpired subscription can be resumed: {subscription_id}")
            state = "active"
        elif action == "cancel":
            if row["state"] == "cancelled":
                return row
            state = "cancelled"
        else:
            raise InvalidInput(f"invalid subscription action: {action}")
        at = iso(now)
        with self.transaction() as connection:
            if row["kind"] == "request" and action == "cancel":
                connection.execute(
                    "UPDATE subscriptions SET state=?, request_state='cancelled', updated_at=? WHERE subscription_id=?",
                    (state, at, subscription_id),
                )
            else:
                connection.execute(
                    "UPDATE subscriptions SET state=?, updated_at=? WHERE subscription_id=?",
                    (state, at, subscription_id),
                )
            if action == "cancel":
                self._expire_subscription_deliveries(
                    connection,
                    [subscription_id],
                    at=at,
                    reason="subscription_cancelled",
                    actor_instance_id=actor_instance_id,
                )
            self._event(
                connection,
                entity_type=row["kind"],
                entity_id=subscription_id,
                event_type={"pause": "paused", "resume": "resumed", "cancel": "cancelled"}[action],
                at=at,
                actor_instance_id=actor_instance_id,
                details={"actor_type": actor_type, "actor_id": actor_id},
            )
        return self.get_subscription(subscription_id, now)

    def add_offer(
        self,
        *,
        offer_id: str,
        owner_type: str,
        owner_id: str,
        topic_filter: str,
        purpose: str,
        schema_id: str | None,
        expires_at: str | None,
        now: datetime,
    ) -> dict:
        self._validate_owner(owner_type, owner_id)
        at = iso(now)
        try:
            with self.transaction() as connection:
                connection.execute(
                    """
                    INSERT INTO offers(
                        offer_id, owner_type, owner_id, topic_filter, purpose,
                        schema_id, state, expires_at, created_at, updated_at
                    ) VALUES (?, ?, ?, ?, ?, ?, 'active', ?, ?, ?)
                    """,
                    (offer_id, owner_type, owner_id, topic_filter, purpose, schema_id, expires_at, at, at),
                )
                self._event(
                    connection,
                    entity_type="offer",
                    entity_id=offer_id,
                    event_type="created",
                    at=at,
                    actor_instance_id=owner_id if owner_type == "instance" else None,
                    details={
                        "owner_type": owner_type,
                        "owner_id": owner_id,
                        "actor_type": owner_type,
                        "actor_id": owner_id,
                    },
                )
        except sqlite3.IntegrityError as exc:
            raise Conflict(f"offer already exists: {offer_id}") from exc
        return self.get_offer(offer_id, now)

    def get_offer(self, offer_id: str, now: datetime) -> dict:
        row = self.connection.execute("SELECT * FROM offers WHERE offer_id=?", (offer_id,)).fetchone()
        if row is None:
            raise NotFound(f"offer not found: {offer_id}")
        return _project_offer(dict(row), iso(now))

    def list_offers(self, now: datetime) -> list[dict]:
        rows = self.connection.execute("SELECT * FROM offers ORDER BY offer_id").fetchall()
        return [_project_offer(dict(row), iso(now)) for row in rows]

    def change_offer(
        self,
        offer_id: str,
        action: str,
        actor_type: str,
        actor_id: str,
        now: datetime,
    ) -> dict:
        row = self.get_offer(offer_id, now)
        actor_instance_id = self._authorize_owner(
            row["owner_type"], row["owner_id"], actor_type, actor_id
        )
        if action == "pause":
            if row["effective_state"] != "active":
                raise Conflict(f"only an active offer can be paused: {offer_id}")
            state = "paused"
        elif action == "resume":
            if row["effective_state"] != "paused":
                raise Conflict(f"only a paused, unexpired offer can be resumed: {offer_id}")
            state = "active"
        elif action == "cancel":
            if row["state"] == "cancelled":
                return row
            state = "cancelled"
        else:
            raise InvalidInput(f"invalid offer action: {action}")
        at = iso(now)
        with self.transaction() as connection:
            connection.execute("UPDATE offers SET state=?, updated_at=? WHERE offer_id=?", (state, at, offer_id))
            self._event(
                connection,
                entity_type="offer",
                entity_id=offer_id,
                event_type={"pause": "paused", "resume": "resumed", "cancel": "cancelled"}[action],
                at=at,
                actor_instance_id=actor_instance_id,
                details={"actor_type": actor_type, "actor_id": actor_id},
            )
        return self.get_offer(offer_id, now)

    def _owner_agent(self, owner_type: str, owner_id: str) -> str:
        if owner_type == "agent":
            return owner_id
        return self._instance_row(owner_id)["agent_id"]

    def matches(self, now: datetime) -> dict:
        subscriptions = [
            item
            for item in self.list_subscriptions(now)
            if item["effective_state"] == "active"
            and (item["kind"] != "request" or item["effective_request_state"] in {"open", "response_available"})
        ]
        offers = [item for item in self.list_offers(now) if item["effective_state"] == "active"]
        instances = self.list_instances(now)
        by_agent: dict[str, list[dict]] = {}
        by_instance = {item["instance_id"]: item for item in instances}
        for instance in instances:
            by_agent.setdefault(instance["agent_id"], []).append(instance)
        pairs = []
        matched_subscription_ids = set()
        for subscription in subscriptions:
            for offer in offers:
                topic_overlap = filters_overlap(
                    subscription["topic_filter"], offer["topic_filter"]
                )
                schemas_match = schema_compatible(
                    subscription["schema_id"], offer["schema_id"]
                )
                if not topic_overlap:
                    continue
                if not schemas_match:
                    continue
                if offer["owner_type"] == "instance":
                    candidates = [by_instance.get(offer["owner_id"])]
                else:
                    candidates = by_agent.get(offer["owner_id"], [])
                live_instances = sorted(
                    item["instance_id"] for item in candidates if item and item["liveness"] == "alive"
                )
                candidate_instances = [
                    {
                        "instance_id": item["instance_id"],
                        "liveness": item["liveness"],
                        "liveness_reason": item["liveness_reason"],
                        "activity": item["activity"],
                    }
                    for item in sorted(
                        (item for item in candidates if item), key=lambda item: item["instance_id"]
                    )
                ]
                pairs.append(
                    {
                        "subscription_id": subscription["subscription_id"],
                        "subscription_kind": subscription["kind"],
                        "subscription_owner_type": subscription["owner_type"],
                        "subscription_owner_id": subscription["owner_id"],
                        "subscriber_agent_id": self._owner_agent(
                            subscription["owner_type"], subscription["owner_id"]
                        ),
                        "subscription_purpose": subscription["purpose"],
                        "subscription_topic_filter": subscription["topic_filter"],
                        "subscription_schema_id": subscription["schema_id"],
                        "subscription_expires_at": subscription["expires_at"],
                        "correlation_id": subscription["correlation_id"],
                        "offer_id": offer["offer_id"],
                        "offer_owner_type": offer["owner_type"],
                        "offer_owner_id": offer["owner_id"],
                        "provider_agent_id": self._owner_agent(offer["owner_type"], offer["owner_id"]),
                        "offer_purpose": offer["purpose"],
                        "offer_topic_filter": offer["topic_filter"],
                        "offer_schema_id": offer["schema_id"],
                        "offer_expires_at": offer["expires_at"],
                        "live_instance_ids": live_instances,
                        "candidate_instances": candidate_instances,
                        "provider_live": bool(live_instances),
                        "availability": "live" if live_instances else "no_live_instance",
                        "facts": {
                            "topic_filters_overlap": topic_overlap,
                            "schemas_compatible": schemas_match,
                        },
                        "reason": "topic filters overlap and declared schemas are compatible",
                    }
                )
                matched_subscription_ids.add(subscription["subscription_id"])
        unmet = []
        for subscription in subscriptions:
            if subscription["subscription_id"] not in matched_subscription_ids:
                candidates = []
                for offer in offers:
                    topic_overlap = filters_overlap(
                        subscription["topic_filter"], offer["topic_filter"]
                    )
                    schemas_match = schema_compatible(
                        subscription["schema_id"], offer["schema_id"]
                    )
                    mismatch_reasons = []
                    if not topic_overlap:
                        mismatch_reasons.append("topic_filter_mismatch")
                    if not schemas_match:
                        mismatch_reasons.append("schema_mismatch")
                    candidates.append(
                        {
                            "offer_id": offer["offer_id"],
                            "provider_agent_id": self._owner_agent(
                                offer["owner_type"], offer["owner_id"]
                            ),
                            "offer_purpose": offer["purpose"],
                            "offer_topic_filter": offer["topic_filter"],
                            "offer_schema_id": offer["schema_id"],
                            "facts": {
                                "topic_filters_overlap": topic_overlap,
                                "schemas_compatible": schemas_match,
                            },
                            "mismatch_reasons": mismatch_reasons,
                        }
                    )
                if not offers:
                    classification = "no_active_offer"
                    reason = "no active Offer exists in this Partition"
                elif any(item["facts"]["topic_filters_overlap"] for item in candidates):
                    classification = "schema_mismatch"
                    reason = "overlapping Offers declare an incompatible schema"
                else:
                    classification = "topic_filter_mismatch"
                    reason = "active Offers have no overlapping topic filter"
                unmet.append(
                    {
                        "subscription_id": subscription["subscription_id"],
                        "kind": subscription["kind"],
                        "owner_type": subscription["owner_type"],
                        "owner_id": subscription["owner_id"],
                        "subscriber_agent_id": self._owner_agent(
                            subscription["owner_type"], subscription["owner_id"]
                        ),
                        "purpose": subscription["purpose"],
                        "topic_filter": subscription["topic_filter"],
                        "schema_id": subscription["schema_id"],
                        "expires_at": subscription["expires_at"],
                        "correlation_id": subscription["correlation_id"],
                        "classification": classification,
                        "reason": reason,
                        "candidates": candidates,
                    }
                )
        return {
            "matches": pairs,
            "unmet": unmet,
        }

    def _is_advertised(
        self,
        connection: sqlite3.Connection,
        instance: dict,
        topic: str,
        schema_id: str | None,
        now_text: str,
    ) -> bool:
        rows = connection.execute(
            """
            SELECT * FROM offers
            WHERE state='active' AND (expires_at IS NULL OR expires_at>?)
              AND ((owner_type='instance' AND owner_id=?) OR (owner_type='agent' AND owner_id=?))
            """,
            (now_text, instance["instance_id"], instance["agent_id"]),
        ).fetchall()
        return any(topic_matches(row["topic_filter"], topic) and schema_compatible(row["schema_id"], schema_id) for row in rows)

    def publish(
        self,
        *,
        producer_instance_id: str,
        topic: str,
        purpose: str,
        payload_kind: str,
        payload_text: str,
        artifact_digest: str | None,
        schema_id: str | None,
        correlation_id: str | None,
        causation_id: str | None,
        expires_at: str | None,
        idempotency_key: str | None,
        retained: bool,
        now: datetime,
    ) -> dict:
        instance = self._instance_row(producer_instance_id)
        if instance["lifecycle_state"] != "active":
            raise Conflict(f"producer instance is stopped: {producer_instance_id}")
        at = iso(now)
        command = {
            "producer_instance_id": producer_instance_id,
            "topic": topic,
            "purpose": purpose,
            "payload_kind": payload_kind,
            "payload_text": payload_text,
            "artifact_digest": artifact_digest,
            "schema_id": schema_id,
            "correlation_id": correlation_id,
            "causation_id": causation_id,
            "expires_at": expires_at,
            "retained": retained,
        }
        digest = command_digest(command)
        with self.transaction() as connection:
            if idempotency_key:
                existing = connection.execute(
                    "SELECT * FROM messages WHERE producer_instance_id=? AND idempotency_key=?",
                    (producer_instance_id, idempotency_key),
                ).fetchone()
                if existing:
                    if existing["command_digest"] != digest:
                        raise Conflict("idempotency key was already used with different publication content")
                    result = dict(existing)
                    result["retained"] = bool(result["retained"])
                    result["advertised"] = bool(result["advertised"])
                    result["deduplicated"] = True
                    result["delivery_count"] = connection.execute(
                        "SELECT COUNT(*) FROM deliveries WHERE message_id=?", (existing["message_id"],)
                    ).fetchone()[0]
                    return result

            message_id = new_id("msg")
            advertised = self._is_advertised(connection, instance, topic, schema_id, at)
            connection.execute(
                """
                INSERT INTO messages(
                    message_id, producer_instance_id, topic, purpose, payload_kind,
                    payload_text, artifact_digest, schema_id, correlation_id,
                    causation_id, expires_at, idempotency_key, command_digest,
                    retained, advertised, created_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    message_id,
                    producer_instance_id,
                    topic,
                    purpose,
                    payload_kind,
                    payload_text,
                    artifact_digest,
                    schema_id,
                    correlation_id,
                    causation_id,
                    expires_at,
                    idempotency_key,
                    digest,
                    int(retained),
                    int(advertised),
                    at,
                ),
            )
            subscriptions = connection.execute(
                """
                SELECT * FROM subscriptions
                WHERE state='active' AND (expires_at IS NULL OR expires_at>?)
                  AND (kind='subscription' OR request_state IN ('open', 'response_available'))
                ORDER BY subscription_id
                """,
                (at,),
            ).fetchall()
            delivery_count = 0
            request_ids = []
            for subscription in subscriptions:
                if not topic_matches(subscription["topic_filter"], topic):
                    continue
                if not schema_compatible(subscription["schema_id"], schema_id):
                    continue
                if (
                    subscription["kind"] == "request"
                    and subscription["correlation_id"] != correlation_id
                ):
                    continue
                connection.execute(
                    """
                    INSERT INTO deliveries(
                        delivery_id, message_id, subscription_id, state, created_at, updated_at
                    ) VALUES (?, ?, ?, 'queued', ?, ?)
                    """,
                    (new_id("del"), message_id, subscription["subscription_id"], at, at),
                )
                delivery_count += 1
                if subscription["kind"] == "request":
                    request_ids.append(subscription["subscription_id"])
            for request_id in request_ids:
                connection.execute(
                    "UPDATE subscriptions SET request_state='response_available', updated_at=? WHERE subscription_id=?",
                    (at, request_id),
                )
            if retained:
                connection.execute(
                    """
                    INSERT INTO retained(topic, schema_key, message_id) VALUES (?, ?, ?)
                    ON CONFLICT(topic, schema_key) DO UPDATE SET message_id=excluded.message_id
                    """,
                    (topic, schema_id or "", message_id),
                )
            self._event(
                connection,
                entity_type="message",
                entity_id=message_id,
                event_type="published",
                at=at,
                actor_instance_id=producer_instance_id,
                details={
                    "topic": topic,
                    "schema_id": schema_id,
                    "delivery_count": delivery_count,
                    "retained": retained,
                    "advertised": advertised,
                },
            )
            row = connection.execute("SELECT * FROM messages WHERE message_id=?", (message_id,)).fetchone()
            result = dict(row)
            result["retained"] = bool(result["retained"])
            result["advertised"] = bool(result["advertised"])
            result["deduplicated"] = False
            result["delivery_count"] = delivery_count
            return result

    def _delivery_owned_by(self, subscription: sqlite3.Row | dict, instance: dict) -> bool:
        if subscription["owner_type"] == "instance":
            return subscription["owner_id"] == instance["instance_id"]
        return subscription["owner_id"] == instance["agent_id"]

    def validate_poll_target(
        self, instance_id: str, subscription_id: str | None
    ) -> dict:
        instance = self._instance_row(instance_id)
        if instance["lifecycle_state"] != "active":
            raise Conflict(f"polling instance is stopped: {instance_id}")
        if subscription_id is None:
            return dict(instance)
        subscription = self.connection.execute(
            "SELECT owner_type, owner_id FROM subscriptions WHERE subscription_id=?",
            (subscription_id,),
        ).fetchone()
        if subscription is None:
            raise NotFound(f"subscription or request not found: {subscription_id}")
        if self._delivery_owned_by(subscription, instance):
            return dict(instance)
        if subscription["owner_type"] == "instance":
            hint = (
                f"poll with the exact owning Instance {subscription['owner_id']!r}; "
                "use an Agent-owned durable Subscription when successor Instances must recover it"
            )
        else:
            hint = f"poll with an active Instance registered to Agent {subscription['owner_id']!r}"
        raise OwnershipMismatch(
            f"subscription {subscription_id!r} is owned by "
            f"{subscription['owner_type']} {subscription['owner_id']!r}, not polling "
            f"Instance {instance_id!r}",
            hint=hint,
        )

    def _message_result(self, row: sqlite3.Row | dict, *, include_payload: bool = False) -> dict:
        result = dict(row)
        result["retained"] = bool(result["retained"])
        result["advertised"] = bool(result["advertised"])
        if not include_payload:
            result.pop("payload_text", None)
        elif result.get("payload_kind") == "json":
            result["payload"] = json.loads(result.pop("payload_text"))
        else:
            result["payload"] = result.pop("payload_text")
        return result

    def get_message(self, message_id: str, *, include_payload: bool = False) -> dict:
        row = self.connection.execute("SELECT * FROM messages WHERE message_id=?", (message_id,)).fetchone()
        if row is None:
            raise NotFound(f"message not found: {message_id}")
        return self._message_result(row, include_payload=include_payload)

    def list_messages(
        self,
        *,
        producer_instance_id: str | None = None,
        idempotency_key: str | None = None,
        include_payload: bool = False,
    ) -> list[dict]:
        clauses = []
        values = []
        if producer_instance_id is not None:
            clauses.append("producer_instance_id=?")
            values.append(producer_instance_id)
        if idempotency_key is not None:
            clauses.append("idempotency_key=?")
            values.append(idempotency_key)
        where = " WHERE " + " AND ".join(clauses) if clauses else ""
        rows = self.connection.execute(
            "SELECT * FROM messages" + where + " ORDER BY created_at, message_id", values
        ).fetchall()
        return [self._message_result(row, include_payload=include_payload) for row in rows]

    def _delivery_result(self, row: sqlite3.Row | dict, *, include_payload: bool = True) -> dict:
        result = dict(row)
        result["retained"] = bool(result["retained"])
        result["advertised"] = bool(result["advertised"])
        if not include_payload:
            result.pop("payload_text", None)
        elif result.get("payload_kind") == "json":
            result["payload"] = json.loads(result.pop("payload_text"))
        else:
            result["payload"] = result.pop("payload_text")
        return result

    def poll_once(
        self,
        *,
        instance_id: str,
        subscription_id: str | None,
        limit: int,
        lease_seconds: float,
        now: datetime,
    ) -> list[dict]:
        instance = self.validate_poll_target(instance_id, subscription_id)
        at = iso(now)
        lease_until = iso(add_seconds(now, lease_seconds))
        selected = []
        with self.transaction() as connection:
            expired_rows = connection.execute(
                """
                SELECT d.delivery_id
                FROM deliveries d
                JOIN subscriptions s ON s.subscription_id=d.subscription_id
                JOIN messages m ON m.message_id=d.message_id
                WHERE d.state IN ('queued', 'leased')
                  AND ((s.expires_at IS NOT NULL AND s.expires_at<=?)
                       OR (m.expires_at IS NOT NULL AND m.expires_at<=?))
                ORDER BY d.delivery_id
                """,
                (at, at),
            ).fetchall()
            for expired in expired_rows:
                connection.execute(
                    """
                    UPDATE deliveries
                    SET state='expired', leased_by_instance_id=NULL, lease_until=NULL, updated_at=?
                    WHERE delivery_id=?
                    """,
                    (at, expired["delivery_id"]),
                )
                self._event(
                    connection,
                    entity_type="delivery",
                    entity_id=expired["delivery_id"],
                    event_type="expired",
                    at=at,
                )
            rows = connection.execute(
                """
                SELECT d.*, s.owner_type, s.owner_id, s.kind AS subscription_kind,
                       s.request_state, s.topic_filter, s.purpose AS subscription_purpose,
                       m.producer_instance_id, m.topic, m.purpose AS message_purpose,
                       m.payload_kind, m.payload_text, m.artifact_digest, m.schema_id,
                       m.correlation_id, m.causation_id, m.expires_at AS message_expires_at,
                       m.retained, m.advertised, m.created_at AS message_created_at
                FROM deliveries d
                JOIN subscriptions s ON s.subscription_id=d.subscription_id
                JOIN messages m ON m.message_id=d.message_id
                WHERE (d.state='queued' OR (d.state='leased' AND d.lease_until<=?))
                  AND s.state='active' AND (s.expires_at IS NULL OR s.expires_at>?)
                  AND (m.expires_at IS NULL OR m.expires_at>?)
                  AND (? IS NULL OR d.subscription_id=?)
                ORDER BY m.created_at, d.delivery_id
                """,
                (at, at, at, subscription_id, subscription_id),
            ).fetchall()
            for row in rows:
                if not self._delivery_owned_by(row, instance):
                    continue
                if row["state"] == "leased":
                    self._event(
                        connection,
                        entity_type="delivery",
                        entity_id=row["delivery_id"],
                        event_type="lease_timed_out",
                        at=at,
                        actor_instance_id=instance_id,
                        details={
                            "previous_lease_until": row["lease_until"],
                            "attempt": int(row["attempt"]),
                        },
                    )
                if int(row["attempt"]) >= MAX_DELIVERY_ATTEMPTS:
                    connection.execute(
                        """
                        UPDATE deliveries
                        SET state='dead_letter', leased_by_instance_id=NULL,
                            lease_until=NULL, updated_at=?
                        WHERE delivery_id=?
                        """,
                        (at, row["delivery_id"]),
                    )
                    self._event(
                        connection,
                        entity_type="delivery",
                        entity_id=row["delivery_id"],
                        event_type="dead_lettered",
                        at=at,
                        actor_instance_id=instance_id,
                        details={"attempts": int(row["attempt"])},
                    )
                    continue
                connection.execute(
                    """
                    UPDATE deliveries
                    SET state='leased', attempt=attempt+1, leased_by_instance_id=?,
                        lease_until=?, updated_at=?
                    WHERE delivery_id=?
                    """,
                    (instance_id, lease_until, at, row["delivery_id"]),
                )
                leased = dict(row)
                leased.update(
                    {
                        "state": "leased",
                        "attempt": int(row["attempt"]) + 1,
                        "leased_by_instance_id": instance_id,
                        "lease_until": lease_until,
                        "updated_at": at,
                    }
                )
                selected.append(self._delivery_result(leased))
                self._event(
                    connection,
                    entity_type="delivery",
                    entity_id=row["delivery_id"],
                    event_type="leased",
                    at=at,
                    actor_instance_id=instance_id,
                    details={"attempt": leased["attempt"], "lease_until": lease_until},
                )
                if len(selected) >= limit:
                    break
        return selected

    def ack(
        self,
        delivery_id: str,
        actor_type: str,
        actor_id: str,
        now: datetime,
    ) -> dict:
        at = iso(now)
        with self.transaction() as connection:
            row = connection.execute(
                """
                SELECT d.*, s.owner_type, s.owner_id, s.kind AS subscription_kind,
                       s.request_state
                FROM deliveries d JOIN subscriptions s ON s.subscription_id=d.subscription_id
                WHERE d.delivery_id=?
                """,
                (delivery_id,),
            ).fetchone()
            if row is None:
                raise NotFound(f"delivery not found: {delivery_id}")
            if actor_type == "instance":
                instance = self._instance_row(actor_id)
                if instance["lifecycle_state"] != "active":
                    raise Conflict(f"acting instance is stopped: {actor_id}")
                if not self._delivery_owned_by(row, instance):
                    raise Conflict("delivery is not owned by the acting Instance or its Agent")
                actor_instance_id = actor_id
            elif actor_type == "agent":
                self.get_agent(actor_id)
                if row["owner_type"] != "agent" or row["owner_id"] != actor_id:
                    raise Conflict("direct Agent acknowledgement requires an Agent-owned Delivery")
                actor_instance_id = None
            else:
                raise InvalidInput(f"invalid actor type: {actor_type}")
            if row["state"] == "acked":
                return {"delivery_id": delivery_id, "state": "acked", "acked_at": row["acked_at"], "deduplicated": True}
            if actor_type == "instance" and (
                row["state"] != "leased" or row["leased_by_instance_id"] != actor_id
            ):
                raise Conflict("delivery must be leased by the acting Instance before acknowledgement")
            if (
                actor_type == "agent"
                and row["state"] == "leased"
                and row["lease_until"]
                and row["lease_until"] > at
            ):
                raise Conflict("direct Agent acknowledgement cannot take an active Instance lease")
            if row["state"] not in {"queued", "leased"}:
                raise Conflict(f"delivery cannot be acknowledged from state {row['state']!r}")
            connection.execute(
                """
                UPDATE deliveries
                SET state='acked', leased_by_instance_id=NULL, lease_until=NULL,
                    acked_at=?, updated_at=?
                WHERE delivery_id=?
                """,
                (at, at, delivery_id),
            )
            if row["subscription_kind"] == "request":
                connection.execute(
                    """
                    UPDATE subscriptions
                    SET request_state='fulfilled', state='cancelled', updated_at=?
                    WHERE subscription_id=?
                    """,
                    (at, row["subscription_id"]),
                )
                self._expire_subscription_deliveries(
                    connection,
                    [row["subscription_id"]],
                    at=at,
                    reason="request_fulfilled",
                    actor_instance_id=actor_instance_id,
                )
            self._event(
                connection,
                entity_type="delivery",
                entity_id=delivery_id,
                event_type="acked",
                at=at,
                actor_instance_id=actor_instance_id,
                details={
                    "subscription_id": row["subscription_id"],
                    "actor_type": actor_type,
                    "actor_id": actor_id,
                },
            )
        return {"delivery_id": delivery_id, "state": "acked", "acked_at": at, "deduplicated": False}

    def preview_deliveries(self, instance_id: str, now: datetime, *, limit: int = 100) -> list[dict]:
        instance = self._instance_row(instance_id)
        at = iso(now)
        rows = self.connection.execute(
            """
            SELECT d.*, s.owner_type, s.owner_id, s.kind AS subscription_kind,
                   s.state AS subscription_state, s.expires_at AS subscription_expires_at,
                   s.topic_filter, m.producer_instance_id, m.topic,
                   m.purpose AS message_purpose, m.payload_kind, m.payload_text,
                   m.artifact_digest, m.schema_id, m.correlation_id, m.causation_id,
                   m.expires_at AS message_expires_at, m.retained, m.advertised,
                   m.created_at AS message_created_at
            FROM deliveries d
            JOIN subscriptions s ON s.subscription_id=d.subscription_id
            JOIN messages m ON m.message_id=d.message_id
            WHERE d.state IN ('queued', 'leased')
              AND s.state='active' AND (s.expires_at IS NULL OR s.expires_at>?)
              AND (m.expires_at IS NULL OR m.expires_at>?)
            ORDER BY m.created_at, d.delivery_id
            """,
            (at, at),
        ).fetchall()
        result = []
        for row in rows:
            if not self._delivery_owned_by(row, instance):
                continue
            item = self._delivery_result(row, include_payload=False)
            item["available"] = row["state"] == "queued" or (row["lease_until"] and row["lease_until"] <= at)
            item["ack_required"] = row["state"] == "leased" and row["leased_by_instance_id"] == instance_id
            result.append(item)
            if len(result) >= limit:
                break
        return result

    def list_deliveries(self, now: datetime, *, include_payload: bool = False) -> list[dict]:
        at = iso(now)
        rows = self.connection.execute(
            """
            SELECT d.*, s.owner_type, s.owner_id, s.kind AS subscription_kind,
                   s.state AS subscription_state, s.expires_at AS subscription_expires_at,
                   m.producer_instance_id, m.topic, m.purpose AS message_purpose,
                   m.payload_kind, m.payload_text, m.artifact_digest, m.schema_id,
                   m.correlation_id, m.causation_id, m.expires_at AS message_expires_at,
                   m.retained, m.advertised, m.created_at AS message_created_at
            FROM deliveries d
            JOIN subscriptions s ON s.subscription_id=d.subscription_id
            JOIN messages m ON m.message_id=d.message_id
            ORDER BY m.created_at, d.delivery_id
            """
        ).fetchall()
        result = []
        for row in rows:
            item = self._delivery_result(row, include_payload=include_payload)
            if item["state"] not in {"acked", "dead_letter", "expired"} and (
                item.get("subscription_state") == "cancelled"
                or (item.get("subscription_expires_at") and item["subscription_expires_at"] <= at)
                or (item.get("message_expires_at") and item["message_expires_at"] <= at)
            ):
                item["effective_state"] = "expired"
            elif item["state"] == "leased" and item.get("lease_until") and item["lease_until"] <= at:
                item["effective_state"] = "queued"
            else:
                item["effective_state"] = item["state"]
            result.append(item)
        return result

    def status(self, now: datetime) -> dict:
        agents = self.list_agents()
        instances = self.list_instances(now)
        subscriptions = self.list_subscriptions(now)
        offers = self.list_offers(now)
        deliveries = self.list_deliveries(now)
        event_count = self.connection.execute("SELECT COUNT(*) FROM events").fetchone()[0]
        metadata = self.metadata()
        return {
            "storage": {
                "schema_version": SCHEMA_VERSION,
                "max_delivery_attempts": MAX_DELIVERY_ATTEMPTS,
                "max_event_rows": MAX_EVENT_ROWS,
                "event_rows": event_count,
                "events_pruned": int(metadata.get("events_pruned", "0")),
            },
            "counts": {
                "agents": len(agents),
                "instances": len(instances),
                "live_instances": sum(1 for item in instances if item["liveness"] == "alive"),
                "active_subscriptions": sum(1 for item in subscriptions if item["effective_state"] == "active"),
                "active_offers": sum(1 for item in offers if item["effective_state"] == "active"),
                "pending_deliveries": sum(1 for item in deliveries if item["effective_state"] in {"queued", "leased"}),
            },
            "instances": instances,
        }

    def next_actions(self, instance_id: str, now: datetime) -> dict:
        instance = self.get_instance(instance_id, now)
        deliveries = self.preview_deliveries(instance_id, now)
        match_result = self.matches(now)
        own_offer_ids = {
            offer["offer_id"]
            for offer in self.list_offers(now)
            if offer["effective_state"] == "active"
            and (
                (offer["owner_type"] == "instance" and offer["owner_id"] == instance_id)
                or (offer["owner_type"] == "agent" and offer["owner_id"] == instance["agent_id"])
            )
        }
        items = []
        for delivery in deliveries:
            if delivery["ack_required"]:
                items.append(
                    {
                        "kind": "acknowledge_delivery",
                        "entity_id": delivery["delivery_id"],
                        "reason": "the Delivery is leased by this Instance and is not acknowledged",
                        "command": f"purposebus ack --instance {instance_id} {delivery['delivery_id']}",
                    }
                )
            elif delivery["available"]:
                items.append(
                    {
                        "kind": "read_delivery",
                        "entity_id": delivery["delivery_id"],
                        "reason": "a matching durable Delivery is available",
                        "command": f"purposebus poll --instance {instance_id}",
                    }
                )
        seen_requests = set()
        for pair in match_result["matches"]:
            if pair["offer_id"] not in own_offer_ids or pair["subscription_kind"] != "request":
                continue
            if pair["subscription_id"] in seen_requests:
                continue
            seen_requests.add(pair["subscription_id"])
            items.append(
                {
                    "kind": "consider_request",
                    "entity_id": pair["subscription_id"],
                    "reason": (
                        f"request purpose {pair['subscription_purpose']!r} matches offer purpose "
                        f"{pair['offer_purpose']!r}; topic filters overlap, schemas are compatible, "
                        f"and provider availability is {pair['availability']}"
                    ),
                    "requester_agent_id": pair["subscriber_agent_id"],
                    "request_purpose": pair["subscription_purpose"],
                    "request_topic_filter": pair["subscription_topic_filter"],
                    "request_schema_id": pair["subscription_schema_id"],
                    "request_expires_at": pair["subscription_expires_at"],
                    "request_correlation_id": pair["correlation_id"],
                    "offer_id": pair["offer_id"],
                    "provider_agent_id": pair["provider_agent_id"],
                    "offer_purpose": pair["offer_purpose"],
                    "offer_topic_filter": pair["offer_topic_filter"],
                    "offer_schema_id": pair["offer_schema_id"],
                    "provider_live": pair["provider_live"],
                    "live_instance_ids": pair["live_instance_ids"],
                    "facts": pair["facts"],
                    "command": f"purposebus request show {pair['subscription_id']}",
                }
            )
        remaining = datetime.fromisoformat(instance["lease_expires_at"].replace("Z", "+00:00")) - now
        if instance["lifecycle_state"] == "active" and remaining.total_seconds() <= max(1.0, float(instance["lease_seconds"]) / 3):
            items.append(
                {
                    "kind": "heartbeat",
                    "entity_id": instance_id,
                    "reason": "the Instance heartbeat lease is approaching expiry or has expired",
                    "command": f"purposebus instance heartbeat {instance_id}",
                }
            )
        warnings = []
        if instance["liveness"] != "alive":
            warnings.append(
                {
                    "kind": "liveness",
                    "entity_id": instance_id,
                    "reason": instance["liveness_reason"],
                    "state": instance["liveness"],
                }
            )
        return {"instance": instance, "items": items, "warnings": warnings}

    def events(self, *, limit: int = 100) -> list[dict]:
        rows = self.connection.execute(
            "SELECT * FROM events ORDER BY sequence DESC LIMIT ?", (limit,)
        ).fetchall()
        result = []
        for row in reversed(rows):
            item = dict(row)
            item["details"] = json.loads(item.pop("details_json"))
            result.append(item)
        return result
