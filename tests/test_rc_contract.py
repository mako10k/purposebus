import hashlib
import json
import re
import tomllib
import unittest
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
CONTRACT = json.loads((REPO_ROOT / "release" / "rc-contract.json").read_text(encoding="utf-8"))
PLUGIN_V1_CONTRACT = json.loads(
    (REPO_ROOT / "release" / "plugin-v1-contract.json").read_text(encoding="utf-8")
)


class RcContractTest(unittest.TestCase):
    def test_contract_pins_accepted_rc_package_versions(self) -> None:
        candidate = CONTRACT["candidate"]
        mcp = tomllib.loads(
            (REPO_ROOT / "integrations/purposebus_mcp/pyproject.toml").read_text(encoding="utf-8")
        )
        controller = tomllib.loads(
            (REPO_ROOT / "integrations/purposebus_codex_controller/pyproject.toml").read_text(encoding="utf-8")
        )
        self.assertEqual(candidate["core_version"], "0.2.0a1")
        self.assertEqual(mcp["project"]["version"], candidate["mcp_version"])
        self.assertEqual(controller["project"]["version"], candidate["controller_version"])
        self.assertEqual(candidate["plugin_version"], "0.2.0+codex.20260904090953")
        self.assertEqual(
            PLUGIN_V1_CONTRACT["predecessor"]["plugin_version"], candidate["plugin_version"]
        )

    def test_historical_contract_is_bound_by_v1_release_contract(self) -> None:
        release_contract = json.loads(
            (REPO_ROOT / "release/v1-contract.json").read_text(encoding="utf-8")
        )
        actual = hashlib.sha256((REPO_ROOT / "release/rc-contract.json").read_bytes()).hexdigest()
        self.assertEqual(
            release_contract["predecessors"]["rc"]["contract_sha256"], actual
        )
        for expected in CONTRACT["candidate"]["critical_file_sha256"].values():
            self.assertRegex(expected, r"^[0-9a-f]{64}$")

    def test_public_success_schema_set_is_frozen(self) -> None:
        release_contract = json.loads(
            (REPO_ROOT / "release/v1-contract.json").read_text(encoding="utf-8")
        )
        self.assertEqual(
            release_contract["candidate"]["public_success_schemas"],
            CONTRACT["candidate"]["public_success_schemas"],
        )

    def test_plugin_and_authority_boundaries_remain_explicit(self) -> None:
        self.assertEqual(CONTRACT["candidate"]["plugin_components"], ["skills"])
        excluded = set(CONTRACT["excluded_authority"])
        self.assertTrue(
            {"active_profile_installation", "commit", "push", "release", "agent_launch"}
            <= excluded
        )
        self.assertEqual(
            CONTRACT["source_snapshot_excludes"],
            ["docs/rc-candidate-evidence-2026-09-08.md"],
        )


if __name__ == "__main__":
    unittest.main()
