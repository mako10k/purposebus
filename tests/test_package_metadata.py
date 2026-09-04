import tomllib
import unittest
from pathlib import Path

import purposebus


REPO_ROOT = Path(__file__).resolve().parents[1]


class PackageMetadataTest(unittest.TestCase):
    def test_current_version_is_consistent(self) -> None:
        project = tomllib.loads(
            (REPO_ROOT / "pyproject.toml").read_text(encoding="utf-8")
        )
        version = project["project"]["version"]
        readme = (REPO_ROOT / "README.md").read_text(encoding="utf-8")

        self.assertEqual(purposebus.__version__, version)
        self.assertIn(f"(`{version}`)", readme)


if __name__ == "__main__":
    unittest.main()
