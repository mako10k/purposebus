#!/usr/bin/env python3
"""R: Assemble verified local release assets and their immutable upload inventory."""

from __future__ import annotations

import argparse
import hashlib
import io
import json
import shutil
import tarfile
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def contained(root: Path, relative: str) -> Path:
    path = (root / relative).resolve()
    if root.resolve() not in path.parents or not path.is_file() or path.is_symlink():
        raise ValueError(f"invalid release file: {relative}")
    return path


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("release_dir", type=Path)
    parser.add_argument("output_dir", type=Path)
    args = parser.parse_args()
    source = args.release_dir.resolve()
    manifest = json.loads((source / "release-manifest.json").read_text())
    evidence = json.loads((source / "evidence.json").read_text())
    if evidence["status"] != "passed" or evidence["release_manifest"]["sha256"] != digest(source / "release-manifest.json"):
        raise ValueError("release evidence does not bind the manifest")
    records = [manifest["candidate"]["source"], manifest["candidate"]["plugin"],
               manifest["contract"], *manifest["rollback"].values(),
               *manifest["candidate"]["wheels"].values()]
    for record in records:
        if digest(contained(source, record["file"])) != record["sha256"]:
            raise ValueError(f"artifact hash mismatch: {record['file']}")
    contract = json.loads(contained(source, manifest["contract"]["file"]).read_text())
    inputs: dict[str, Path] = {}
    for predecessor in contract["predecessors"].values():
        for key, value in predecessor.items():
            if key.endswith("_path"):
                path = contained(ROOT, value)
                if digest(path) != predecessor[key.removesuffix("_path") + "_sha256"]:
                    raise ValueError(f"predecessor hash mismatch: {value}")
                inputs["verification-inputs/" + value] = path
    for path in source.rglob("*"):
        if path.is_file():
            if path.is_symlink():
                raise ValueError("release symlinks are not supported")
            inputs["release/" + path.relative_to(source).as_posix()] = path
    output = args.output_dir.resolve()
    output.mkdir(parents=True, exist_ok=False)
    selected = [manifest["candidate"]["source"], manifest["candidate"]["plugin"],
                *manifest["candidate"]["wheels"].values()]
    for record in selected:
        path = contained(source, record["file"])
        shutil.copy2(path, output / path.name)
    for name in ("release-manifest.json", "evidence.json"):
        shutil.copy2(source / name, output / name)
    bundle = output / "purposebus-1.0.0-release-bundle.tar"
    with tarfile.open(bundle, "w", format=tarfile.PAX_FORMAT) as archive:
        for name, path in sorted(inputs.items()):
            data = path.read_bytes()
            info = tarfile.TarInfo(name)
            info.size = len(data)
            info.mtime = 315532800
            info.mode = 0o644
            archive.addfile(info, io.BytesIO(data))
    assets = sorted(output.iterdir())
    (output / "SHA256SUMS").write_text("".join(f"{digest(path)}  {path.name}\n" for path in assets))
    inventory = {path.name: {"sha256": digest(path), "bytes": path.stat().st_size}
                 for path in sorted(output.iterdir())}
    (output.parent / (output.name + "-inventory.json")).write_text(json.dumps(inventory, indent=2) + "\n")
    print(json.dumps({"status": "prepared", "assets": inventory}, sort_keys=True))


if __name__ == "__main__":
    main()
