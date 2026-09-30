import tempfile
import unittest
from pathlib import Path

from purposebus_mcp.config import ConfigurationError, PartitionBinding, parse_bindings


class PartitionBindingTest(unittest.TestCase):
    def test_parses_an_explicit_existing_directory(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            binding = PartitionBinding.parse(f"project={directory}")
            self.assertEqual(binding.alias, "project")
            self.assertEqual(binding.path, Path(directory).resolve())

    def test_rejects_paths_and_aliases_that_expand_the_tool_boundary(self) -> None:
        for value in ("Project=/tmp", "project=relative", "missing", "=/tmp"):
            with self.subTest(value=value), self.assertRaises(ConfigurationError):
                PartitionBinding.parse(value)

    def test_requires_unique_aliases_and_paths(self) -> None:
        with tempfile.TemporaryDirectory() as first, tempfile.TemporaryDirectory() as second:
            with self.assertRaises(ConfigurationError):
                parse_bindings([f"one={first}", f"one={second}"])
            with self.assertRaises(ConfigurationError):
                parse_bindings([f"one={first}", f"two={first}"])


if __name__ == "__main__":
    unittest.main()
