from __future__ import annotations

import json
from collections.abc import Callable, Mapping, Sequence
from typing import Any

from .partition import Partition


DEFAULT_COLLECTION_LIMIT = 100
MAX_COLLECTION_LIMIT = 1000
DEFAULT_CANDIDATE_LIMIT = 25
MAX_CANDIDATE_LIMIT = 100


AGENT_FIELDS = (
    "agent_id",
    "kind",
    "description",
    "capabilities",
    "created_at",
    "updated_at",
)

INSTANCE_FIELDS = (
    "instance_id",
    "agent_id",
    "objective",
    "lifecycle_state",
    "declared_activity",
    "activity",
    "heartbeat_at",
    "lease_expires_at",
    "lease_seconds",
    "liveness",
    "liveness_reason",
    "wait_valid",
    "wait_reason",
    "created_at",
    "updated_at",
)

SUBSCRIPTION_FIELDS = (
    "subscription_id",
    "owner_type",
    "owner_id",
    "topic_filter",
    "purpose",
    "schema_id",
    "durable",
    "state",
    "effective_state",
    "expires_at",
    "kind",
    "request_state",
    "effective_request_state",
    "correlation_id",
    "created_at",
    "updated_at",
)

OFFER_FIELDS = (
    "offer_id",
    "owner_type",
    "owner_id",
    "topic_filter",
    "purpose",
    "schema_id",
    "state",
    "effective_state",
    "expires_at",
    "created_at",
    "updated_at",
)

MESSAGE_FIELDS = (
    "message_id",
    "producer_instance_id",
    "topic",
    "purpose",
    "payload_kind",
    "artifact_digest",
    "schema_id",
    "correlation_id",
    "causation_id",
    "expires_at",
    "idempotency_key",
    "retained",
    "advertised",
    "created_at",
    "deduplicated",
    "delivery_count",
)

DELIVERY_FIELDS = (
    "delivery_id",
    "message_id",
    "subscription_id",
    "state",
    "effective_state",
    "attempt",
    "leased_by_instance_id",
    "lease_until",
    "acked_at",
    "created_at",
    "updated_at",
    "owner_type",
    "owner_id",
    "subscription_kind",
    "request_state",
    "subscription_purpose",
    "topic_filter",
    "producer_instance_id",
    "topic",
    "message_purpose",
    "payload_kind",
    "artifact_digest",
    "schema_id",
    "correlation_id",
    "causation_id",
    "message_expires_at",
    "retained",
    "advertised",
    "message_created_at",
    "available",
    "ack_required",
)

EVENT_FIELDS = (
    "sequence",
    "event_id",
    "entity_type",
    "entity_id",
    "event_type",
    "actor_instance_id",
    "at",
)

EVENT_DETAIL_FIELDS = {
    ("agent", "registered"): ("kind", "capabilities", "actor_type", "actor_id"),
    ("instance", "started"): ("agent_id", "objective"),
    ("instance", "heartbeat"): ("activity",),
    ("instance", "stopped"): (),
    ("instance", "wait_started"): ("until", "selector"),
    ("instance", "wait_ended"): (),
    ("subscription", "created"): (
        "owner_type",
        "owner_id",
        "actor_type",
        "actor_id",
        "retained_deliveries",
    ),
    ("request", "created"): (
        "owner_type",
        "owner_id",
        "actor_type",
        "actor_id",
        "retained_deliveries",
    ),
    ("subscription", "paused"): ("actor_type", "actor_id"),
    ("subscription", "resumed"): ("actor_type", "actor_id"),
    ("subscription", "cancelled"): ("actor_type", "actor_id", "reason"),
    ("request", "cancelled"): ("actor_type", "actor_id", "reason"),
    ("offer", "created"): ("owner_type", "owner_id", "actor_type", "actor_id"),
    ("offer", "paused"): ("actor_type", "actor_id"),
    ("offer", "resumed"): ("actor_type", "actor_id"),
    ("offer", "cancelled"): ("actor_type", "actor_id"),
    ("message", "published"): (
        "topic",
        "schema_id",
        "delivery_count",
        "retained",
        "advertised",
    ),
    ("delivery", "expired"): ("reason", "subscription_id"),
    ("delivery", "lease_timed_out"): ("previous_lease_until", "attempt"),
    ("delivery", "dead_lettered"): ("attempts",),
    ("delivery", "leased"): ("attempt", "lease_until"),
    ("delivery", "acked"): (
        "subscription_id",
        "actor_type",
        "actor_id",
    ),
}

MATCH_FIELDS = (
    "subscription_id",
    "subscription_kind",
    "subscription_owner_type",
    "subscription_owner_id",
    "subscriber_agent_id",
    "subscription_purpose",
    "subscription_topic_filter",
    "subscription_schema_id",
    "subscription_expires_at",
    "correlation_id",
    "offer_id",
    "offer_owner_type",
    "offer_owner_id",
    "provider_agent_id",
    "offer_purpose",
    "offer_topic_filter",
    "offer_schema_id",
    "offer_expires_at",
    "live_instance_ids",
    "candidate_instances",
    "provider_live",
    "availability",
    "facts",
    "reason",
)

UNMET_FIELDS = (
    "subscription_id",
    "kind",
    "owner_type",
    "owner_id",
    "subscriber_agent_id",
    "purpose",
    "topic_filter",
    "schema_id",
    "expires_at",
    "correlation_id",
    "classification",
    "reason",
)

CANDIDATE_FIELDS = (
    "offer_id",
    "provider_agent_id",
    "offer_purpose",
    "offer_topic_filter",
    "offer_schema_id",
    "facts",
    "mismatch_reasons",
)

NEXT_ITEM_FIELDS = (
    "kind",
    "entity_id",
    "reason",
    "command",
    "requester_agent_id",
    "request_purpose",
    "request_topic_filter",
    "request_schema_id",
    "request_expires_at",
    "request_correlation_id",
    "offer_id",
    "provider_agent_id",
    "offer_purpose",
    "offer_topic_filter",
    "offer_schema_id",
    "provider_live",
    "live_instance_ids",
    "facts",
    "state",
)

ACK_FIELDS = ("delivery_id", "state", "acked_at", "deduplicated")


def partition_context(partition: Partition) -> dict:
    display_name = partition.path.name or str(partition.path)
    return {
        "partition_id": partition.partition_id,
        "path": str(partition.path),
        "source": partition.source,
        "display_name": display_name,
    }


def _select(record: Mapping, fields: Sequence[str]) -> dict:
    return {field: record[field] for field in fields if field in record}


def page(
    records: Sequence,
    limit: int,
    projector: Callable[[Any], Any],
) -> dict:
    selected = records[:limit]
    return {
        "items": [projector(record) for record in selected],
        "page": {
            "limit": limit,
            "returned": len(selected),
            "total": len(records),
            "truncated": len(records) > limit,
        },
    }


def project_agent(record: Mapping) -> dict:
    return _select(record, AGENT_FIELDS)


def project_instance(record: Mapping) -> dict:
    return _select(record, INSTANCE_FIELDS)


def project_subscription(record: Mapping) -> dict:
    return _select(record, SUBSCRIPTION_FIELDS)


def project_offer(record: Mapping) -> dict:
    return _select(record, OFFER_FIELDS)


def project_message(record: Mapping, *, include_payload: bool = False) -> dict:
    result = _select(record, MESSAGE_FIELDS)
    if include_payload and "payload" in record:
        result["payload"] = record["payload"]
    return result


def project_delivery(
    record: Mapping,
    *,
    ack_instance: str | None = None,
    include_payload: bool = False,
) -> dict:
    result = _select(record, DELIVERY_FIELDS)
    if include_payload and "payload" in record:
        result["payload"] = record["payload"]
    if ack_instance is not None and result.get("state") == "leased":
        result["next"] = {
            "action": "ack",
            "command": f"purposebus ack {result['delivery_id']} --instance {ack_instance}",
            "reason": "acknowledge this Delivery after its payload has been handled",
            "context": "reuse the same Partition and state configuration as this poll",
        }
    return result


def project_event(record: Mapping) -> dict:
    result = _select(record, EVENT_FIELDS)
    detail_fields = EVENT_DETAIL_FIELDS.get(
        (record.get("entity_type"), record.get("event_type")), ()
    )
    result["details"] = _select(record.get("details", {}), detail_fields)
    return result


def _project_match(record: Mapping, candidate_limit: int) -> dict:
    result = _select(record, MATCH_FIELDS)
    if "candidate_instances" in result:
        result["candidate_instances"] = page(
            result["candidate_instances"],
            candidate_limit,
            lambda item: _select(
                item, ("instance_id", "liveness", "liveness_reason", "activity")
            ),
        )
    if "live_instance_ids" in result:
        result["live_instance_ids"] = page(
            result["live_instance_ids"], candidate_limit, lambda item: item
        )
    if "facts" in result:
        result["facts"] = _select(
            result["facts"], ("topic_filters_overlap", "schemas_compatible")
        )
    return result


def _project_unmet(record: Mapping, candidate_limit: int) -> dict:
    result = _select(record, UNMET_FIELDS)
    result["candidates"] = page(
        record.get("candidates", []), candidate_limit, _project_candidate
    )
    return result


def _project_candidate(record: Mapping) -> dict:
    result = _select(record, CANDIDATE_FIELDS)
    if "facts" in result:
        result["facts"] = _select(
            result["facts"], ("topic_filters_overlap", "schemas_compatible")
        )
    return result


def _project_next_item(record: Mapping, provider_limit: int) -> dict:
    result = _select(record, NEXT_ITEM_FIELDS)
    if "facts" in result:
        result["facts"] = _select(
            result["facts"], ("topic_filters_overlap", "schemas_compatible")
        )
    if "live_instance_ids" in result:
        result["live_instance_ids"] = page(
            result["live_instance_ids"], provider_limit, lambda item: item
        )
    return result


def _project_status(result: Mapping, limit: int) -> dict:
    storage = result["storage"]
    return {
        "storage": {
            "health": "ok",
            "state_schema_version": storage["schema_version"],
            "max_delivery_attempts": storage["max_delivery_attempts"],
            "max_event_rows": storage["max_event_rows"],
            "event_rows": storage["event_rows"],
            "events_pruned": storage["events_pruned"],
        },
        "counts": _select(
            result["counts"],
            (
                "agents",
                "instances",
                "live_instances",
                "active_subscriptions",
                "active_offers",
                "pending_deliveries",
            ),
        ),
        "instances": page(result["instances"], limit, project_instance),
    }


def project_result(args, result):
    limit = getattr(args, "limit", DEFAULT_COLLECTION_LIMIT)

    if args.command == "help":
        return _select(result, ("topic", "text"))
    if args.command == "init":
        return {
            "created": bool(result["created"]),
            "metadata": _select(result["metadata"], ("schema_version", "created_at")),
        }
    if args.command == "agent":
        if args.agent_command == "list":
            return page(result, limit, project_agent)
        return project_agent(result)
    if args.command == "instance":
        if args.instance_command == "list":
            return page(result, limit, project_instance)
        return project_instance(result)
    if args.command == "subscription":
        if args.subscription_command == "list":
            return page(result, limit, project_subscription)
        return project_subscription(result)
    if args.command == "offer":
        if args.offer_command == "list":
            return page(result, limit, project_offer)
        return project_offer(result)
    if args.command == "request":
        if args.request_command == "list":
            return page(result, limit, project_subscription)
        if args.request_command == "create" and "request" in result:
            return {
                "request": project_subscription(result["request"]),
                "deliveries": page(
                    result["deliveries"],
                    1,
                    lambda item: project_delivery(
                        item,
                        ack_instance=result["request"]["owner_id"],
                        include_payload=True,
                    ),
                ),
            }
        return project_subscription(result)
    if args.command == "publish":
        return project_message(result)
    if args.command == "message":
        if args.message_command == "list":
            return page(result, limit, project_message)
        return project_message(result, include_payload=args.include_payload)
    if args.command == "poll":
        return {
            "deliveries": page(
                result,
                args.limit,
                lambda item: project_delivery(
                    item, ack_instance=args.instance, include_payload=True
                ),
            )
        }
    if args.command == "ack":
        return _select(result, ACK_FIELDS)
    if args.command == "match":
        candidate_limit = args.candidate_limit
        matches = page(
            result["matches"],
            limit,
            lambda item: _project_match(item, candidate_limit),
        )
        unmet = page(
            result["unmet"],
            limit,
            lambda item: _project_unmet(item, candidate_limit),
        )
        return {
            "summary": {
                "matches": len(result["matches"]),
                "unavailable_matches": sum(
                    1 for item in result["matches"] if not item["provider_live"]
                ),
                "unmet": len(result["unmet"]),
            },
            "matches": matches,
            "unmet": unmet,
        }
    if args.command == "status":
        return _project_status(result, limit)
    if args.command == "next":
        return {
            "instance": project_instance(result["instance"]),
            "items": page(
                result["items"], limit, lambda item: _project_next_item(item, limit)
            ),
            "warnings": page(
                result["warnings"], limit, lambda item: _project_next_item(item, limit)
            ),
        }
    if args.command == "events":
        return page(result, args.limit, project_event)
    if args.command == "delivery" and args.delivery_command == "list":
        return page(result, limit, project_delivery)
    raise ValueError(f"no public projection for command: {args.command}")


def _partition_lines(document: Mapping) -> list[str]:
    partition = document["partition"]
    actor = document["actor"]
    actor_text = "operator" if actor is None else f"{actor['type']} {actor['id']}"
    return [
        f"Partition: {partition['display_name']} ({partition['partition_id']})",
        f"Source: {partition['path']} [{partition['source']}]",
        f"Actor: {actor_text}",
    ]


def _page_header(label: str, value: Mapping) -> str:
    metadata = value["page"]
    suffix = " (truncated)" if metadata["truncated"] else ""
    return f"{label}: {metadata['returned']} of {metadata['total']}{suffix}"


def _resource_line(kind: str, item: Mapping) -> str:
    if kind == "agent":
        capabilities = ",".join(item.get("capabilities", [])) or "-"
        return (
            f"- {item['agent_id']} kind={item['kind']} capabilities={capabilities}: "
            f"{item['description']}"
        )
    if kind == "instance":
        return (
            f"- {item['instance_id']} agent={item['agent_id']} "
            f"lifecycle={item['lifecycle_state']} activity={item['activity']} "
            f"liveness={item['liveness']} reason={item['liveness_reason']} "
            f"lease_expires_at={item.get('lease_expires_at', '-')}: {item['objective']}"
        )
    if kind in {"subscription", "request"}:
        return (
            f"- {item['subscription_id']} owner={item['owner_type']}:{item['owner_id']} "
            f"kind={item['kind']} state={item['effective_state']} durable={item['durable']} "
            f"topic={item['topic_filter']} schema={item.get('schema_id') or '-'} "
            f"expires_at={item.get('expires_at') or '-'} "
            f"correlation={item.get('correlation_id') or '-'}: {item['purpose']}"
        )
    if kind == "offer":
        return (
            f"- {item['offer_id']} owner={item['owner_type']}:{item['owner_id']} "
            f"state={item['effective_state']} topic={item['topic_filter']} "
            f"schema={item.get('schema_id') or '-'} "
            f"expires_at={item.get('expires_at') or '-'}: {item['purpose']}"
        )
    if kind == "message":
        return (
            f"- {item['message_id']} producer={item['producer_instance_id']} "
            f"topic={item['topic']} schema={item.get('schema_id') or '-'} "
            f"payload={item['payload_kind']} retained={item.get('retained', False)} "
            f"advertised={item.get('advertised', False)} "
            f"correlation={item.get('correlation_id') or '-'}: {item['purpose']}"
        )
    if kind == "delivery":
        return (
            f"- {item['delivery_id']} state={item.get('effective_state', item['state'])} "
            f"attempt={item['attempt']} subscription={item['subscription_id']} "
            f"leased_by={item.get('leased_by_instance_id') or '-'} "
            f"lease_until={item.get('lease_until') or '-'} "
            f"topic={item.get('topic', '-')} schema={item.get('schema_id') or '-'} "
            f"correlation={item.get('correlation_id') or '-'}"
        )
    if kind == "event":
        return (
            f"- {item['sequence']} {item['event_type']} "
            f"{item['entity_type']}={item['entity_id']} at={item['at']} "
            f"actor={item.get('actor_instance_id') or 'operator'} "
            f"details={json.dumps(item.get('details', {}), ensure_ascii=False, sort_keys=True)}"
        )
    return "- unsupported resource"


def render_human(document: Mapping) -> list[str]:
    schema = document["schema"]
    result = document["result"]
    lines = _partition_lines(document)

    resource_lists = {
        "purposebus.agent-list.v2": ("Agents", "agent"),
        "purposebus.instance-list.v2": ("Instances", "instance"),
        "purposebus.subscription-list.v2": ("Subscriptions", "subscription"),
        "purposebus.offer-list.v2": ("Offers", "offer"),
        "purposebus.request-list.v2": ("Requests", "request"),
        "purposebus.message-list.v2": ("Messages", "message"),
        "purposebus.delivery-list.v2": ("Deliveries", "delivery"),
        "purposebus.events.v2": ("Events", "event"),
    }
    if schema in resource_lists:
        label, kind = resource_lists[schema]
        lines.append(_page_header(label, result))
        lines.extend(_resource_line(kind, item) for item in result["items"])
        return lines

    if schema == "purposebus.status.v2":
        lines.append(
            f"Storage: {result['storage']['health']} "
            f"(state schema {result['storage']['state_schema_version']})"
        )
        lines.append(
            "Counts: "
            + ", ".join(f"{key}={value}" for key, value in result["counts"].items())
        )
        lines.append(_page_header("Instances", result["instances"]))
        lines.extend(_resource_line("instance", item) for item in result["instances"]["items"])
        return lines

    if schema == "purposebus.match.v2":
        lines.append(_page_header("Matches", result["matches"]))
        for item in result["matches"]["items"]:
            lines.append(
                f"- subscription={item['subscription_id']} offer={item['offer_id']} "
                f"availability={item['availability']}: {item['reason']}"
            )
            lines.append(
                f"  Need: topic={item['subscription_topic_filter']} "
                f"schema={item.get('subscription_schema_id') or '-'} "
                f"purpose={item['subscription_purpose']}"
            )
            lines.append(
                f"  Offer: topic={item['offer_topic_filter']} "
                f"schema={item.get('offer_schema_id') or '-'} "
                f"purpose={item['offer_purpose']}"
            )
        lines.append(_page_header("Unmet", result["unmet"]))
        for item in result["unmet"]["items"]:
            lines.append(
                f"- subscription={item['subscription_id']} "
                f"classification={item['classification']}: {item['reason']}"
            )
            for candidate in item["candidates"]["items"]:
                reasons = ",".join(candidate["mismatch_reasons"]) or "-"
                lines.append(
                    f"  Candidate: offer={candidate['offer_id']} "
                    f"mismatch={reasons} purpose={candidate['offer_purpose']}"
                )
        return lines

    if schema == "purposebus.next.v2":
        lines.append(_resource_line("instance", result["instance"]))
        lines.append(_page_header("Next actions", result["items"]))
        for item in result["items"]["items"]:
            lines.append(f"- {item['kind']} {item['entity_id']}: {item['reason']}")
            if item.get("command"):
                lines.append(f"  Command: {item['command']}")
        for warning in result["warnings"]["items"]:
            lines.append(
                f"Warning: {warning['kind']} {warning['entity_id']} "
                f"state={warning.get('state', '-')} reason={warning['reason']}"
            )
        return lines

    if schema == "purposebus.poll.v2":
        deliveries = result["deliveries"]
        lines.append(_page_header("Leased Deliveries", deliveries))
        for item in deliveries["items"]:
            lines.append(_resource_line("delivery", item))
            if "payload" in item:
                lines.append(
                    "  Payload: "
                    + json.dumps(item["payload"], ensure_ascii=False, sort_keys=True)
                )
            if item.get("next"):
                lines.append(f"  Next: {item['next']['command']}")
        return lines

    if schema == "purposebus.init.v2":
        state = "created" if result["created"] else "already initialized"
        lines.append(f"State: {state}; schema {result['metadata']['schema_version']}")
        return lines

    if schema == "purposebus.ack.v2":
        lines.append(
            f"Delivery {result['delivery_id']}: {result['state']} at {result['acked_at']}"
        )
        return lines

    single_resources = {
        "agent": "agent",
        "instance": "instance",
        "subscription": "subscription",
        "offer": "offer",
        "request": "request",
        "message": "message",
    }
    for prefix, kind in single_resources.items():
        if schema.startswith(f"purposebus.{prefix}-"):
            if prefix == "request" and "request" in result:
                lines.append(_resource_line("request", result["request"]))
                lines.append(_page_header("Leased Deliveries", result["deliveries"]))
                for delivery in result["deliveries"]["items"]:
                    lines.append(_resource_line("delivery", delivery))
                    if "payload" in delivery:
                        lines.append(
                            "  Payload: "
                            + json.dumps(
                                delivery["payload"], ensure_ascii=False, sort_keys=True
                            )
                        )
                    if delivery.get("next"):
                        lines.append(f"  Next: {delivery['next']['command']}")
                return lines
            lines.append(_resource_line(kind, result))
            if kind == "message" and "payload" in result:
                lines.append(
                    "Payload: "
                    + json.dumps(result["payload"], ensure_ascii=False, sort_keys=True)
                )
            return lines

    if schema == "purposebus.publish.v2":
        lines.append(_resource_line("message", result))
        lines.append(
            f"Deliveries created: {result['delivery_count']}; "
            f"deduplicated={str(result['deduplicated']).lower()}"
        )
        return lines

    raise ValueError(f"no human renderer for response schema: {schema}")
