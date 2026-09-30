#!/usr/bin/env python3
"""Build and verify an immutable local PurposeBus RC candidate.

The verifier uses only temporary Python/Codex profiles and isolated PurposeBus
state. It never installs into an active user profile or contacts a package
index. Candidate artifacts are installed once under build/rc/<source-sha256>;
an existing artifact with different bytes is an error rather than an overwrite.
"""

from __future__ import annotations

import argparse
import concurrent.futures
import hashlib
import io
import json
import os
import platform
import re
import shutil
import stat
import subprocess
import sys
import tarfile
import tempfile
import tomllib
import venv
import zipfile
from email import policy
from email.parser import BytesParser
from pathlib import Path
from typing import Any, Iterable, Mapping, Sequence


REPO_ROOT = Path(__file__).resolve().parents[1]
CONTRACT_PATH = REPO_ROOT / "release" / "rc-contract.json"
SOURCE_DATE_EPOCH = "315532800"
SKIPPED_PREFIXES = (".git/", ".sealgraph/", ".venv/", "build/", "dist/")


class VerificationError(RuntimeError):
    pass


def run(
    command: Sequence[str | Path],
    *,
    cwd: Path = REPO_ROOT,
    environment: Mapping[str, str] | None = None,
    check: bool = True,
    timeout: float = 180,
) -> subprocess.CompletedProcess[str]:
    completed = subprocess.run(
        [str(item) for item in command],
        cwd=cwd,
        env=dict(environment) if environment is not None else None,
        capture_output=True,
        check=False,
        text=True,
        timeout=timeout,
    )
    if check and completed.returncode != 0:
        detail = completed.stderr.strip() or completed.stdout.strip()
        raise VerificationError(f"command failed ({completed.returncode}): {' '.join(map(str, command))}: {detail}")
    return completed


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def load_contract() -> dict[str, Any]:
    return json.loads(CONTRACT_PATH.read_text(encoding="utf-8"))


def repository_files(contract: Mapping[str, Any]) -> list[Path]:
    output = run(("git", "ls-files", "-co", "--exclude-standard", "-z")).stdout
    excluded = set(contract["source_snapshot_excludes"])
    paths: list[Path] = []
    for raw in output.split("\0"):
        if not raw:
            continue
        relative = Path(raw)
        normalized = relative.as_posix()
        if normalized in excluded or normalized.startswith(SKIPPED_PREFIXES):
            continue
        if "__pycache__" in relative.parts or any(part.endswith(".egg-info") for part in relative.parts):
            continue
        source = REPO_ROOT / relative
        if source.is_symlink() or not source.is_file():
            raise VerificationError(f"release source must be a regular file: {relative}")
        paths.append(relative)
    return sorted(paths, key=lambda item: item.as_posix())


def write_source_tar(destination: Path, paths: Iterable[Path]) -> None:
    with tarfile.open(destination, "w", format=tarfile.PAX_FORMAT) as archive:
        for relative in paths:
            source = REPO_ROOT / relative
            data = source.read_bytes()
            info = tarfile.TarInfo(relative.as_posix())
            info.size = len(data)
            info.mtime = int(SOURCE_DATE_EPOCH)
            info.mode = 0o755 if source.stat().st_mode & stat.S_IXUSR else 0o644
            info.uid = info.gid = 0
            info.uname = info.gname = ""
            archive.addfile(info, io.BytesIO(data))


def extract_tar(path: Path, destination: Path) -> None:
    destination.mkdir(parents=True, exist_ok=True)
    with tarfile.open(path, "r") as archive:
        for member in archive.getmembers():
            target = (destination / member.name).resolve()
            if destination.resolve() not in (target, *target.parents):
                raise VerificationError(f"archive path escapes destination: {member.name}")
        archive.extractall(destination, filter="data")


def safe_environment(home: Path) -> dict[str, str]:
    home.mkdir(parents=True, exist_ok=True)
    allowed = ("LANG", "LC_ALL", "LC_CTYPE", "PATH", "SHELL", "TERM", "USER", "LOGNAME")
    environment = {key: os.environ[key] for key in allowed if os.environ.get(key)}
    environment.update(
        {
            "HOME": str(home),
            "NO_COLOR": "1",
            "PYTHONHASHSEED": "0",
            "SOURCE_DATE_EPOCH": SOURCE_DATE_EPOCH,
        }
    )
    return environment


def build_wheel(python: Path, source: Path, destination: Path, home: Path) -> Path:
    destination.mkdir(parents=True, exist_ok=True)
    before = set(destination.glob("*.whl"))
    run(
        (
            python,
            "-m",
            "pip",
            "wheel",
            "--disable-pip-version-check",
            "--no-cache-dir",
            "--no-deps",
            "--no-build-isolation",
            "--wheel-dir",
            destination,
            source,
        ),
        environment=safe_environment(home),
    )
    created = set(destination.glob("*.whl")) - before
    if len(created) != 1:
        raise VerificationError(f"expected one wheel from {source}, found {len(created)}")
    return created.pop()


def wheel_metadata(path: Path) -> dict[str, Any]:
    with zipfile.ZipFile(path) as archive:
        metadata_names = [name for name in archive.namelist() if name.endswith(".dist-info/METADATA")]
        if len(metadata_names) != 1:
            raise VerificationError(f"wheel has {len(metadata_names)} METADATA files: {path}")
        message = BytesParser(policy=policy.default).parsebytes(archive.read(metadata_names[0]))
        return {
            "name": str(message["Name"]),
            "version": str(message["Version"]),
            "requires_dist": list(message.get_all("Requires-Dist", [])),
        }


def package_specs(contract: Mapping[str, Any]) -> tuple[tuple[str, str, str, str], ...]:
    candidate = contract["candidate"]
    return (
        ("core", ".", "purposebus", candidate["core_version"]),
        ("mcp", "integrations/purposebus_mcp", "purposebus-mcp", candidate["mcp_version"]),
        (
            "controller",
            "integrations/purposebus_codex_controller",
            "purposebus-codex-controller",
            candidate["controller_version"],
        ),
    )


def build_candidate_twice(
    python: Path,
    source_tar: Path,
    work: Path,
    contract: Mapping[str, Any],
) -> tuple[dict[str, Path], dict[str, dict[str, Any]]]:
    first: dict[str, Path] = {}
    metadata: dict[str, dict[str, Any]] = {}
    hashes: dict[str, str] = {}
    for build_number in (1, 2):
        source_root = work / f"candidate-source-{build_number}"
        extract_tar(source_tar, source_root)
        for key, relative, expected_name, expected_version in package_specs(contract):
            wheel = build_wheel(
                python,
                source_root / relative,
                work / f"candidate-wheels-{build_number}" / key,
                work / f"build-home-{build_number}",
            )
            details = wheel_metadata(wheel)
            if details["name"] != expected_name or details["version"] != expected_version:
                raise VerificationError(
                    f"{key} metadata mismatch: {details['name']} {details['version']}"
                )
            wheel_hash = sha256_file(wheel)
            if build_number == 1:
                first[key] = wheel
                metadata[key] = details
                hashes[key] = wheel_hash
            elif hashes[key] != wheel_hash:
                raise VerificationError(f"{key} wheel is not reproducible")
    if metadata["core"]["requires_dist"]:
        raise VerificationError("core wheel must remain dependency-free")
    if metadata["controller"]["requires_dist"]:
        raise VerificationError("controller policy wheel must remain dependency-free")
    return first, metadata


def build_baseline(
    python: Path, work: Path, contract: Mapping[str, Any]
) -> tuple[Path, Path, dict[str, Any]]:
    revision = contract["baseline"]["git_revision"]
    completed = subprocess.run(
        ["git", "archive", "--format=tar", revision],
        cwd=REPO_ROOT,
        capture_output=True,
        check=False,
        timeout=60,
    )
    if completed.returncode != 0:
        raise VerificationError(
            f"git archive failed ({completed.returncode}): "
            f"{completed.stderr.decode(errors='replace').strip()}"
        )
    archive = completed.stdout
    tar_path = work / "baseline-source.tar"
    tar_path.write_bytes(archive)
    source_root = work / "baseline-source"
    extract_tar(tar_path, source_root)
    wheel = build_wheel(python, source_root, work / "baseline-wheel", work / "baseline-home")
    details = wheel_metadata(wheel)
    expected = contract["baseline"]
    if details["name"] != "purposebus" or details["version"] != expected["core_version"]:
        raise VerificationError("baseline core metadata does not match the contract")
    return tar_path, wheel, details


def read_json_result(completed: subprocess.CompletedProcess[str]) -> dict[str, Any]:
    stream = completed.stdout if completed.returncode == 0 else completed.stderr
    try:
        document = json.loads(stream)
    except json.JSONDecodeError as exc:
        raise VerificationError(f"CLI did not return JSON: {stream!r}") from exc
    if not isinstance(document, dict):
        raise VerificationError("CLI JSON result was not an object")
    return document


def cli_command(executable: Path, partition: Path, state: Path, *arguments: str) -> tuple[str, ...]:
    return (
        str(executable),
        "--partition",
        str(partition),
        "--state-dir",
        str(state),
        "--format",
        "json",
        *arguments,
    )


def install_wheel(python: Path, wheel: Path, environment: Mapping[str, str]) -> None:
    run(
        (
            python,
            "-m",
            "pip",
            "install",
            "--disable-pip-version-check",
            "--no-index",
            "--no-deps",
            "--force-reinstall",
            wheel,
        ),
        environment=environment,
    )


def verify_core_transition(
    baseline_wheel: Path,
    candidate_wheel: Path,
    work: Path,
    contract: Mapping[str, Any],
) -> dict[str, Any]:
    environment_root = work / "core-transition"
    venv.EnvBuilder(with_pip=True, clear=False).create(environment_root)
    python = environment_root / "bin" / "python"
    executable = environment_root / "bin" / "purposebus"
    environment = safe_environment(work / "transition-home")
    partition = work / "transition-partition"
    state = work / "transition-state"
    partition.mkdir()

    install_wheel(python, baseline_wheel, environment)
    baseline_version = run((executable, "--version"), environment=environment).stdout.strip()
    initialized = read_json_result(
        run(cli_command(executable, partition, state, "init"), environment=environment)
    )
    registered = read_json_result(
        run(
            cli_command(
                executable,
                partition,
                state,
                "agent",
                "register",
                "rc-agent",
                "--kind",
                "ai",
                "--description",
                "RC transition probe",
            ),
            environment=environment,
        )
    )

    install_wheel(python, candidate_wheel, environment)
    candidate_version = run((executable, "--version"), environment=environment).stdout.strip()
    upgraded = read_json_result(
        run(cli_command(executable, partition, state, "agent", "list"), environment=environment)
    )
    if "rc-agent" not in json.dumps(upgraded, sort_keys=True):
        raise VerificationError("candidate did not reopen baseline state")

    install_wheel(python, baseline_wheel, environment)
    rolled_back = read_json_result(
        run(cli_command(executable, partition, state, "agent", "list"), environment=environment)
    )
    if "rc-agent" not in json.dumps(rolled_back, sort_keys=True):
        raise VerificationError("baseline did not reopen state after rollback")

    install_wheel(python, candidate_wheel, environment)
    reupgraded = read_json_result(
        run(cli_command(executable, partition, state, "status"), environment=environment)
    )
    if reupgraded.get("schema") != "purposebus.status.v2":
        raise VerificationError("candidate status schema changed after re-upgrade")

    expected_baseline = f"purposebus {contract['baseline']['core_version']}"
    expected_candidate = f"purposebus {contract['candidate']['core_version']}"
    if baseline_version != expected_baseline or candidate_version != expected_candidate:
        raise VerificationError("core transition version readback failed")
    return {
        "baseline_version": baseline_version,
        "candidate_version": candidate_version,
        "baseline_init_schema": initialized["schema"],
        "baseline_register_schema": registered["schema"],
        "upgrade_schema": upgraded["schema"],
        "rollback_schema": rolled_back["schema"],
        "reupgrade_schema": reupgraded["schema"],
        "state_record_preserved": True,
        "python": python,
        "executable": executable,
        "environment": environment,
    }


def verify_corruption_and_recovery(
    executable: Path, environment: Mapping[str, str], work: Path, error_schema: str
) -> dict[str, Any]:
    partition = work / "corrupt-partition"
    state = work / "corrupt-state"
    partition.mkdir()
    read_json_result(run(cli_command(executable, partition, state, "init"), environment=environment))
    databases = list(state.rglob("purposebus.sqlite3"))
    if len(databases) != 1:
        raise VerificationError(f"expected one PurposeBus database, found {len(databases)}")
    database = databases[0]
    database.write_bytes(b"purposebus-rc-intentional-corruption")
    corrupted_hash = sha256_file(database)
    failed = run(
        cli_command(executable, partition, state, "status"),
        environment=environment,
        check=False,
    )
    if failed.returncode == 0:
        raise VerificationError("corrupt state did not fail closed")
    document = read_json_result(failed)
    if document.get("schema") != error_schema or sha256_file(database) != corrupted_hash:
        raise VerificationError("corrupt state was modified or used an unexpected error schema")

    recovery_state = work / "recovery-state"
    recovered = read_json_result(
        run(cli_command(executable, partition, recovery_state, "init"), environment=environment)
    )
    recovery_databases = list(recovery_state.rglob("purposebus.sqlite3"))
    if len(recovery_databases) != 1:
        raise VerificationError("separate recovery state was not initialized")
    return {
        "failure_schema": document["schema"],
        "failure_error": document.get("error"),
        "corrupt_bytes_preserved": True,
        "recovery_schema": recovered["schema"],
        "state_directory_mode": oct(stat.S_IMODE(recovery_databases[0].parent.stat().st_mode)),
        "database_mode": oct(stat.S_IMODE(recovery_databases[0].stat().st_mode)),
    }


def verify_load(
    executable: Path,
    environment: Mapping[str, str],
    work: Path,
    contract: Mapping[str, Any],
) -> dict[str, Any]:
    partition = work / "load-partition"
    state = work / "load-state"
    partition.mkdir()
    read_json_result(run(cli_command(executable, partition, state, "init"), environment=environment))
    bounds = contract["bounds"]
    count = int(bounds["load_processes"])
    workers = int(bounds["load_workers"])
    timeout = float(bounds["per_process_timeout_seconds"])

    def one_status(_: int) -> str:
        completed = run(
            cli_command(executable, partition, state, "status"),
            environment=environment,
            timeout=timeout,
        )
        return str(read_json_result(completed).get("schema"))

    with concurrent.futures.ThreadPoolExecutor(max_workers=workers) as executor:
        schemas = list(executor.map(one_status, range(count)))
    if schemas != ["purposebus.status.v2"] * count:
        raise VerificationError("bounded load returned an unexpected schema")
    return {"processes": count, "workers": workers, "all_completed_within_timeout": True}


def plugin_tree_hash(root: Path) -> str:
    digest = hashlib.sha256()
    for path in sorted((item for item in root.rglob("*") if item.is_file()), key=lambda item: item.relative_to(root).as_posix()):
        relative = path.relative_to(root).as_posix().encode()
        digest.update(len(relative).to_bytes(4, "big"))
        digest.update(relative)
        digest.update(bytes.fromhex(sha256_file(path)))
    return digest.hexdigest()


def replace_test_plugin(source: Path, destination: Path, test_root: Path) -> None:
    resolved = destination.resolve()
    if test_root.resolve() not in resolved.parents:
        raise VerificationError("refusing to replace a plugin outside the temporary test root")
    if destination.exists():
        shutil.rmtree(destination)
    shutil.copytree(source, destination)


def verify_cached_plugin(codex_home: Path, source: Path, expected_version: str) -> None:
    expected = codex_home / "plugins" / "cache" / "purposebus-local" / "purposebus" / expected_version
    manifest_path = expected / ".codex-plugin" / "plugin.json"
    if not manifest_path.is_file():
        candidates = list(codex_home.rglob(".codex-plugin/plugin.json"))
        raise VerificationError(f"expected cached Plugin was absent; found {candidates}")
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    if manifest.get("version") != expected_version:
        raise VerificationError("cached Plugin version does not match source")
    for source_file in (item for item in source.rglob("*") if item.is_file()):
        relative = source_file.relative_to(source)
        cached_file = expected / relative
        if not cached_file.is_file() or sha256_file(cached_file) != sha256_file(source_file):
            raise VerificationError(f"cached Plugin differs from source: {relative}")


def verify_plugin_transition(
    baseline_root: Path,
    candidate_root: Path,
    work: Path,
    contract: Mapping[str, Any],
) -> dict[str, Any]:
    codex = shutil.which("codex")
    if codex is None:
        raise VerificationError("codex executable is required for Plugin transition verification")
    isolated_home = work / "codex-user-home"
    codex_home = isolated_home / ".codex"
    codex_home.mkdir(parents=True)
    marketplace_root = work / "test-marketplace"
    marketplace_file = marketplace_root / ".agents" / "plugins" / "marketplace.json"
    marketplace_file.parent.mkdir(parents=True)
    shutil.copy2(baseline_root / ".agents" / "plugins" / "marketplace.json", marketplace_file)
    test_plugin = marketplace_root / "plugins" / "purposebus"
    replace_test_plugin(baseline_root / "plugins" / "purposebus", test_plugin, marketplace_root)

    environment = safe_environment(isolated_home)
    environment["CODEX_HOME"] = str(codex_home)
    add_marketplace = (codex, "plugin", "marketplace", "add", marketplace_root, "--json")
    add_plugin = (codex, "plugin", "add", "purposebus@purposebus-local", "--json")
    run(add_marketplace, environment=environment, timeout=60)

    baseline_version = contract["baseline"]["plugin_version"]
    candidate_version = contract["candidate"]["plugin_version"]
    run(add_plugin, environment=environment, timeout=60)
    verify_cached_plugin(codex_home, test_plugin, baseline_version)

    replace_test_plugin(candidate_root / "plugins" / "purposebus", test_plugin, marketplace_root)
    run(add_plugin, environment=environment, timeout=60)
    verify_cached_plugin(codex_home, test_plugin, candidate_version)

    run((codex, "plugin", "remove", "purposebus@purposebus-local", "--json"), environment=environment, timeout=60)
    removed = json.loads(
        run(
            (codex, "plugin", "list", "--marketplace", "purposebus-local", "--json"),
            environment=environment,
            timeout=60,
        ).stdout
    )
    if any(item["pluginId"] == "purposebus@purposebus-local" for item in removed["installed"]):
        raise VerificationError("candidate Plugin remains installed after removal")
    run(add_plugin, environment=environment, timeout=60)
    verify_cached_plugin(codex_home, test_plugin, candidate_version)

    replace_test_plugin(baseline_root / "plugins" / "purposebus", test_plugin, marketplace_root)
    run(add_plugin, environment=environment, timeout=60)
    verify_cached_plugin(codex_home, test_plugin, baseline_version)

    run((codex, "plugin", "remove", "purposebus@purposebus-local", "--json"), environment=environment, timeout=60)
    run((codex, "plugin", "marketplace", "remove", "purposebus-local", "--json"), environment=environment, timeout=60)
    return {
        "baseline_version": baseline_version,
        "candidate_version": candidate_version,
        "upgrade_cache_readback": True,
        "candidate_uninstall_readback": True,
        "candidate_reinstall_readback": True,
        "rollback_cache_readback": True,
        "isolated_home": True,
        "active_profile_unchanged": True,
        "baseline_tree_sha256": plugin_tree_hash(baseline_root / "plugins" / "purposebus"),
        "candidate_tree_sha256": plugin_tree_hash(candidate_root / "plugins" / "purposebus"),
        "codex_version": run((codex, "--version"), environment=environment).stdout.strip(),
    }


def verify_contract(contract: Mapping[str, Any]) -> None:
    if contract.get("schema") != "purposebus.rc-contract.v1":
        raise VerificationError("unsupported RC contract schema")
    for relative, expected in contract["candidate"]["critical_file_sha256"].items():
        actual = sha256_file(REPO_ROOT / relative)
        if actual != expected:
            raise VerificationError(f"critical file drift: {relative}: {actual}")
    schemas = sorted(set(re.findall(r'purposebus\.[a-z0-9-]+\.v2', (REPO_ROOT / "src/purposebus/cli.py").read_text(encoding="utf-8"))))
    if schemas != contract["candidate"]["public_success_schemas"]:
        raise VerificationError("public success schema set drifted")
    if set(contract["candidate"]["plugin_components"]) != {"skills"}:
        raise VerificationError("the current RC contract must keep the Plugin Skill-only")


def install_immutable(source: Path, destination: Path) -> None:
    if destination.exists():
        if sha256_file(source) != sha256_file(destination):
            raise VerificationError(f"immutable output differs: {destination}")
        return
    destination.parent.mkdir(parents=True, exist_ok=True)
    with destination.open("xb") as stream:
        stream.write(source.read_bytes())


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output-root", type=Path, default=REPO_ROOT / "build" / "rc")
    arguments = parser.parse_args()
    contract = load_contract()
    verify_contract(contract)

    build_root = REPO_ROOT / "build"
    build_root.mkdir(exist_ok=True)
    with tempfile.TemporaryDirectory(prefix="purposebus-rc-", dir=build_root) as temporary:
        work = Path(temporary)
        source_tar = work / "candidate-source.tar"
        write_source_tar(source_tar, repository_files(contract))
        source_hash = sha256_file(source_tar)
        baseline_tar, baseline_wheel, baseline_metadata = build_baseline(Path(sys.executable), work, contract)
        candidate_wheels, candidate_metadata = build_candidate_twice(
            Path(sys.executable), source_tar, work, contract
        )

        candidate_source_root = work / "candidate-for-runtime"
        extract_tar(source_tar, candidate_source_root)
        baseline_source_root = work / "baseline-for-runtime"
        extract_tar(baseline_tar, baseline_source_root)
        transition = verify_core_transition(
            baseline_wheel, candidate_wheels["core"], work, contract
        )
        corruption = verify_corruption_and_recovery(
            transition.pop("executable"),
            transition.pop("environment"),
            work,
            contract["candidate"]["error_schema"],
        )
        transition.pop("python")
        load = verify_load(
            work / "core-transition" / "bin" / "purposebus",
            safe_environment(work / "transition-home"),
            work,
            contract,
        )
        plugin = verify_plugin_transition(
            baseline_source_root, candidate_source_root, work, contract
        )

        destination = arguments.output_root.resolve() / source_hash
        artifacts = destination / "artifacts"
        install_immutable(source_tar, artifacts / "candidate-source.tar")
        install_immutable(baseline_tar, artifacts / "baseline-source.tar")
        install_immutable(baseline_wheel, artifacts / "baseline" / baseline_wheel.name)
        wheel_records: dict[str, Any] = {}
        for key, wheel in candidate_wheels.items():
            target = artifacts / "candidate" / wheel.name
            install_immutable(wheel, target)
            wheel_records[key] = {
                "file": str(target.relative_to(destination)),
                "sha256": sha256_file(wheel),
                "metadata": candidate_metadata[key],
                "reproducible_two_builds": True,
            }

        evidence = {
            "schema": "purposebus.rc-evidence.v1",
            "status": "passed",
            "contract_sha256": sha256_file(CONTRACT_PATH),
            "source": {
                "base_head": run(("git", "rev-parse", "HEAD")).stdout.strip(),
                "candidate_tar": "artifacts/candidate-source.tar",
                "candidate_tar_sha256": source_hash,
                "baseline_revision": contract["baseline"]["git_revision"],
                "baseline_tar_sha256": sha256_file(baseline_tar),
            },
            "wheels": wheel_records,
            "baseline_wheel": {
                "file": str((artifacts / "baseline" / baseline_wheel.name).relative_to(destination)),
                "sha256": sha256_file(baseline_wheel),
                "metadata": baseline_metadata,
            },
            "checks": {
                "critical_contract_files": "passed",
                "public_schema_freeze": "passed",
                "candidate_wheel_reproducibility": "passed",
                "core_upgrade_rollback": transition,
                "corrupt_state_recovery": corruption,
                "bounded_load": load,
                "plugin_upgrade_rollback": plugin,
            },
            "environment": {
                "platform": platform.platform(),
                "python": platform.python_version(),
                "implementation": platform.python_implementation(),
                "machine": platform.machine(),
                "codex": plugin["codex_version"],
            },
            "limitations": [
                "No active Codex or ChatGPT profile was changed.",
                "No new conversation or agent run was started.",
                "Only the recorded WSL2 Ubuntu and Python environment was exercised.",
                "Public Plugin Directory review, signing, publication, and deployment were not exercised.",
            ],
        }
        evidence_bytes = (json.dumps(evidence, indent=2, sort_keys=True) + "\n").encode()
        evidence_temp = work / "evidence.json"
        evidence_temp.write_bytes(evidence_bytes)
        install_immutable(evidence_temp, destination / "evidence.json")
        print(json.dumps({"status": "passed", "source_sha256": source_hash, "evidence": str(destination / "evidence.json")}, sort_keys=True))
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (OSError, VerificationError, subprocess.SubprocessError, ValueError) as exc:
        print(json.dumps({"status": "failed", "error": str(exc)}, sort_keys=True), file=sys.stderr)
        raise SystemExit(1)
