"""R: Verify release review fixes through isolated public CLI invocations."""

from __future__ import annotations

import json
import os
import sqlite3
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


class ReleaseRegressionTest(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.project = self.root / "project"
        self.project.mkdir()
        self.state = self.root / "state"
        self.env = dict(os.environ, PYTHONPATH=str(ROOT / "src"))

    def cli(self, *args, expected=0, explicit=True, env=None, cwd=None):
        command = [sys.executable, "-m", "purposebus", "--state-dir", str(self.state), "--format", "json"]
        if explicit:
            command += ["--partition", str(self.project)]
        result = subprocess.run(command + list(args), cwd=cwd or self.project,
                                env=env or self.env, capture_output=True, text=True, timeout=10)
        self.assertEqual(result.returncode, expected, result.stdout + result.stderr)
        return json.loads(result.stdout if expected == 0 else result.stderr)

    def snapshot(self):
        database = next(self.state.rglob("purposebus.sqlite3"))
        with sqlite3.connect(database) as conn:
            return list(conn.iterdump())

    def test_implicit_partition_ignores_inherited_git_context(self):
        git_env = {k: v for k, v in self.env.items() if not k.startswith("GIT_")}
        subprocess.run(["git", "init", "-q", str(self.project)], env=git_env, check=True)
        other = self.root / "other"
        other.mkdir()
        subprocess.run(["git", "init", "-q", str(other)], env=git_env, check=True)
        nested = self.project / "nested"
        nested.mkdir()
        contexts = [
            {"GIT_WORK_TREE": str(other)},
            {"GIT_DIR": str(other / ".git"), "GIT_WORK_TREE": str(other)},
            {"GIT_CONFIG_COUNT": "1", "GIT_CONFIG_KEY_0": "core.worktree", "GIT_CONFIG_VALUE_0": str(other)},
        ]
        for context in contexts:
            with self.subTest(context=context):
                result = self.cli("init", explicit=False, env=dict(git_env, **context), cwd=nested)
                self.assertEqual(result["partition"]["path"], str(self.project))
                self.assertEqual(result["partition"]["source"], "git_worktree")

    def test_overflowing_durations_are_structured_errors_without_mutation(self):
        self.cli("init")
        self.cli("agent", "register", "probe", "--kind", "ai", "--description", "release probe")
        self.cli("instance", "start", "probe", "--id", "probe-1", "--objective", "release probe")
        before = self.snapshot()
        commands = [
            ("poll", "--instance", "probe-1", "--wait", "9" * 400 + "s"),
            ("poll", "--instance", "probe-1", "--wait", "999999999999999999s"),
            ("subscription", "add", "probe/#", "--instance", "probe-1", "--purpose", "probe", "--expires-in", "999999999999999999s"),
            ("publish", "probe/test", "--instance", "probe-1", "--purpose", "probe", "--payload", "probe", "--expires-in", "9" * 400 + "s"),
        ]
        for args in commands:
            with self.subTest(command=args[0]):
                result = self.cli(*args, expected=2)
                self.assertEqual(result["schema"], "purposebus.error.v1")
                self.assertEqual(result["error"], "invalid_input")
                self.assertEqual(self.snapshot(), before)


if __name__ == "__main__":
    unittest.main()
