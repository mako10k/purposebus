import hashlib
import json
import re
import tomllib
import unittest
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
CONTRACT = json.loads((REPO_ROOT / "release/v1-contract.json").read_text(encoding="utf-8"))


class V1ReleaseContractTest(unittest.TestCase):
    def test_exact_core_plugin_and_adapter_versions(self) -> None:
        candidate = CONTRACT["candidate"]
        project = tomllib.loads((REPO_ROOT / "pyproject.toml").read_text(encoding="utf-8"))
        manifest = json.loads(
            (REPO_ROOT / "plugins/purposebus/.codex-plugin/plugin.json").read_text(
                encoding="utf-8"
            )
        )
        runtime = (REPO_ROOT / "src/purposebus/__init__.py").read_text(encoding="utf-8")
        adapter = (
            REPO_ROOT / "integrations/purposebus_mcp/src/purposebus_mcp/cli_adapter.py"
        ).read_text(encoding="utf-8")
        self.assertEqual(CONTRACT["schema"], "purposebus.release-contract.v1")
        self.assertEqual(project["project"]["version"], "1.0.0")
        self.assertIn('__version__ = "1.0.0"', runtime)
        self.assertEqual(candidate["core_version"], "1.0.0")
        self.assertEqual(manifest["version"], candidate["plugin_version"])
        self.assertEqual(candidate["plugin_core_specifier"], "==1.0.0")
        self.assertIn('SUPPORTED_PURPOSEBUS_VERSION = "1.0.0"', adapter)

    def test_critical_files_match_the_frozen_hashes(self) -> None:
        for relative, expected in CONTRACT["candidate"]["critical_file_sha256"].items():
            with self.subTest(relative=relative):
                actual = hashlib.sha256((REPO_ROOT / relative).read_bytes()).hexdigest()
                self.assertEqual(actual, expected)

    def test_public_and_state_contracts_are_unchanged(self) -> None:
        candidate = CONTRACT["candidate"]
        source = (REPO_ROOT / "src/purposebus/cli.py").read_text(encoding="utf-8")
        schemas = sorted(set(re.findall(r"purposebus\.[a-z0-9-]+\.v2", source)))
        self.assertEqual(schemas, candidate["public_success_schemas"])
        self.assertEqual(candidate["error_schema"], "purposebus.error.v1")
        self.assertEqual(candidate["state_schema"], "1")
        self.assertEqual(candidate["plugin_components"], ["skills"])

    def test_fresh_session_matrix_and_authority_are_explicit(self) -> None:
        evaluations = json.loads(
            (REPO_ROOT / CONTRACT["evaluations"]["path"]).read_text(encoding="utf-8")
        )
        self.assertEqual(evaluations["status"], "passed")
        self.assertEqual(
            set(CONTRACT["evaluations"]["required"]), set(evaluations["evaluations"])
        )
        self.assertTrue(
            {
                "active_profile_installation",
                "commit",
                "push",
                "tag",
                "publication",
                "release",
                "workspace_publication",
            }
            <= set(CONTRACT["excluded_authority"])
        )
        self.assertEqual(
            CONTRACT["publication_inputs"]["git_ref"], "pending_explicit_authorization"
        )


if __name__ == "__main__":
    unittest.main()
