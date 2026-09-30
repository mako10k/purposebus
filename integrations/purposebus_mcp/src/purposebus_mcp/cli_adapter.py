from __future__ import annotations

import json
import math
import os
import re
import shutil
import subprocess
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from .config import PartitionBinding


SUPPORTED_PURPOSEBUS_VERSION = "1.0.0"
_SAFE_ENVIRONMENT_KEYS = (
    "HOME",
    "LANG",
    "LC_ALL",
    "LC_CTYPE",
    "PURPOSEBUS_STATE_DIR",
    "XDG_STATE_HOME",
)
_IDENTIFIER = re.compile(r"^[A-Za-z][A-Za-z0-9._:-]{0,127}$")


class PurposeBusGatewayError(RuntimeError):
    """Base error for a failed public-CLI gateway operation."""


class PurposeBusProtocolError(PurposeBusGatewayError):
    """The CLI result did not satisfy the pinned public response contract."""


@dataclass(frozen=True)
class PurposeBusCliError(PurposeBusGatewayError):
    error: str
    message: str
    hint: str | None
    exit_code: int

    def __str__(self) -> str:
        detail = f"{self.error}: {self.message}"
        return f"{detail} ({self.hint})" if self.hint else detail


def _default_command() -> tuple[str, ...]:
    executable = shutil.which("purposebus")
    if executable is None:
        raise PurposeBusGatewayError("purposebus executable was not found on PATH")
    return (str(Path(executable).resolve()),)


def _clean_environment(source: Mapping[str, str]) -> dict[str, str]:
    return {key: source[key] for key in _SAFE_ENVIRONMENT_KEYS if source.get(key)}


def _json_object(text: str, stream: str) -> dict[str, Any]:
    try:
        value = json.loads(text)
    except json.JSONDecodeError as exc:
        raise PurposeBusProtocolError(f"{stream} did not contain one JSON document") from exc
    if not isinstance(value, dict):
        raise PurposeBusProtocolError(f"{stream} JSON document was not an object")
    return value


def _identifier(value: str, label: str) -> str:
    if not _IDENTIFIER.fullmatch(value):
        raise PurposeBusGatewayError(f"invalid {label}")
    return value


class PurposeBusCliGateway:
    """Invoke only the allowlisted, read-only PurposeBus public CLI surface."""

    def __init__(
        self,
        bindings: Mapping[str, PartitionBinding],
        *,
        command: Sequence[str] | None = None,
        timeout_seconds: float = 10.0,
        environment: Mapping[str, str] | None = None,
    ) -> None:
        if not bindings:
            raise PurposeBusGatewayError("at least one partition binding is required")
        if not math.isfinite(timeout_seconds) or timeout_seconds <= 0:
            raise PurposeBusGatewayError("timeout must be a finite value greater than zero")
        effective_command = tuple(command) if command is not None else _default_command()
        if not effective_command:
            raise PurposeBusGatewayError("purposebus command must not be empty")
        self._bindings = dict(bindings)
        self._command = effective_command
        self._timeout_seconds = timeout_seconds
        self._environment = _clean_environment(environment or os.environ)

    def check_version(self) -> None:
        completed = self._run_process(("--version",))
        expected = f"purposebus {SUPPORTED_PURPOSEBUS_VERSION}"
        if (
            completed.returncode != 0
            or completed.stdout.strip() != expected
            or completed.stderr
        ):
            raise PurposeBusProtocolError(
                f"unsupported PurposeBus CLI; expected exactly {expected!r}"
            )

    def status(self, alias: str, *, limit: int = 100) -> dict[str, Any]:
        return self._invoke(alias, "purposebus.status.v2", ("status", "--limit", str(limit)))

    def list_agents(self, alias: str, *, limit: int = 100) -> dict[str, Any]:
        return self._invoke(
            alias, "purposebus.agent-list.v2", ("agent", "list", "--limit", str(limit))
        )

    def list_instances(self, alias: str, *, limit: int = 100) -> dict[str, Any]:
        return self._invoke(
            alias,
            "purposebus.instance-list.v2",
            ("instance", "list", "--limit", str(limit)),
        )

    def match(
        self, alias: str, *, limit: int = 100, candidate_limit: int = 25
    ) -> dict[str, Any]:
        return self._invoke(
            alias,
            "purposebus.match.v2",
            ("match", "--limit", str(limit), "--candidate-limit", str(candidate_limit)),
        )

    def next(self, alias: str, instance_id: str, *, limit: int = 100) -> dict[str, Any]:
        return self._invoke(
            alias,
            "purposebus.next.v2",
            ("next", "--instance", _identifier(instance_id, "Instance ID"), "--limit", str(limit)),
        )

    def get_request(self, alias: str, request_id: str) -> dict[str, Any]:
        return self._invoke(
            alias,
            "purposebus.request-show.v2",
            ("request", "show", _identifier(request_id, "Request ID")),
        )

    def _binding(self, alias: str) -> PartitionBinding:
        try:
            return self._bindings[alias]
        except KeyError as exc:
            raise PurposeBusGatewayError(f"unknown partition alias: {alias}") from exc

    def _invoke(
        self, alias: str, expected_schema: str, arguments: Sequence[str]
    ) -> dict[str, Any]:
        binding = self._binding(alias)
        completed = self._run_process(
            ("--partition", str(binding.path), "--format", "json", *arguments)
        )
        if completed.returncode != 0:
            document = _json_object(completed.stderr, "PurposeBus stderr")
            if document.get("schema") != "purposebus.error.v1":
                raise PurposeBusProtocolError("PurposeBus error used an unsupported schema")
            raise PurposeBusCliError(
                error=str(document.get("error", "unknown_error")),
                message=str(document.get("message", "PurposeBus command failed")),
                hint=(str(document["hint"]) if document.get("hint") is not None else None),
                exit_code=completed.returncode,
            )
        if completed.stderr:
            raise PurposeBusProtocolError("successful PurposeBus command wrote to stderr")
        document = _json_object(completed.stdout, "PurposeBus stdout")
        if document.get("schema") != expected_schema:
            raise PurposeBusProtocolError(
                f"PurposeBus returned {document.get('schema')!r}; expected {expected_schema!r}"
            )
        if set(document) != {"schema", "actor", "partition", "result"}:
            raise PurposeBusProtocolError("PurposeBus response has unsupported top-level fields")
        partition = document.get("partition")
        if not isinstance(partition, dict):
            raise PurposeBusProtocolError("PurposeBus response omitted partition context")
        if partition.get("path") != str(binding.path) or partition.get("source") != "explicit":
            raise PurposeBusProtocolError("PurposeBus response did not match the configured partition")
        return document

    def _run_process(self, arguments: Sequence[str]) -> subprocess.CompletedProcess[str]:
        try:
            return subprocess.run(
                [*self._command, *arguments],
                capture_output=True,
                check=False,
                env=self._environment,
                text=True,
                timeout=self._timeout_seconds,
            )
        except subprocess.TimeoutExpired as exc:
            raise PurposeBusGatewayError(
                f"PurposeBus CLI exceeded the {self._timeout_seconds:g}s timeout"
            ) from exc
        except OSError as exc:
            raise PurposeBusGatewayError(f"PurposeBus CLI could not be executed: {exc}") from exc
