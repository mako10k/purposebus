from __future__ import annotations

import hashlib
import json
import os
import re
import socket
import uuid
from datetime import datetime, timedelta, timezone
from pathlib import Path

from .errors import InvalidInput


UTC = timezone.utc
MAX_INLINE_BYTES = 64 * 1024
_DURATION_RE = re.compile(r"^(?P<value>[0-9]+(?:\.[0-9]+)?)(?P<unit>ms|s|m|h)?$")
_IDENTIFIER_RE = re.compile(r"^[A-Za-z][A-Za-z0-9._:-]{0,127}$")


def now_utc() -> datetime:
    return datetime.now(UTC)


def parse_time(value: str | None) -> datetime:
    if value is None:
        return now_utc()
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as exc:
        raise InvalidInput(f"invalid ISO 8601 time: {value}") from exc
    if parsed.tzinfo is None:
        raise InvalidInput("--at requires an explicit timezone")
    return parsed.astimezone(UTC)


def iso(value: datetime) -> str:
    return value.astimezone(UTC).isoformat(timespec="milliseconds").replace("+00:00", "Z")


def add_seconds(value: datetime, seconds: float) -> datetime:
    return value + timedelta(seconds=seconds)


def parse_duration(value: str | int | float) -> float:
    if isinstance(value, (int, float)):
        seconds = float(value)
    else:
        match = _DURATION_RE.fullmatch(value.strip())
        if not match:
            raise InvalidInput(f"invalid duration: {value}", hint="use forms such as 500ms, 5s, 2m, or 1h")
        amount = float(match.group("value"))
        unit = match.group("unit") or "s"
        seconds = amount * {"ms": 0.001, "s": 1, "m": 60, "h": 3600}[unit]
    if seconds < 0:
        raise InvalidInput("duration must not be negative")
    return seconds


def new_id(prefix: str) -> str:
    return f"{prefix}_{uuid.uuid4().hex}"


def canonical_json(value) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def command_digest(value) -> str:
    return "sha256:" + hashlib.sha256(canonical_json(value).encode("utf-8")).hexdigest()


def json_text(value) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, indent=2)


def parse_json_payload(value: str):
    try:
        parsed = json.loads(value)
    except json.JSONDecodeError as exc:
        raise InvalidInput(f"invalid JSON payload: {exc.msg}") from exc
    return canonical_json(parsed)


def validate_inline(value: str) -> None:
    size = len(value.encode("utf-8"))
    if size > MAX_INLINE_BYTES:
        raise InvalidInput(f"inline payload is {size} bytes; MVP limit is {MAX_INLINE_BYTES} bytes")


def _topic_parts(value: str) -> list[str]:
    if not value or value.startswith("/") or value.endswith("/") or "//" in value:
        raise InvalidInput("topic must contain non-empty slash-separated levels")
    return value.split("/")


def validate_topic(value: str) -> str:
    parts = _topic_parts(value)
    if any(part in {"+", "#"} or "+" in part or "#" in part for part in parts):
        raise InvalidInput("publication topic must not contain wildcards")
    return value


def validate_filter(value: str) -> str:
    parts = _topic_parts(value)
    for index, part in enumerate(parts):
        if ("+" in part and part != "+") or ("#" in part and part != "#"):
            raise InvalidInput("topic wildcards must occupy a complete level")
        if part == "#" and index != len(parts) - 1:
            raise InvalidInput("multi-level # wildcard must be the final level")
    return value


def topic_matches(topic_filter: str, topic: str) -> bool:
    filters = topic_filter.split("/")
    topics = topic.split("/")
    index = 0
    while index < len(filters):
        part = filters[index]
        if part == "#":
            return True
        if index >= len(topics):
            return False
        if part != "+" and part != topics[index]:
            return False
        index += 1
    return index == len(topics)


def filters_overlap(left: str, right: str) -> bool:
    a = left.split("/")
    b = right.split("/")
    index = 0
    while True:
        if index == len(a) and index == len(b):
            return True
        if index < len(a) and a[index] == "#":
            return True
        if index < len(b) and b[index] == "#":
            return True
        if index == len(a) or index == len(b):
            return False
        if a[index] != "+" and b[index] != "+" and a[index] != b[index]:
            return False
        index += 1


def schema_compatible(left: str | None, right: str | None) -> bool:
    return left is None or right is None or left == right


def current_boot_id() -> str | None:
    try:
        return Path("/proc/sys/kernel/random/boot_id").read_text(encoding="ascii").strip()
    except OSError:
        return None


def process_start_identity(pid: int) -> str | None:
    try:
        raw = Path(f"/proc/{pid}/stat").read_text(encoding="utf-8")
    except OSError:
        return None
    end = raw.rfind(")")
    if end < 0:
        return None
    fields_after_command = raw[end + 2 :].split()
    if len(fields_after_command) <= 19:
        return None
    return fields_after_command[19]


def process_observation(pid: int | None) -> dict:
    if pid is None:
        return {"host": socket.gethostname(), "boot_id": current_boot_id(), "pid": None, "process_start": None}
    if pid <= 0:
        raise InvalidInput("PID must be a positive integer")
    return {
        "host": socket.gethostname(),
        "boot_id": current_boot_id(),
        "pid": pid,
        "process_start": process_start_identity(pid),
    }


def process_matches(host: str | None, boot_id: str | None, pid: int | None, process_start: str | None) -> tuple[bool | None, str]:
    if pid is None:
        return None, "no_pid"
    if host != socket.gethostname():
        return None, "different_host"
    current_boot = current_boot_id()
    if boot_id is None or current_boot is None:
        return None, "boot_identity_unavailable"
    if boot_id != current_boot:
        return False, "boot_identity_changed"
    observed_start = process_start_identity(pid)
    if observed_start is None:
        return False, "process_absent"
    if process_start is None:
        return None, "process_start_unavailable"
    if observed_start != process_start:
        return False, "pid_reused"
    return True, "process_identity_matches"


def capabilities(value: str | None) -> list[str]:
    if not value:
        return []
    return sorted({part.strip() for part in value.split(",") if part.strip()})


def validate_identifier(value: str, label: str = "identifier") -> str:
    if not _IDENTIFIER_RE.fullmatch(value):
        raise InvalidInput(
            f"invalid {label}: {value!r}",
            hint="use 1-128 characters beginning with a letter, followed by letters, digits, dot, underscore, colon, or hyphen",
        )
    return value


def expiry(now: datetime, duration: str | None) -> str | None:
    if duration is None:
        return None
    return iso(add_seconds(now, parse_duration(duration)))


def ensure_private_file(path) -> None:
    try:
        os.chmod(path, 0o600)
    except FileNotFoundError:
        pass
