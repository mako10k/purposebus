import asyncio
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

from purposebus_mcp.server import create_server


class StubGateway:
    def __getattr__(self, _name):
        return lambda *_args, **_kwargs: {}


class ServerContractTest(unittest.TestCase):
    def test_advertises_only_the_six_read_only_tools(self) -> None:
        server = create_server(StubGateway())
        tools = asyncio.run(server.list_tools())
        self.assertEqual(
            [tool.name for tool in tools],
            [
                "purposebus_status",
                "purposebus_list_agents",
                "purposebus_list_instances",
                "purposebus_match",
                "purposebus_next",
                "purposebus_get_request",
            ],
        )
        self.assertEqual(
            [tool.title for tool in tools],
            [
                "Read PurposeBus status",
                "List PurposeBus agents",
                "List PurposeBus agent instances",
                "Match PurposeBus offers",
                "Read PurposeBus next guidance",
                "Read a PurposeBus request",
            ],
        )
        for tool in tools:
            annotations = tool.annotations.model_dump(by_alias=True)
            self.assertTrue(annotations["readOnlyHint"])
            self.assertFalse(annotations["destructiveHint"])
            self.assertTrue(annotations["idempotentHint"])
            self.assertFalse(annotations["openWorldHint"])
            self.assertNotIn("path", tool.input_schema.get("properties", {}))
            self.assertIsNotNone(tool.output_schema)

    def test_collection_bounds_are_part_of_the_tool_schema(self) -> None:
        tools = {tool.name: tool for tool in asyncio.run(create_server(StubGateway()).list_tools())}
        status_limit = tools["purposebus_status"].input_schema["properties"]["limit"]
        self.assertEqual(status_limit["minimum"], 1)
        self.assertEqual(status_limit["maximum"], 1000)
        candidate_limit = tools["purposebus_match"].input_schema["properties"][
            "candidate_limit"
        ]
        self.assertEqual(candidate_limit["minimum"], 1)
        self.assertEqual(candidate_limit["maximum"], 100)

    def test_stdio_client_can_initialize_list_and_call_status(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            partition = root / "partition"
            state_root = root / "state"
            partition.mkdir()
            environment = dict(os.environ)
            environment["XDG_STATE_HOME"] = str(state_root)
            subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "purposebus",
                    "--partition",
                    str(partition),
                    "--format",
                    "json",
                    "init",
                ],
                capture_output=True,
                check=True,
                env=environment,
                text=True,
            )

            async def smoke() -> tuple[str, int, bool, str]:
                parameters = StdioServerParameters(
                    command=sys.executable,
                    args=[
                        "-m",
                        "purposebus_mcp",
                        "--partition",
                        f"project={partition}",
                    ],
                    env={
                        "HOME": str(root / "home"),
                        "PATH": f"{Path(sys.executable).parent}{os.pathsep}{os.defpath}",
                        "XDG_STATE_HOME": str(state_root),
                    },
                )
                async with stdio_client(parameters) as (read_stream, write_stream):
                    async with ClientSession(read_stream, write_stream) as session:
                        initialized = await session.initialize()
                        tools = await session.list_tools()
                        result = await session.call_tool(
                            "purposebus_status", {"partition": "project", "limit": 1}
                        )
                        return (
                            initialized.server_info.name,
                            len(tools.tools),
                            result.is_error,
                            result.structured_content["schema"],
                        )

            self.assertEqual(
                asyncio.run(smoke()),
                ("purposebus-readonly", 6, False, "purposebus.status.v2"),
            )


if __name__ == "__main__":
    unittest.main()
