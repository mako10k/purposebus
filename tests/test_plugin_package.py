import json
import unittest
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
PLUGIN_ROOT = REPO_ROOT / "plugins" / "purposebus"


class PluginPackageTest(unittest.TestCase):
    def test_manifest_components_exist_and_are_bounded(self) -> None:
        manifest_path = PLUGIN_ROOT / ".codex-plugin" / "plugin.json"
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))

        self.assertEqual(manifest["name"], PLUGIN_ROOT.name)
        self.assertEqual(manifest["version"], "0.1.0")
        self.assertEqual(manifest["skills"], "./skills/")
        self.assertTrue((PLUGIN_ROOT / manifest["skills"]).is_dir())
        self.assertNotIn("mcpServers", manifest)
        self.assertNotIn("apps", manifest)
        self.assertNotIn("hooks", manifest)
        self.assertNotIn("[TODO:", manifest_path.read_text(encoding="utf-8"))

    def test_repo_marketplace_resolves_plugin(self) -> None:
        marketplace_path = REPO_ROOT / ".agents" / "plugins" / "marketplace.json"
        marketplace = json.loads(marketplace_path.read_text(encoding="utf-8"))
        self.assertEqual(marketplace["name"], "purposebus-local")

        entry = next(item for item in marketplace["plugins"] if item["name"] == "purposebus")
        self.assertEqual(entry["source"], {"source": "local", "path": "./plugins/purposebus"})
        self.assertEqual(entry["policy"]["installation"], "AVAILABLE")
        self.assertEqual(entry["policy"]["authentication"], "ON_INSTALL")
        self.assertTrue((REPO_ROOT / entry["source"]["path"]).is_dir())

    def test_skill_is_discoverable(self) -> None:
        skill_path = PLUGIN_ROOT / "skills" / "purposebus" / "SKILL.md"
        skill = skill_path.read_text(encoding="utf-8")
        self.assertTrue(skill.startswith("---\nname: purposebus\n"))
        self.assertIn("\ndescription:", skill.split("---", 2)[1])
        self.assertNotIn("[TODO:", skill)


if __name__ == "__main__":
    unittest.main()
