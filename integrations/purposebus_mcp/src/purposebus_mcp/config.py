from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable


_ALIAS = re.compile(r"^[a-z][a-z0-9_-]{0,63}$")


class ConfigurationError(ValueError):
    """The operator supplied an invalid MCP server configuration."""


@dataclass(frozen=True)
class PartitionBinding:
    alias: str
    path: Path

    @classmethod
    def parse(cls, value: str) -> "PartitionBinding":
        alias, separator, raw_path = value.partition("=")
        if not separator or not alias or not raw_path:
            raise ConfigurationError("partition binding must be ALIAS=/absolute/path")
        if not _ALIAS.fullmatch(alias):
            raise ConfigurationError(
                "partition alias must start with a lowercase letter and contain only "
                "lowercase letters, digits, '_' or '-'"
            )
        path = Path(raw_path)
        if not path.is_absolute():
            raise ConfigurationError("partition path must be absolute")
        try:
            resolved = path.resolve(strict=True)
        except OSError as exc:
            raise ConfigurationError(f"partition path cannot be resolved: {path}") from exc
        if not resolved.is_dir():
            raise ConfigurationError(f"partition path is not a directory: {resolved}")
        return cls(alias=alias, path=resolved)


def parse_bindings(values: Iterable[str]) -> dict[str, PartitionBinding]:
    bindings: dict[str, PartitionBinding] = {}
    paths: set[Path] = set()
    for value in values:
        binding = PartitionBinding.parse(value)
        if binding.alias in bindings:
            raise ConfigurationError(f"duplicate partition alias: {binding.alias}")
        if binding.path in paths:
            raise ConfigurationError(f"duplicate partition path: {binding.path}")
        bindings[binding.alias] = binding
        paths.add(binding.path)
    if not bindings:
        raise ConfigurationError("at least one --partition ALIAS=/absolute/path is required")
    return bindings
