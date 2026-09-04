from __future__ import annotations

import hashlib
import os
import subprocess
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class Partition:
    partition_id: str
    path: Path
    source: str
    state_root: Path
    directory: Path
    database: Path


def _git_root(cwd: Path) -> Path | None:
    environment = dict(os.environ)
    environment["GIT_OPTIONAL_LOCKS"] = "0"
    result = subprocess.run(
        ["git", "-C", str(cwd), "rev-parse", "--show-toplevel"],
        check=False,
        stdout=subprocess.PIPE,
        stderr=subprocess.DEVNULL,
        text=True,
        env=environment,
    )
    if result.returncode != 0:
        return None
    return Path(result.stdout.strip()).resolve()


def _state_root(override: str | None) -> Path:
    if override:
        return Path(override).expanduser().resolve()
    if os.environ.get("PURPOSEBUS_STATE_DIR"):
        return Path(os.environ["PURPOSEBUS_STATE_DIR"]).expanduser().resolve()
    if os.environ.get("XDG_STATE_HOME"):
        return Path(os.environ["XDG_STATE_HOME"]).expanduser().resolve() / "purposebus"
    return Path.home() / ".local" / "state" / "purposebus"


def resolve_partition(path_override: str | None = None, state_override: str | None = None) -> Partition:
    if path_override:
        path = Path(path_override).expanduser().resolve()
        source = "explicit"
    else:
        cwd = Path.cwd().resolve()
        git_root = _git_root(cwd)
        path = git_root or cwd
        source = "git_worktree" if git_root else "cwd"
    digest = hashlib.sha256(str(path).encode("utf-8")).hexdigest()
    partition_id = f"path-sha256:{digest}"
    state_root = _state_root(state_override)
    directory = state_root / "partitions" / digest
    return Partition(
        partition_id=partition_id,
        path=path,
        source=source,
        state_root=state_root,
        directory=directory,
        database=directory / "purposebus.sqlite3",
    )
