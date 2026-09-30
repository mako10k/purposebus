import hashlib
import json
import unittest
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
CONTRACT = json.loads(
    (REPO_ROOT / "release/plugin-v1-contract.json").read_text(encoding="utf-8")
)


class PluginV1ContractTest(unittest.TestCase):
    def test_historical_identity_and_core_compatibility_are_preserved(self) -> None:
        self.assertEqual(CONTRACT["schema"], "purposebus.plugin-package-contract.v1")
        self.assertEqual(CONTRACT["plugin"]["name"], "purposebus")
        self.assertEqual(CONTRACT["plugin"]["version"], "1.0.0+codex.20260908092104")
        self.assertEqual(CONTRACT["core_compatibility"]["specifier"], "==0.2.0a1")
        self.assertEqual(CONTRACT["core_compatibility"]["verified_versions"], ["0.2.0a1"])

    def test_historical_hashes_are_well_formed_and_bound_by_release_contract(self) -> None:
        for expected in CONTRACT["critical_file_sha256"].values():
            self.assertRegex(expected, r"^[0-9a-f]{64}$")
        release_contract = json.loads(
            (REPO_ROOT / "release/v1-contract.json").read_text(encoding="utf-8")
        )
        actual = hashlib.sha256(
            (REPO_ROOT / "release/plugin-v1-contract.json").read_bytes()
        ).hexdigest()
        self.assertEqual(
            release_contract["predecessors"]["plugin_package"]["contract_sha256"],
            actual,
        )

    def test_components_and_marketplace_are_bounded(self) -> None:
        marketplace = json.loads(
            (REPO_ROOT / CONTRACT["marketplace"]["file"]).read_text(encoding="utf-8")
        )
        entry = next(
            item for item in marketplace["plugins"] if item["name"] == CONTRACT["plugin"]["name"]
        )
        self.assertEqual(CONTRACT["plugin"]["components"], ["skills"])
        self.assertEqual(marketplace["name"], CONTRACT["marketplace"]["name"])
        self.assertEqual(entry["source"], CONTRACT["marketplace"]["source"])
        self.assertEqual(entry["policy"], CONTRACT["marketplace"]["policy"])
        self.assertEqual(entry["category"], CONTRACT["marketplace"]["category"])

    def test_evaluation_and_authority_sets_are_explicit(self) -> None:
        self.assertEqual(
            set(CONTRACT["required_evaluations"]),
            {"direct", "indirect", "follow_up", "negative", "cross_host_boundary", "request_response"},
        )
        self.assertTrue(
            {
                "active_profile_installation",
                "commit",
                "push",
                "publication",
                "plugin_directory_submission",
                "mcp_or_app_addition",
            }
            <= set(CONTRACT["excluded_authority"])
        )


if __name__ == "__main__":
    unittest.main()
