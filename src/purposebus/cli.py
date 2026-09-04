from __future__ import annotations

import argparse
import json
import os
import sqlite3
import sys
import time
from datetime import datetime

from . import __version__
from .errors import PurposeBusError, InvalidInput, NoMessage
from .partition import resolve_partition
from .store import Store
from .util import (
    add_seconds,
    capabilities,
    expiry,
    iso,
    json_text,
    new_id,
    now_utc,
    parse_duration,
    parse_json_payload,
    parse_time,
    validate_filter,
    validate_identifier,
    validate_inline,
    validate_topic,
)


HELP_TOPICS = {
    "usecases": """PurposeBus use cases

Discover a provider:
  purposebus match
  purposebus next --instance INSTANCE_ID

Request information:
  purposebus request create TOPIC --purpose TEXT --instance INSTANCE_ID --expires-in 5m

Publish and receive:
  purposebus publish TOPIC --purpose TEXT --instance INSTANCE_ID --json-payload JSON --idempotency-key KEY
  purposebus message list --producer INSTANCE_ID --idempotency-key KEY
  purposebus poll --instance INSTANCE_ID --wait 30s
  purposebus ack DELIVERY_ID --instance INSTANCE_ID

Inspect without mutation:
  purposebus status
  purposebus agent list
  purposebus instance list
  purposebus message list
  purposebus delivery list
""",
    "concepts": """PurposeBus concepts

Agent: stable human or AI identity inside one Partition.
Instance: one concrete Agent run or interactive presence.
Subscription: purpose-bearing information need.
Offer: purpose-bearing declaration of information that can be provided.
Request: one-shot expiring Subscription with correlation.
Message: published information.
Delivery: subscriber-specific lease and acknowledgement state.
Partition: application-level discovery and routing boundary.

Activity and liveness are separate. PID is observation evidence, not identity or authority.
Offers, matches, Messages, and purposebus next never authorize unrelated work.
""",
    "partitions": """PurposeBus Partitions

The default Partition is the canonical Git worktree root, or the canonical current
directory outside Git. Override it with --partition PATH. Dynamic state is stored
outside the checkout under XDG state, or under --state-dir / PURPOSEBUS_STATE_DIR.

There is no implicit cross-Partition discovery or delivery. A Partition is not an
OS security boundary.
""",
    "agent": """Agent integration

Existing Agents call commands directly; a PurposeBus launcher is not required.

  purposebus agent register AGENT --kind ai --description TEXT
  purposebus instance start AGENT --id INSTANCE --objective TEXT --pid PID
  purposebus instance heartbeat INSTANCE
  purposebus next --instance INSTANCE

Use --format json for stable machine-readable results. Mutations require explicit
Agent or Instance identity; PurposeBus never chooses an arbitrary live Instance. Every
JSON document carries an explicit purposebus.*.v1 schema identity. On ambiguous publish
outcomes, read back with message list before retrying the identical command.

An Instance-owned Subscription can be polled only by that exact Instance identity,
including after a new CLI process starts. An Agent-owned durable Subscription can be
recovered by another active Instance of the same Agent. An explicit --subscription
owned by someone else fails as ownership_mismatch rather than no_message.
""",
}


class Parser(argparse.ArgumentParser):
    def error(self, message):
        raise InvalidInput(message, hint=f"run {self.prog} --help")


def _owner_arguments(parser: argparse.ArgumentParser) -> None:
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--agent", dest="owner_agent")
    group.add_argument("--instance", dest="owner_instance")


def _actor_arguments(parser: argparse.ArgumentParser) -> None:
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--agent", dest="actor_agent")
    group.add_argument("--instance", dest="actor_instance")


def _owner(args) -> tuple[str, str]:
    if getattr(args, "owner_agent", None):
        return "agent", validate_identifier(args.owner_agent, "Agent ID")
    return "instance", validate_identifier(args.owner_instance, "Instance ID")


def build_parser() -> Parser:
    parser = Parser(
        prog="purposebus",
        description="Local-first coordination queue for human and AI agents.",
    )
    parser.add_argument("--partition", metavar="PATH", help="explicit project communication boundary")
    parser.add_argument("--state-dir", metavar="PATH", help="override PurposeBus state root")
    parser.add_argument("--format", choices=("human", "json"), default="human")
    parser.add_argument("--at", metavar="ISO8601", help="override current time for deterministic tests")
    parser.add_argument("--version", action="version", version=f"purposebus {__version__}")
    commands = parser.add_subparsers(dest="command", required=True)

    commands.add_parser("init", help="initialize the resolved Partition")

    help_parser = commands.add_parser("help", help="show task-oriented or conceptual guidance")
    help_parser.add_argument("topic", nargs="?", choices=tuple(HELP_TOPICS), default="usecases")

    agent = commands.add_parser("agent", help="manage stable Agent registry records")
    agent_commands = agent.add_subparsers(dest="agent_command", required=True)
    register = agent_commands.add_parser("register", help="register one Agent")
    register.add_argument("agent_id")
    register.add_argument("--kind", choices=("human", "ai"), required=True)
    register.add_argument("--description", required=True)
    register.add_argument("--capabilities", help="comma-separated stable capability identifiers")
    agent_commands.add_parser("list", help="list Agents")
    agent_show = agent_commands.add_parser("show", help="show one Agent")
    agent_show.add_argument("agent_id")

    instance = commands.add_parser("instance", help="manage concrete Agent Instances")
    instance_commands = instance.add_subparsers(dest="instance_command", required=True)
    instance_start = instance_commands.add_parser("start", help="register one active Instance")
    instance_start.add_argument("agent_id")
    instance_start.add_argument("--id", dest="instance_id")
    instance_start.add_argument("--objective", required=True)
    instance_start.add_argument("--activity", choices=("idle", "busy", "draining"), default="idle")
    instance_start.add_argument("--lease", default="30s")
    instance_start.add_argument("--pid", type=int, help="external Agent process PID; omitted for lease-only presence")
    heartbeat = instance_commands.add_parser("heartbeat", help="refresh one Instance lease")
    heartbeat.add_argument("instance_id")
    heartbeat.add_argument("--activity", choices=("idle", "busy", "draining"))
    heartbeat.add_argument("--objective")
    stop = instance_commands.add_parser("stop", help="explicitly stop one Instance")
    stop.add_argument("instance_id")
    instance_commands.add_parser("list", help="list Instances")
    instance_show = instance_commands.add_parser("show", help="show one Instance")
    instance_show.add_argument("instance_id")

    subscription = commands.add_parser("subscription", help="manage durable information needs")
    subscription_commands = subscription.add_subparsers(dest="subscription_command", required=True)
    subscription_add = subscription_commands.add_parser("add", help="add one Subscription")
    subscription_add.add_argument("topic_filter")
    _owner_arguments(subscription_add)
    subscription_add.add_argument("--purpose", required=True)
    subscription_add.add_argument("--schema")
    subscription_add.add_argument("--expires-in")
    subscription_add.add_argument("--ephemeral", action="store_true")
    subscription_add.add_argument("--id", dest="subscription_id")
    subscription_commands.add_parser("list", help="list Subscriptions")
    subscription_show = subscription_commands.add_parser("show", help="show one Subscription")
    subscription_show.add_argument("subscription_id")
    for action in ("pause", "resume", "cancel"):
        action_parser = subscription_commands.add_parser(action, help=f"{action} one Subscription")
        action_parser.add_argument("subscription_id")
        _actor_arguments(action_parser)

    offer = commands.add_parser("offer", help="manage current publishable declarations")
    offer_commands = offer.add_subparsers(dest="offer_command", required=True)
    offer_add = offer_commands.add_parser("add", help="add one Offer")
    offer_add.add_argument("topic_filter")
    _owner_arguments(offer_add)
    offer_add.add_argument("--purpose", required=True)
    offer_add.add_argument("--schema")
    offer_add.add_argument("--expires-in")
    offer_add.add_argument("--id", dest="offer_id")
    offer_commands.add_parser("list", help="list Offers")
    offer_show = offer_commands.add_parser("show", help="show one Offer")
    offer_show.add_argument("offer_id")
    for action in ("pause", "resume", "cancel"):
        action_parser = offer_commands.add_parser(action, help=f"{action} one Offer")
        action_parser.add_argument("offer_id")
        _actor_arguments(action_parser)

    request = commands.add_parser("request", help="manage one-shot expiring information needs")
    request_commands = request.add_subparsers(dest="request_command", required=True)
    request_create = request_commands.add_parser("create", help="create one Request")
    request_create.add_argument("topic_filter")
    _owner_arguments(request_create)
    request_create.add_argument("--purpose", required=True)
    request_create.add_argument("--schema")
    request_create.add_argument("--expires-in", default="5m")
    request_create.add_argument("--correlation-id")
    request_create.add_argument("--id", dest="request_id")
    request_create.add_argument("--wait", help="wait for a response; requires Instance ownership")
    request_commands.add_parser("list", help="list Requests")
    request_show = request_commands.add_parser("show", help="show one Request")
    request_show.add_argument("request_id")
    request_cancel = request_commands.add_parser("cancel", help="cancel one Request")
    request_cancel.add_argument("request_id")
    _actor_arguments(request_cancel)

    publish = commands.add_parser("publish", help="publish one Message")
    publish.add_argument("topic")
    publish.add_argument("--instance", required=True)
    publish.add_argument("--purpose", required=True)
    payload = publish.add_mutually_exclusive_group(required=True)
    payload.add_argument("--text")
    payload.add_argument("--json-payload")
    payload.add_argument("--reference")
    publish.add_argument("--artifact-digest")
    publish.add_argument("--schema")
    publish.add_argument("--correlation-id")
    publish.add_argument("--causation-id")
    publish.add_argument("--expires-in")
    publish.add_argument("--idempotency-key")
    publish.add_argument("--retain", action="store_true")

    message = commands.add_parser("message", help="inspect published Messages")
    message_commands = message.add_subparsers(dest="message_command", required=True)
    message_list = message_commands.add_parser("list", help="list Message metadata without payloads")
    message_list.add_argument("--producer", help="filter by producer Instance ID")
    message_list.add_argument("--idempotency-key", help="filter by producer-scoped idempotency key")
    message_show = message_commands.add_parser("show", help="show one Message")
    message_show.add_argument("message_id")
    message_show.add_argument("--include-payload", action="store_true")

    poll = commands.add_parser("poll", help="lease matching Deliveries")
    poll.add_argument("--instance", required=True)
    poll.add_argument("--subscription")
    poll.add_argument("--limit", type=int, default=1)
    poll.add_argument("--lease", default="30s")
    poll.add_argument("--wait", default="0s")

    ack = commands.add_parser("ack", help="acknowledge one leased Delivery")
    ack.add_argument("delivery_id")
    _actor_arguments(ack)

    commands.add_parser("match", help="show matching Offers and unmet demand")
    commands.add_parser("status", help="show Partition and Instance status")

    next_parser = commands.add_parser("next", help="show read-only actions for one Instance")
    next_parser.add_argument("--instance", required=True)

    events = commands.add_parser("events", help="show non-payload event history")
    events.add_argument("--limit", type=int, default=100)

    delivery = commands.add_parser("delivery", help="inspect Delivery state")
    delivery_commands = delivery.add_subparsers(dest="delivery_command", required=True)
    delivery_commands.add_parser("list", help="list Deliveries without payloads")

    return parser


def _human_lines(value, indent=0):
    prefix = " " * indent
    if isinstance(value, dict):
        for key, item in value.items():
            if isinstance(item, (dict, list)):
                yield f"{prefix}{key}:"
                yield from _human_lines(item, indent + 2)
            else:
                rendered = "-" if item is None else str(item).lower() if isinstance(item, bool) else str(item)
                yield f"{prefix}{key}: {rendered}"
    elif isinstance(value, list):
        if not value:
            yield f"{prefix}[]"
        for item in value:
            if isinstance(item, dict):
                yield f"{prefix}-"
                yield from _human_lines(item, indent + 2)
            else:
                yield f"{prefix}- {item}"
    else:
        yield f"{prefix}{value}"


def emit(args, schema: str, result, partition=None, actor=None) -> None:
    document = {"schema": schema, "actor": actor, "result": result}
    if partition is not None:
        document["partition"] = partition.as_dict()
    if args.format == "json":
        print(json_text(document))
    else:
        for line in _human_lines(document):
            print(line)


def emit_error(args, error: PurposeBusError) -> None:
    document = {
        "schema": "purposebus.error.v1",
        "error": error.error,
        "message": str(error),
        "hint": error.hint,
    }
    if getattr(args, "format", "human") == "json":
        print(json_text(document), file=sys.stderr)
    else:
        print(f"error: {error.error}: {error}", file=sys.stderr)
        if error.hint:
            print(f"hint: {error.hint}", file=sys.stderr)


def _nonempty(value: str, label: str) -> str:
    if not value.strip():
        raise InvalidInput(f"{label} must not be empty")
    return value


def _actor(args) -> tuple[str, str]:
    if getattr(args, "actor_agent", None):
        return "agent", validate_identifier(args.actor_agent, "Agent ID")
    return "instance", validate_identifier(args.actor_instance, "Instance ID")


def _identity(identity_type: str, identity_id: str) -> dict:
    return {"type": identity_type, "id": identity_id}


def _output_actor(args, result) -> dict | None:
    if args.command == "agent" and args.agent_command == "register":
        return _identity("agent", result["agent_id"])
    if args.command == "instance":
        if args.instance_command == "start":
            return _identity("instance", result["instance_id"])
        if args.instance_command in {"heartbeat", "stop"}:
            return _identity("instance", args.instance_id)
    if args.command in {"subscription", "offer"}:
        subcommand = getattr(args, f"{args.command}_command")
        if subcommand == "add":
            owner_type, owner_id = _owner(args)
            return _identity(owner_type, owner_id)
        if subcommand in {"pause", "resume", "cancel"}:
            actor_type, actor_id = _actor(args)
            return _identity(actor_type, actor_id)
    if args.command == "request":
        if args.request_command == "create":
            owner_type, owner_id = _owner(args)
            return _identity(owner_type, owner_id)
        if args.request_command == "cancel":
            actor_type, actor_id = _actor(args)
            return _identity(actor_type, actor_id)
    if args.command in {"publish", "poll", "next"}:
        return _identity("instance", args.instance)
    if args.command == "ack":
        actor_type, actor_id = _actor(args)
        return _identity(actor_type, actor_id)
    return None


def _normalize_global_options(argv: list[str]) -> list[str]:
    """Allow root context options on either side of a nested subcommand."""
    value_options = {"--partition", "--state-dir", "--format", "--at"}
    global_arguments: list[str] = []
    command_arguments: list[str] = []
    index = 0
    while index < len(argv):
        value = argv[index]
        option = value.split("=", 1)[0]
        if option in value_options:
            global_arguments.append(value)
            if "=" not in value:
                if index + 1 >= len(argv):
                    global_arguments.append("")
                else:
                    index += 1
                    global_arguments.append(argv[index])
        elif value == "--version":
            global_arguments.append(value)
        else:
            command_arguments.append(value)
        index += 1
    return global_arguments + command_arguments


def _read_store(partition) -> Store:
    return Store(partition, readonly=True)


def _write_store(partition) -> Store:
    return Store(partition, readonly=False)


def _poll_wait(
    store: Store,
    *,
    instance_id: str,
    subscription_id: str | None,
    limit: int,
    lease_seconds: float,
    wait_seconds: float,
    fixed_time: datetime | None,
) -> list[dict]:
    if limit <= 0 or limit > 100:
        raise InvalidInput("--limit must be between 1 and 100")
    if lease_seconds <= 0:
        raise InvalidInput("--lease must be greater than zero")
    if wait_seconds < 0:
        raise InvalidInput("--wait must not be negative")
    if fixed_time is not None and wait_seconds > 0:
        raise InvalidInput("blocking --wait cannot be combined with --at")
    if wait_seconds == 0:
        current = fixed_time or now_utc()
        deliveries = store.poll_once(
            instance_id=instance_id,
            subscription_id=subscription_id,
            limit=limit,
            lease_seconds=lease_seconds,
            now=current,
        )
        if not deliveries:
            raise NoMessage()
        return deliveries

    store.validate_poll_target(instance_id, subscription_id)
    started = now_utc()
    deadline = add_seconds(started, wait_seconds)
    previous_activity = store.set_wait(instance_id, started, deadline, subscription_id, os.getpid())
    last_refresh = started
    try:
        while True:
            current = now_utc()
            deliveries = store.poll_once(
                instance_id=instance_id,
                subscription_id=subscription_id,
                limit=limit,
                lease_seconds=lease_seconds,
                now=current,
            )
            if deliveries:
                return deliveries
            if current >= deadline:
                raise NoMessage("poll wait expired without a matching message")
            if (current - last_refresh).total_seconds() >= 1:
                store.refresh_wait(instance_id, current)
                last_refresh = current
            time.sleep(min(0.1, max(0.0, (deadline - current).total_seconds())))
    finally:
        store.clear_wait(instance_id, now_utc(), previous_activity)


def dispatch(args) -> tuple[str, object, object | None]:
    partition = resolve_partition(args.partition, args.state_dir)
    now = parse_time(args.at)

    if args.command == "help":
        return "purposebus.help.v1", {"topic": args.topic, "text": HELP_TOPICS[args.topic]}, partition
    if args.command == "init":
        store, created = Store.initialize(partition, now)
        try:
            return "purposebus.init.v1", {"created": created, "metadata": store.metadata()}, partition
        finally:
            store.close()

    if args.command == "agent":
        if args.agent_command == "register":
            with _write_store(partition) as store:
                result = store.register_agent(
                    validate_identifier(args.agent_id, "Agent ID"),
                    args.kind,
                    _nonempty(args.description, "description"),
                    capabilities(args.capabilities),
                    now,
                )
            return "purposebus.agent-register.v1", result, partition
        with _read_store(partition) as store:
            if args.agent_command == "list":
                result = store.list_agents()
                schema = "purposebus.agent-list.v1"
            else:
                result = store.get_agent(validate_identifier(args.agent_id, "Agent ID"))
                schema = "purposebus.agent-show.v1"
        return schema, result, partition

    if args.command == "instance":
        if args.instance_command == "start":
            lease = parse_duration(args.lease)
            if lease <= 0:
                raise InvalidInput("--lease must be greater than zero")
            with _write_store(partition) as store:
                result = store.start_instance(
                    validate_identifier(args.agent_id, "Agent ID"),
                    validate_identifier(args.instance_id or new_id("ins"), "Instance ID"),
                    _nonempty(args.objective, "objective"),
                    args.activity,
                    lease,
                    args.pid,
                    now,
                )
            return "purposebus.instance-start.v1", result, partition
        if args.instance_command == "heartbeat":
            with _write_store(partition) as store:
                result = store.heartbeat_instance(
                    validate_identifier(args.instance_id, "Instance ID"),
                    now,
                    activity=args.activity,
                    objective=args.objective,
                )
            return "purposebus.instance-heartbeat.v1", result, partition
        if args.instance_command == "stop":
            with _write_store(partition) as store:
                result = store.stop_instance(validate_identifier(args.instance_id, "Instance ID"), now)
            return "purposebus.instance-stop.v1", result, partition
        with _read_store(partition) as store:
            if args.instance_command == "list":
                result = store.list_instances(now)
                schema = "purposebus.instance-list.v1"
            else:
                result = store.get_instance(validate_identifier(args.instance_id, "Instance ID"), now)
                schema = "purposebus.instance-show.v1"
        return schema, result, partition

    if args.command == "subscription":
        if args.subscription_command == "add":
            owner_type, owner_id = _owner(args)
            with _write_store(partition) as store:
                result = store.add_subscription(
                    subscription_id=validate_identifier(
                        args.subscription_id or new_id("sub"), "Subscription ID"
                    ),
                    owner_type=owner_type,
                    owner_id=owner_id,
                    topic_filter=validate_filter(args.topic_filter),
                    purpose=_nonempty(args.purpose, "purpose"),
                    schema_id=args.schema,
                    durable=not args.ephemeral,
                    expires_at=expiry(now, args.expires_in),
                    kind="subscription",
                    correlation_id=None,
                    now=now,
                )
            return "purposebus.subscription-add.v1", result, partition
        if args.subscription_command in {"pause", "resume", "cancel"}:
            actor_type, actor_id = _actor(args)
            with _write_store(partition) as store:
                result = store.change_subscription(
                    validate_identifier(args.subscription_id, "Subscription ID"),
                    args.subscription_command,
                    actor_type,
                    actor_id,
                    now,
                )
            return f"purposebus.subscription-{args.subscription_command}.v1", result, partition
        with _read_store(partition) as store:
            if args.subscription_command == "list":
                result = store.list_subscriptions(now, kind="subscription")
                schema = "purposebus.subscription-list.v1"
            else:
                result = store.get_subscription(
                    validate_identifier(args.subscription_id, "Subscription ID"), now
                )
                schema = "purposebus.subscription-show.v1"
        return schema, result, partition

    if args.command == "offer":
        if args.offer_command == "add":
            owner_type, owner_id = _owner(args)
            with _write_store(partition) as store:
                result = store.add_offer(
                    offer_id=validate_identifier(args.offer_id or new_id("off"), "Offer ID"),
                    owner_type=owner_type,
                    owner_id=owner_id,
                    topic_filter=validate_filter(args.topic_filter),
                    purpose=_nonempty(args.purpose, "purpose"),
                    schema_id=args.schema,
                    expires_at=expiry(now, args.expires_in),
                    now=now,
                )
            return "purposebus.offer-add.v1", result, partition
        if args.offer_command in {"pause", "resume", "cancel"}:
            actor_type, actor_id = _actor(args)
            with _write_store(partition) as store:
                result = store.change_offer(
                    validate_identifier(args.offer_id, "Offer ID"),
                    args.offer_command,
                    actor_type,
                    actor_id,
                    now,
                )
            return f"purposebus.offer-{args.offer_command}.v1", result, partition
        with _read_store(partition) as store:
            if args.offer_command == "list":
                result = store.list_offers(now)
                schema = "purposebus.offer-list.v1"
            else:
                result = store.get_offer(validate_identifier(args.offer_id, "Offer ID"), now)
                schema = "purposebus.offer-show.v1"
        return schema, result, partition

    if args.command == "request":
        if args.request_command == "create":
            owner_type, owner_id = _owner(args)
            request_id = validate_identifier(args.request_id or new_id("req"), "Request ID")
            correlation_id = args.correlation_id or new_id("corr")
            with _write_store(partition) as store:
                request = store.add_subscription(
                    subscription_id=request_id,
                    owner_type=owner_type,
                    owner_id=owner_id,
                    topic_filter=validate_filter(args.topic_filter),
                    purpose=_nonempty(args.purpose, "purpose"),
                    schema_id=args.schema,
                    durable=True,
                    expires_at=expiry(now, args.expires_in),
                    kind="request",
                    correlation_id=correlation_id,
                    now=now,
                )
                if args.wait:
                    if owner_type != "instance":
                        raise InvalidInput("request --wait requires --instance ownership")
                    deliveries = _poll_wait(
                        store,
                        instance_id=owner_id,
                        subscription_id=request_id,
                        limit=1,
                        lease_seconds=30,
                        wait_seconds=parse_duration(args.wait),
                        fixed_time=parse_time(args.at) if args.at else None,
                    )
                    result = {"request": request, "deliveries": deliveries}
                else:
                    result = request
            return "purposebus.request-create.v1", result, partition
        if args.request_command == "cancel":
            actor_type, actor_id = _actor(args)
            with _write_store(partition) as store:
                result = store.change_subscription(
                    validate_identifier(args.request_id, "Request ID"),
                    "cancel",
                    actor_type,
                    actor_id,
                    now,
                )
            return "purposebus.request-cancel.v1", result, partition
        with _read_store(partition) as store:
            if args.request_command == "list":
                result = store.list_subscriptions(now, kind="request")
                schema = "purposebus.request-list.v1"
            else:
                result = store.get_subscription(validate_identifier(args.request_id, "Request ID"), now)
                schema = "purposebus.request-show.v1"
        return schema, result, partition

    if args.command == "publish":
        if args.text is not None:
            payload_kind = "text"
            payload_text = args.text
        elif args.json_payload is not None:
            payload_kind = "json"
            payload_text = parse_json_payload(args.json_payload)
        else:
            payload_kind = "reference"
            payload_text = args.reference
        if args.artifact_digest is not None and payload_kind != "reference":
            raise InvalidInput("--artifact-digest requires --reference")
        validate_inline(payload_text)
        with _write_store(partition) as store:
            result = store.publish(
                producer_instance_id=validate_identifier(args.instance, "Instance ID"),
                topic=validate_topic(args.topic),
                purpose=_nonempty(args.purpose, "purpose"),
                payload_kind=payload_kind,
                payload_text=payload_text,
                artifact_digest=args.artifact_digest,
                schema_id=args.schema,
                correlation_id=args.correlation_id,
                causation_id=args.causation_id,
                expires_at=expiry(now, args.expires_in),
                idempotency_key=args.idempotency_key,
                retained=args.retain,
                now=now,
            )
        safe_result = dict(result)
        safe_result.pop("payload_text", None)
        return "purposebus.publish.v1", safe_result, partition

    if args.command == "message":
        with _read_store(partition) as store:
            if args.message_command == "list":
                if args.idempotency_key and not args.producer:
                    raise InvalidInput("--idempotency-key requires --producer because keys are producer-scoped")
                result = store.list_messages(
                    producer_instance_id=(
                        validate_identifier(args.producer, "producer Instance ID") if args.producer else None
                    ),
                    idempotency_key=args.idempotency_key,
                )
                schema = "purposebus.message-list.v1"
            else:
                result = store.get_message(
                    validate_identifier(args.message_id, "Message ID"),
                    include_payload=args.include_payload,
                )
                schema = "purposebus.message-show.v1"
        return schema, result, partition

    if args.command == "poll":
        fixed_time = parse_time(args.at) if args.at else None
        with _write_store(partition) as store:
            result = _poll_wait(
                store,
                instance_id=validate_identifier(args.instance, "Instance ID"),
                subscription_id=(
                    validate_identifier(args.subscription, "Subscription ID") if args.subscription else None
                ),
                limit=args.limit,
                lease_seconds=parse_duration(args.lease),
                wait_seconds=parse_duration(args.wait),
                fixed_time=fixed_time,
            )
        return "purposebus.poll.v1", result, partition

    if args.command == "ack":
        actor_type, actor_id = _actor(args)
        with _write_store(partition) as store:
            result = store.ack(
                validate_identifier(args.delivery_id, "Delivery ID"),
                actor_type,
                actor_id,
                now,
            )
        return "purposebus.ack.v1", result, partition

    if args.command == "match":
        with _read_store(partition) as store:
            result = store.matches(now)
        return "purposebus.match.v1", result, partition

    if args.command == "status":
        with _read_store(partition) as store:
            result = store.status(now)
        return "purposebus.status.v1", result, partition

    if args.command == "next":
        with _read_store(partition) as store:
            result = store.next_actions(validate_identifier(args.instance, "Instance ID"), now)
        return "purposebus.next.v1", result, partition

    if args.command == "events":
        if args.limit <= 0 or args.limit > 1000:
            raise InvalidInput("--limit must be between 1 and 1000")
        with _read_store(partition) as store:
            result = store.events(limit=args.limit)
        return "purposebus.events.v1", result, partition

    if args.command == "delivery" and args.delivery_command == "list":
        with _read_store(partition) as store:
            result = store.list_deliveries(now)
        return "purposebus.delivery-list.v1", result, partition

    raise InvalidInput("unsupported command")


def main(argv=None) -> int:
    parser = build_parser()
    effective_argv = list(argv) if argv is not None else sys.argv[1:]
    requested_json = any(
        value == "--format=json"
        or (value == "--format" and index + 1 < len(effective_argv) and effective_argv[index + 1] == "json")
        for index, value in enumerate(effective_argv)
    )
    args = argparse.Namespace(format="json" if requested_json else "human")
    try:
        args = parser.parse_args(_normalize_global_options(effective_argv))
        schema, result, partition = dispatch(args)
        if args.command == "help" and args.format == "human":
            print(result["text"].rstrip())
        else:
            emit(args, schema, result, partition, _output_actor(args, result))
        return 0
    except PurposeBusError as exc:
        emit_error(args, exc)
        return exc.exit_code
    except sqlite3.DatabaseError as exc:
        error = PurposeBusError(
            f"SQLite operation failed: {exc}",
            error="storage_failure",
            exit_code=70,
            hint="run purposebus status and inspect the configured state path; state is not reset automatically",
        )
        emit_error(args, error)
        return error.exit_code
    except KeyboardInterrupt:
        error = PurposeBusError("interrupted", error="interrupted", exit_code=130)
        emit_error(args, error)
        return error.exit_code


if __name__ == "__main__":
    raise SystemExit(main())
