import json
import tomllib
import unittest
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]


class IntegrationPackageBoundaryTest(unittest.TestCase):
    def project(self, relative_path: str) -> dict:
        return tomllib.loads((REPO_ROOT / relative_path).read_text(encoding="utf-8"))

    def test_core_remains_standard_library_only(self) -> None:
        core = self.project("pyproject.toml")
        self.assertNotIn("dependencies", core["project"])
        mcp = self.project("integrations/purposebus_mcp/pyproject.toml")
        self.assertEqual(
            mcp["project"]["dependencies"],
            ["mcp>=2.2,<3", "pydantic>=2.12,<3"],
        )

    def test_controller_is_non_runnable_and_dependency_free(self) -> None:
        controller = self.project("integrations/purposebus_codex_controller/pyproject.toml")
        self.assertNotIn("dependencies", controller["project"])
        self.assertNotIn("scripts", controller["project"])

    def test_existing_plugin_does_not_silently_gain_mcp(self) -> None:
        manifest = json.loads(
            (
                REPO_ROOT
                / "plugins"
                / "purposebus"
                / ".codex-plugin"
                / "plugin.json"
            ).read_text(encoding="utf-8")
        )
        self.assertNotIn("mcpServers", manifest)
        self.assertNotIn("apps", manifest)
        self.assertNotIn("hooks", manifest)


if __name__ == "__main__":
    unittest.main()
