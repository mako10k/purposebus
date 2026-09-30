import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from purposebus_mcp.cli_adapter import (
    PurposeBusCliError,
    PurposeBusCliGateway,
    PurposeBusGatewayError,
    PurposeBusProtocolError,
)
from purposebus_mcp.config import PartitionBinding


def completed(returncode: int, *, stdout: str = "", stderr: str = ""):
    return subprocess.CompletedProcess(["purposebus"], returncode, stdout, stderr)


class CliAdapterUnitTest(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        binding = PartitionBinding.parse(f"project={self.temporary.name}")
        self.gateway = PurposeBusCliGateway(
            {"project": binding},
            command=("/example/purposebus",),
            environment={
                "HOME": "/example/home",
                "GH_TOKEN": "must-not-be-forwarded",
                "PURPOSEBUS_STATE_DIR": "/example/state",
            },
        )
        self.binding = binding

    def document(self, schema: str) -> str:
        return json.dumps(
            {
                "schema": schema,
                "actor": None,
                "partition": {
                    "partition_id": "partition",
                    "path": str(self.binding.path),
                    "source": "explicit",
                    "display_name": "project",
                },
                "result": {},
            }
        )

    @patch("purposebus_mcp.cli_adapter.subprocess.run")
    def test_invokes_only_an_explicit_partition_and_a_clean_environment(self, run) -> None:
        run.return_value = completed(0, stdout=self.document("purposebus.status.v2"))
        result = self.gateway.status("project", limit=7)
        self.assertEqual(result["schema"], "purposebus.status.v2")
        arguments = run.call_args.args[0]
        self.assertEqual(
            arguments,
            [
                "/example/purposebus",
                "--partition",
                str(self.binding.path),
                "--format",
                "json",
                "status",
                "--limit",
                "7",
            ],
        )
        self.assertEqual(
            run.call_args.kwargs["env"],
            {"HOME": "/example/home", "PURPOSEBUS_STATE_DIR": "/example/state"},
        )

    @patch("purposebus_mcp.cli_adapter.subprocess.run")
    def test_checks_the_exact_core_version(self, run) -> None:
        run.return_value = completed(0, stdout="purposebus 1.0.0\n")
        self.gateway.check_version()
        run.return_value = completed(0, stdout="purposebus 1.0.1\n")
        with self.assertRaises(PurposeBusProtocolError):
            self.gateway.check_version()

    @patch("purposebus_mcp.cli_adapter.subprocess.run")
    def test_preserves_public_cli_errors_as_tool_safe_structure(self, run) -> None:
        run.return_value = completed(
            65,
            stderr=json.dumps(
                {
                    "schema": "purposebus.error.v1",
                    "error": "not_found",
                    "message": "Request was not found",
                    "hint": "inspect request list",
                }
            ),
        )
        with self.assertRaises(PurposeBusCliError) as caught:
            self.gateway.get_request("project", "req-missing")
        self.assertEqual(caught.exception.error, "not_found")
        self.assertEqual(caught.exception.exit_code, 65)

    @patch("purposebus_mcp.cli_adapter.subprocess.run")
    def test_fails_closed_on_schema_or_partition_drift(self, run) -> None:
        run.return_value = completed(0, stdout=self.document("purposebus.status.v1"))
        with self.assertRaises(PurposeBusProtocolError):
            self.gateway.status("project")
        document = json.loads(self.document("purposebus.status.v2"))
        document["partition"]["path"] = "/another/project"
        run.return_value = completed(0, stdout=json.dumps(document))
        with self.assertRaises(PurposeBusProtocolError):
            self.gateway.status("project")

    def test_rejects_unknown_tool_supplied_partition_alias(self) -> None:
        with self.assertRaisesRegex(PurposeBusGatewayError, "unknown partition alias"):
            self.gateway.status("not-configured")

    def test_rejects_control_like_identifiers_before_invoking_the_cli(self) -> None:
        with self.assertRaisesRegex(PurposeBusGatewayError, "invalid Instance ID"):
            self.gateway.next("project", "--partition=/another/project")
        with self.assertRaisesRegex(PurposeBusGatewayError, "invalid Request ID"):
            self.gateway.get_request("project", "../request")

    def test_rejects_non_finite_or_non_positive_timeouts(self) -> None:
        for timeout in (0, -1, float("nan"), float("inf")):
            with self.subTest(timeout=timeout), self.assertRaisesRegex(
                PurposeBusGatewayError, "timeout must be a finite value greater than zero"
            ):
                PurposeBusCliGateway(
                    {"project": self.binding},
                    command=("/example/purposebus",),
                    timeout_seconds=timeout,
                )


class CliAdapterLiveTest(unittest.TestCase):
    def run_cli(self, state_root: Path, partition: Path, *arguments: str) -> dict:
        environment = dict(os.environ)
        environment["XDG_STATE_HOME"] = str(state_root)
        completed_process = subprocess.run(
            [
                sys.executable,
                "-m",
                "purposebus",
                "--partition",
                str(partition),
                "--format",
                "json",
                *arguments,
            ],
            capture_output=True,
            check=True,
            env=environment,
            text=True,
        )
        return json.loads(completed_process.stdout)

    def test_all_six_operations_use_real_isolated_cli_responses(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            partition = root / "partition"
            state_root = root / "state"
            partition.mkdir()
            self.run_cli(state_root, partition, "init")
            self.run_cli(
                state_root,
                partition,
                "agent",
                "register",
                "worker",
                "--kind",
                "ai",
                "--description",
                "integration test worker",
            )
            self.run_cli(
                state_root,
                partition,
                "instance",
                "start",
                "worker",
                "--id",
                "worker-1",
                "--objective",
                "inspect integration behavior",
            )
            request = self.run_cli(
                state_root,
                partition,
                "request",
                "create",
                "test/topic",
                "--instance",
                "worker-1",
                "--purpose",
                "obtain integration evidence",
                "--id",
                "req-1",
            )
            binding = PartitionBinding.parse(f"project={partition}")
            gateway = PurposeBusCliGateway(
                {"project": binding},
                command=(sys.executable, "-m", "purposebus"),
                environment={"XDG_STATE_HOME": str(state_root)},
            )
            gateway.check_version()
            documents = [
                gateway.status("project", limit=10),
                gateway.list_agents("project", limit=10),
                gateway.list_instances("project", limit=10),
                gateway.match("project", limit=10, candidate_limit=5),
                gateway.next("project", "worker-1", limit=10),
                gateway.get_request("project", request["result"]["subscription_id"]),
            ]
            self.assertEqual(
                [document["schema"] for document in documents],
                [
                    "purposebus.status.v2",
                    "purposebus.agent-list.v2",
                    "purposebus.instance-list.v2",
                    "purposebus.match.v2",
                    "purposebus.next.v2",
                    "purposebus.request-show.v2",
                ],
            )


if __name__ == "__main__":
    unittest.main()
