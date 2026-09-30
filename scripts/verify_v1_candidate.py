#!/usr/bin/env python3
"""Build and verify the immutable local PurposeBus 1.0.0 release package.

The verifier uses content-addressed outputs, temporary Python and Codex homes,
and the accepted RC/Plugin artifacts as rollback inputs. It does not contact a
package index, mutate an active profile, or publish anything.
"""

from __future__ import annotations

import argparse
import hashlib
import io
import json
import os
import platform
import re
import shutil
import stat
import sys
import tempfile
import tomllib
import zipfile
from pathlib import Path
from typing import Any, Iterable, Mapping, Sequence

import verify_rc_candidate as rc


REPO_ROOT = Path(__file__).resolve().parents[1]
CONTRACT_PATH = REPO_ROOT / "release" / "v1-contract.json"
SOURCE_DATE_EPOCH = "315532800"
SECRET_PATTERNS = (
    re.compile(rb"sk-[A-Za-z0-9_-]{20,}"),
    re.compile(rb"gh[pousr]_[A-Za-z0-9]{20,}"),
    re.compile(rb"AKIA[A-Z0-9]{16}"),
    re.compile(rb"-----BEGIN [A-Z ]*PRIVATE KEY-----"),
)
DISALLOWED_NAMES = {".env", "auth.json", "credentials.json", "id_rsa", "id_ed25519"}


def sha256_file(path: Path) -> str:
    return rc.sha256_file(path)


def load_contract() -> dict[str, Any]:
    value = json.loads(CONTRACT_PATH.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise rc.VerificationError("release contract must be one JSON object")
    return value


def repository_path(value: str) -> Path:
    path = (REPO_ROOT / value).resolve()
    if REPO_ROOT.resolve() not in (path, *path.parents):
        raise rc.VerificationError(f"contract path escapes the repository: {value}")
    return path


def core_runtime_version() -> str:
    source = (REPO_ROOT / "src" / "purposebus" / "__init__.py").read_text(encoding="utf-8")
    matched = re.fullmatch(
        r'"""PurposeBus local-first agent coordination queue\."""\n\n__version__ = "([^"]+)"\n',
        source,
    )
    if matched is None:
        raise rc.VerificationError("purposebus.__version__ is not in the release form")
    return matched.group(1)


def verify_contract(contract: Mapping[str, Any]) -> None:
    if contract.get("schema") != "purposebus.release-contract.v1":
        raise rc.VerificationError("unsupported release contract schema")
    candidate = contract["candidate"]
    project = tomllib.loads((REPO_ROOT / "pyproject.toml").read_text(encoding="utf-8"))
    manifest = json.loads(
        (REPO_ROOT / "plugins" / "purposebus" / ".codex-plugin" / "plugin.json").read_text(
            encoding="utf-8"
        )
    )
    if project["project"]["version"] != candidate["core_version"] or core_runtime_version() != candidate["core_version"]:
        raise rc.VerificationError("core version sources differ from the release contract")
    if manifest.get("version") != candidate["plugin_version"]:
        raise rc.VerificationError("Plugin version differs from the release contract")
    if candidate["plugin_core_specifier"] != f"=={candidate['core_version']}":
        raise rc.VerificationError("Plugin core compatibility is not exact")
    skill = (REPO_ROOT / "plugins" / "purposebus" / "skills" / "purposebus" / "SKILL.md").read_text(
        encoding="utf-8"
    )
    if f"purposebus {candidate['core_version']}" not in skill or f"`=={candidate['core_version']}`" not in skill:
        raise rc.VerificationError("Plugin Skill does not declare the exact core version")
    adapter = (
        REPO_ROOT / "integrations" / "purposebus_mcp" / "src" / "purposebus_mcp" / "cli_adapter.py"
    ).read_text(encoding="utf-8")
    if f'SUPPORTED_PURPOSEBUS_VERSION = "{candidate["core_version"]}"' not in adapter:
        raise rc.VerificationError("MCP adapter does not pin the release core")
    for field in ("mcpServers", "apps", "hooks"):
        if field in manifest:
            raise rc.VerificationError(f"unexpected Plugin component: {field}")
    if candidate["plugin_components"] != ["skills"] or candidate["state_schema"] != "1":
        raise rc.VerificationError("release component or state-schema boundary changed")

    schemas = sorted(
        set(
            re.findall(
                r"purposebus\.[a-z0-9-]+\.v2",
                (REPO_ROOT / "src" / "purposebus" / "cli.py").read_text(encoding="utf-8"),
            )
        )
    )
    if schemas != candidate["public_success_schemas"]:
        raise rc.VerificationError("public success schema set drifted")
    for relative, expected in candidate["critical_file_sha256"].items():
        actual = sha256_file(repository_path(relative))
        if actual != expected:
            raise rc.VerificationError(f"critical file drift: {relative}: {actual}")

    for predecessor in contract["predecessors"].values():
        for key in ("contract", "source", "evidence", "core_wheel", "package"):
            path_key = f"{key}_path"
            hash_key = f"{key}_sha256"
            if path_key not in predecessor:
                continue
            path = repository_path(predecessor[path_key])
            if not path.is_file() or sha256_file(path) != predecessor[hash_key]:
                raise rc.VerificationError(f"predecessor {key} is absent or changed: {path}")
    evaluations = repository_path(contract["evaluations"]["path"])
    if sha256_file(evaluations) != contract["evaluations"]["sha256"]:
        raise rc.VerificationError("fresh-session evaluation manifest drifted")
    evaluation_document = json.loads(evaluations.read_text(encoding="utf-8"))
    if evaluation_document.get("status") != "passed":
        raise rc.VerificationError("fresh-session evaluation matrix has not passed")


def plugin_files(root: Path) -> list[Path]:
    files: list[Path] = []
    for path in root.rglob("*"):
        if path.is_symlink():
            raise rc.VerificationError(f"Plugin contains a symlink: {path}")
        if path.is_file():
            relative = path.relative_to(root)
            if relative.name.lower() in DISALLOWED_NAMES or relative.suffix.lower() in {".pem", ".key"}:
                raise rc.VerificationError(f"credential-like Plugin file: {relative}")
            content = path.read_bytes()
            if any(pattern.search(content) for pattern in SECRET_PATTERNS):
                raise rc.VerificationError(f"credential-like Plugin content: {relative}")
            files.append(relative)
    return sorted(files, key=lambda item: item.as_posix())


def plugin_archive(root: Path, files: Sequence[Path]) -> bytes:
    output = io.BytesIO()
    with zipfile.ZipFile(output, "w", compression=zipfile.ZIP_STORED) as archive:
        for relative in files:
            info = zipfile.ZipInfo(f"purposebus/{relative.as_posix()}")
            info.date_time = (1980, 1, 1, 0, 0, 0)
            info.compress_type = zipfile.ZIP_STORED
            info.create_system = 3
            info.external_attr = 0o100644 << 16
            archive.writestr(info, (root / relative).read_bytes())
    return output.getvalue()


def extract_plugin_archive(archive_path: Path, destination: Path) -> None:
    destination.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(archive_path) as archive:
        for member in archive.infolist():
            target = (destination / member.filename).resolve()
            if destination.resolve() not in (target, *target.parents):
                raise rc.VerificationError(f"Plugin archive path escapes destination: {member.filename}")
        archive.extractall(destination)


def baseline_plugin_root(contract: Mapping[str, Any], work: Path) -> Path:
    root = work / "baseline-plugin-source"
    marketplace = root / ".agents" / "plugins" / "marketplace.json"
    marketplace.parent.mkdir(parents=True)
    shutil.copy2(REPO_ROOT / ".agents" / "plugins" / "marketplace.json", marketplace)
    extracted = work / "baseline-plugin-archive"
    extract_plugin_archive(
        repository_path(contract["predecessors"]["plugin_package"]["package_path"]), extracted
    )
    shutil.copytree(extracted / "purposebus", root / "plugins" / "purposebus")
    return root


def run_source_tests(source_root: Path, work: Path) -> dict[str, Any]:
    environment = rc.safe_environment(work / "test-home")
    environment["PYTHONPATH"] = str(source_root / "src")
    completed = rc.run(
        (sys.executable, "-m", "unittest", "discover", "-s", "tests", "-v"),
        cwd=source_root,
        environment=environment,
        timeout=300,
    )
    count = len(re.findall(r"^test_", completed.stderr, flags=re.MULTILINE))
    return {"status": "passed", "observed_test_lines": count}


def copy_bytes(source: Path, destination: Path) -> None:
    rc.install_immutable(source, destination)


def write_bytes(data: bytes, destination: Path) -> None:
    with tempfile.NamedTemporaryFile(dir=destination.parent if destination.parent.exists() else None) as temporary:
        temporary.write(data)
        temporary.flush()
        rc.install_immutable(Path(temporary.name), destination)


def artifact_record(path: Path, root: Path) -> dict[str, str]:
    return {"file": str(path.relative_to(root)), "sha256": sha256_file(path)}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output-root", type=Path, default=REPO_ROOT / "build" / "v1")
    arguments = parser.parse_args()
    contract = load_contract()
    verify_contract(contract)

    build_root = REPO_ROOT / "build"
    build_root.mkdir(exist_ok=True)
    with tempfile.TemporaryDirectory(prefix="purposebus-v1-", dir=build_root) as raw_work:
        work = Path(raw_work)
        source_tar = work / "candidate-source.tar"
        rc.write_source_tar(source_tar, rc.repository_files(contract))
        source_sha256 = sha256_file(source_tar)
        candidate_wheels, candidate_metadata = rc.build_candidate_twice(
            Path(sys.executable), source_tar, work, contract
        )
        candidate_source = work / "candidate-source"
        rc.extract_tar(source_tar, candidate_source)
        source_tests = run_source_tests(candidate_source, work)

        predecessor_wheel = repository_path(contract["predecessors"]["rc"]["core_wheel_path"])
        transition = rc.verify_core_transition(
            predecessor_wheel, candidate_wheels["core"], work, contract
        )
        corruption = rc.verify_corruption_and_recovery(
            transition.pop("executable"),
            transition.pop("environment"),
            work,
            contract["candidate"]["error_schema"],
        )
        transition.pop("python")
        load = rc.verify_load(
            work / "core-transition" / "bin" / "purposebus",
            rc.safe_environment(work / "transition-home"),
            work,
            contract,
        )

        plugin_root = candidate_source / "plugins" / "purposebus"
        files = plugin_files(plugin_root)
        expected_files = contract["candidate"]["plugin_files"]
        if [path.as_posix() for path in files] != expected_files:
            raise rc.VerificationError("Plugin file allowlist drifted")
        plugin_bytes = plugin_archive(plugin_root, files)
        plugin_repeat = plugin_archive(plugin_root, files)
        if plugin_bytes != plugin_repeat:
            raise rc.VerificationError("Plugin archive is not deterministic")
        plugin = rc.verify_plugin_transition(
            baseline_plugin_root(contract, work), candidate_source, work, contract
        )

        destination = arguments.output_root.resolve() / source_sha256
        artifacts = destination / "artifacts"
        copy_bytes(source_tar, artifacts / "candidate-source.tar")
        wheel_records: dict[str, Any] = {}
        for key, wheel in candidate_wheels.items():
            target = artifacts / "candidate" / wheel.name
            copy_bytes(wheel, target)
            wheel_records[key] = {
                **artifact_record(target, destination),
                "metadata": candidate_metadata[key],
                "reproducible_two_builds": True,
            }
        plugin_name = f"purposebus-plugin-{contract['candidate']['plugin_version']}.zip"
        plugin_target = artifacts / "candidate" / plugin_name
        plugin_target.parent.mkdir(parents=True, exist_ok=True)
        write_bytes(plugin_bytes, plugin_target)
        rollback_core = artifacts / "rollback" / predecessor_wheel.name
        copy_bytes(predecessor_wheel, rollback_core)
        predecessor_plugin = repository_path(
            contract["predecessors"]["plugin_package"]["package_path"]
        )
        rollback_plugin = artifacts / "rollback" / predecessor_plugin.name
        copy_bytes(predecessor_plugin, rollback_plugin)
        contract_target = artifacts / "contracts" / CONTRACT_PATH.name
        copy_bytes(CONTRACT_PATH, contract_target)

        artifact_manifest = {
            "schema": "purposebus.release-artifacts.v1",
            "core_version": contract["candidate"]["core_version"],
            "plugin_version": contract["candidate"]["plugin_version"],
            "source_sha256": source_sha256,
            "candidate": {
                "source": artifact_record(artifacts / "candidate-source.tar", destination),
                "wheels": wheel_records,
                "plugin": artifact_record(plugin_target, destination),
            },
            "rollback": {
                "core": artifact_record(rollback_core, destination),
                "plugin": artifact_record(rollback_plugin, destination),
            },
            "contract": artifact_record(contract_target, destination),
        }
        manifest_bytes = (json.dumps(artifact_manifest, indent=2, sort_keys=True) + "\n").encode()
        manifest_target = destination / "release-manifest.json"
        manifest_target.parent.mkdir(parents=True, exist_ok=True)
        write_bytes(manifest_bytes, manifest_target)

        evidence = {
            "schema": "purposebus.release-evidence.v1",
            "status": "passed",
            "contract_sha256": sha256_file(CONTRACT_PATH),
            "source": {
                "base_head": rc.run(("git", "rev-parse", "HEAD")).stdout.strip(),
                "candidate_tar_sha256": source_sha256,
            },
            "release_manifest": artifact_record(manifest_target, destination),
            "checks": {
                "critical_contract_files": "passed",
                "source_tests": source_tests,
                "candidate_wheel_reproducibility": "passed",
                "core_upgrade_no_migration_rollback": transition,
                "corrupt_state_recovery": corruption,
                "bounded_load": load,
                "plugin_upgrade_uninstall_rollback": plugin,
                "plugin_archive_deterministic": True,
                "fresh_session_matrix": contract["evaluations"],
            },
            "environment": {
                "platform": platform.platform(),
                "python": platform.python_version(),
                "implementation": platform.python_implementation(),
                "machine": platform.machine(),
                "codex": plugin["codex_version"],
            },
            "limitations": contract["limitations"],
        }
        evidence_bytes = (json.dumps(evidence, indent=2, sort_keys=True) + "\n").encode()
        evidence_target = destination / "evidence.json"
        write_bytes(evidence_bytes, evidence_target)
        print(
            json.dumps(
                {
                    "status": "passed",
                    "source_sha256": source_sha256,
                    "manifest": str(manifest_target),
                    "evidence": str(evidence_target),
                },
                sort_keys=True,
            )
        )
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (OSError, ValueError, rc.VerificationError) as error:
        print(json.dumps({"status": "failed", "error": str(error)}, sort_keys=True), file=sys.stderr)
        raise SystemExit(1)
