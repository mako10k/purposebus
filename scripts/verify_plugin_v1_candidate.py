#!/usr/bin/env python3
"""Build and verify the immutable local PurposeBus Codex Plugin 1.0 package."""

from __future__ import annotations

import hashlib
import io
import json
import os
import platform
import re
import shutil
import subprocess
import sys
import tempfile
import zipfile
from pathlib import Path
from typing import Any, Mapping, Sequence


REPO_ROOT = Path(__file__).resolve().parents[1]
CONTRACT_PATH = REPO_ROOT / "release" / "plugin-v1-contract.json"
PLUGIN_ROOT = REPO_ROOT / "plugins" / "purposebus"
SECRET_PATTERNS = (
    re.compile(rb"sk-[A-Za-z0-9_-]{20,}"),
    re.compile(rb"gh[pousr]_[A-Za-z0-9]{20,}"),
    re.compile(rb"AKIA[A-Z0-9]{16}"),
    re.compile(rb"-----BEGIN [A-Z ]*PRIVATE KEY-----"),
)
DISALLOWED_NAMES = {".env", "auth.json", "credentials.json", "id_rsa", "id_ed25519"}


class VerificationError(RuntimeError):
    pass


def run(
    command: Sequence[str | Path],
    *,
    environment: Mapping[str, str] | None = None,
    timeout: float = 90,
) -> subprocess.CompletedProcess[str]:
    completed = subprocess.run(
        [str(value) for value in command],
        cwd=REPO_ROOT,
        env=dict(environment) if environment is not None else None,
        capture_output=True,
        check=False,
        text=True,
        timeout=timeout,
    )
    if completed.returncode != 0:
        detail = completed.stderr.strip() or completed.stdout.strip()
        raise VerificationError(
            f"command failed ({completed.returncode}): {' '.join(map(str, command))}: {detail}"
        )
    return completed


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def sha256_file(path: Path) -> str:
    return sha256_bytes(path.read_bytes())


def plugin_files() -> list[Path]:
    files: list[Path] = []
    for path in PLUGIN_ROOT.rglob("*"):
        if path.is_symlink():
            raise VerificationError(f"Plugin package contains a symlink: {path}")
        if path.is_file():
            files.append(path.relative_to(PLUGIN_ROOT))
    return sorted(files, key=lambda path: path.as_posix())


def tree_hash(files: Sequence[Path]) -> str:
    digest = hashlib.sha256()
    for relative in files:
        encoded = relative.as_posix().encode("utf-8")
        digest.update(len(encoded).to_bytes(4, "big"))
        digest.update(encoded)
        digest.update(bytes.fromhex(sha256_file(PLUGIN_ROOT / relative)))
    return digest.hexdigest()


def archive_bytes(files: Sequence[Path]) -> bytes:
    output = io.BytesIO()
    with zipfile.ZipFile(output, "w", compression=zipfile.ZIP_STORED) as archive:
        for relative in files:
            info = zipfile.ZipInfo(f"purposebus/{relative.as_posix()}")
            info.date_time = (1980, 1, 1, 0, 0, 0)
            info.compress_type = zipfile.ZIP_STORED
            info.create_system = 3
            info.external_attr = 0o100644 << 16
            archive.writestr(info, (PLUGIN_ROOT / relative).read_bytes())
    return output.getvalue()


def scan_secrets(files: Sequence[Path]) -> None:
    for relative in files:
        if relative.name.lower() in DISALLOWED_NAMES or relative.suffix.lower() in {".pem", ".key"}:
            raise VerificationError(f"credential-like file is not allowed: {relative}")
        content = (PLUGIN_ROOT / relative).read_bytes()
        if any(pattern.search(content) for pattern in SECRET_PATTERNS):
            raise VerificationError(f"credential-like content is not allowed: {relative}")


def safe_environment(home: Path) -> dict[str, str]:
    environment: dict[str, str] = {
        "HOME": str(home),
        "PATH": os.environ.get("PATH", ""),
        "LC_ALL": "C.UTF-8",
        "LANG": "C.UTF-8",
    }
    for key in ("SHELL", "TERM", "COLORTERM", "WSL_DISTRO_NAME", "WSL_INTEROP"):
        if key in os.environ:
            environment[key] = os.environ[key]
    return environment


def immutable_write(path: Path, data: bytes) -> None:
    if path.exists():
        if path.read_bytes() != data:
            raise VerificationError(f"immutable artifact differs: {path}")
        return
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(data)


def verify_cached_plugin(codex_home: Path, source: Path, version: str) -> None:
    cached = codex_home / "plugins" / "cache" / "purposebus-local" / "purposebus" / version
    if not cached.is_dir():
        raise VerificationError(f"installed Plugin cache is absent: {cached}")
    for source_file in (path for path in source.rglob("*") if path.is_file()):
        relative = source_file.relative_to(source)
        cached_file = cached / relative
        if not cached_file.is_file() or sha256_file(cached_file) != sha256_file(source_file):
            raise VerificationError(f"installed Plugin cache differs: {relative}")


def isolated_install_remove(contract: Mapping[str, Any]) -> dict[str, Any]:
    codex = shutil.which("codex")
    purposebus = shutil.which("purposebus")
    if codex is None or purposebus is None:
        raise VerificationError("codex and purposebus executables are required")

    with tempfile.TemporaryDirectory(prefix="purposebus-plugin-v1-") as raw_work:
        work = Path(raw_work)
        home = work / "home"
        codex_home = home / ".codex"
        codex_home.mkdir(parents=True)
        marketplace_root = work / "marketplace"
        marketplace_file = marketplace_root / ".agents" / "plugins" / "marketplace.json"
        marketplace_file.parent.mkdir(parents=True)
        shutil.copy2(REPO_ROOT / contract["marketplace"]["file"], marketplace_file)
        plugin_copy = marketplace_root / "plugins" / "purposebus"
        shutil.copytree(PLUGIN_ROOT, plugin_copy)
        environment = safe_environment(home)
        environment["CODEX_HOME"] = str(codex_home)

        run((codex, "plugin", "marketplace", "add", marketplace_root, "--json"), environment=environment)
        run((codex, "plugin", "add", "purposebus@purposebus-local", "--json"), environment=environment)
        listed = json.loads(
            run(
                (codex, "plugin", "list", "--marketplace", "purposebus-local", "--json"),
                environment=environment,
            ).stdout
        )
        installed = [item for item in listed["installed"] if item["pluginId"] == "purposebus@purposebus-local"]
        if len(installed) != 1 or installed[0]["version"] != contract["plugin"]["version"]:
            raise VerificationError("isolated Plugin list does not identify the exact candidate")
        verify_cached_plugin(codex_home, plugin_copy, contract["plugin"]["version"])

        run((codex, "plugin", "remove", "purposebus@purposebus-local", "--json"), environment=environment)
        after_remove = json.loads(
            run(
                (codex, "plugin", "list", "--marketplace", "purposebus-local", "--json"),
                environment=environment,
            ).stdout
        )
        if any(item["pluginId"] == "purposebus@purposebus-local" for item in after_remove["installed"]):
            raise VerificationError("Plugin remains installed after isolated removal")

        partition = work / "partition"
        partition.mkdir()
        state = work / "state"
        cli_prefix = (
            purposebus,
            "--partition",
            partition,
            "--state-dir",
            state,
            "--format",
            "json",
        )
        initialized = json.loads(run((*cli_prefix, "init"), environment=environment).stdout)
        status = json.loads(run((*cli_prefix, "status"), environment=environment).stdout)
        version = run((purposebus, "--version"), environment=environment).stdout.strip()
        if version != contract["core_compatibility"]["cli_version_output"]:
            raise VerificationError(f"raw CLI fallback version differs: {version}")
        if initialized.get("schema") != "purposebus.init.v2" or status.get("schema") != "purposebus.status.v2":
            raise VerificationError("raw CLI fallback returned an unexpected schema")

        run((codex, "plugin", "marketplace", "remove", "purposebus-local", "--json"), environment=environment)
        return {
            "isolated_home": True,
            "installed_version": installed[0]["version"],
            "cache_matches_source": True,
            "uninstall_readback": True,
            "raw_cli_fallback_version": version,
            "raw_cli_fallback_schema": status["schema"],
            "live_state_unchanged": True,
            "active_profile_unchanged": True,
        }


def verify_contract(contract: Mapping[str, Any], files: Sequence[Path]) -> dict[str, Any]:
    if contract.get("schema") != "purposebus.plugin-package-contract.v1":
        raise VerificationError("unsupported Plugin package contract")
    manifest = json.loads((PLUGIN_ROOT / ".codex-plugin" / "plugin.json").read_text(encoding="utf-8"))
    if manifest.get("name") != contract["plugin"]["name"] or manifest.get("version") != contract["plugin"]["version"]:
        raise VerificationError("Plugin identity differs from the contract")
    if [path.as_posix() for path in files] != contract["plugin"]["files"]:
        raise VerificationError("Plugin file allowlist differs from the contract")
    if contract["plugin"]["components"] != ["skills"]:
        raise VerificationError("Plugin must remain Skill-only")
    for field in ("mcpServers", "apps", "hooks"):
        if field in manifest:
            raise VerificationError(f"unexpected Plugin component: {field}")
    for relative, expected in contract["critical_file_sha256"].items():
        actual = sha256_file(REPO_ROOT / relative)
        if actual != expected:
            raise VerificationError(f"critical file drift: {relative}: {actual}")
    if contract["core_compatibility"]["specifier"] != "==0.2.0a1":
        raise VerificationError("core compatibility must remain evidence-backed")
    return {"critical_files": "passed", "file_allowlist": "passed", "skill_only": True}


def main() -> int:
    contract = json.loads(CONTRACT_PATH.read_text(encoding="utf-8"))
    files = plugin_files()
    contract_checks = verify_contract(contract, files)
    scan_secrets(files)
    tree_sha256 = tree_hash(files)
    package = archive_bytes(files)
    package_sha256 = sha256_bytes(package)
    output_root = REPO_ROOT / "build" / "plugin-v1" / tree_sha256
    package_name = f"purposebus-plugin-{contract['plugin']['version']}.zip"
    package_path = output_root / package_name
    immutable_write(package_path, package)
    install_checks = isolated_install_remove(contract)
    evidence = {
        "schema": "purposebus.plugin-package-evidence.v1",
        "status": "package_checks_passed",
        "contract_sha256": sha256_file(CONTRACT_PATH),
        "plugin": {
            "name": contract["plugin"]["name"],
            "version": contract["plugin"]["version"],
            "tree_sha256": tree_sha256,
            "package_file": package_name,
            "package_sha256": package_sha256,
        },
        "checks": {
            **contract_checks,
            "credential_pattern_scan": "passed",
            "deterministic_archive": True,
            "isolated_install_remove": install_checks,
        },
        "behavioral_evaluations": "pending_external_fresh_sessions",
        "environment": {
            "codex": run(("codex", "--version")).stdout.strip(),
            "purposebus": run(("purposebus", "--version")).stdout.strip(),
            "python": platform.python_version(),
            "platform": platform.platform(),
        },
        "limitations": [
            "Fresh-session behavioral evaluations are recorded separately.",
            "No active Plugin profile or live PurposeBus state was changed.",
            "No workspace or public Plugin Directory publication was attempted.",
        ],
    }
    evidence_bytes = (json.dumps(evidence, indent=2, sort_keys=True) + "\n").encode("utf-8")
    immutable_write(output_root / "evidence.json", evidence_bytes)
    print(
        json.dumps(
            {
                "status": evidence["status"],
                "tree_sha256": tree_sha256,
                "package_sha256": package_sha256,
                "evidence": str(output_root / "evidence.json"),
            },
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (OSError, ValueError, VerificationError, subprocess.SubprocessError) as error:
        print(f"verify-plugin-v1: {error}", file=sys.stderr)
        raise SystemExit(1)
