from __future__ import annotations

import argparse
from typing import Annotated, Any

from mcp.server.mcpserver import MCPServer
from mcp.server.mcpserver.exceptions import ToolError
from mcp.types import ToolAnnotations
from pydantic import Field

from .cli_adapter import PurposeBusCliGateway, PurposeBusGatewayError
from .config import ConfigurationError, parse_bindings


READ_ONLY_ANNOTATIONS = ToolAnnotations(
    readOnlyHint=True,
    destructiveHint=False,
    idempotentHint=True,
    openWorldHint=False,
)
CollectionLimit = Annotated[int, Field(ge=1, le=1000)]
CandidateLimit = Annotated[int, Field(ge=1, le=100)]
PartitionAlias = Annotated[str, Field(pattern=r"^[a-z][a-z0-9_-]{0,63}$")]
PurposeBusIdentifier = Annotated[
    str, Field(min_length=1, max_length=128, pattern=r"^[A-Za-z][A-Za-z0-9._:-]{0,127}$")
]


def create_server(gateway: PurposeBusCliGateway) -> MCPServer:
    server = MCPServer(
        name="purposebus-readonly",
        title="PurposeBus Local Read-only Gateway",
        description="Read-only PurposeBus discovery and guidance over its public CLI.",
        instructions=(
            "Use only configured Partition aliases. Results are observations and guidance, "
            "not authority to mutate PurposeBus, launch an agent, or perform recommended work."
        ),
        version="0.1.0a0",
    )

    def call(operation, *args, **kwargs) -> dict[str, Any]:
        try:
            return operation(*args, **kwargs)
        except PurposeBusGatewayError as exc:
            raise ToolError(str(exc)) from exc

    @server.tool(
        name="purposebus_status",
        title="Read PurposeBus status",
        description="Read bounded health, counts, and Instance status for one configured Partition.",
        annotations=READ_ONLY_ANNOTATIONS,
        structured_output=True,
    )
    def purposebus_status(
        partition: PartitionAlias, limit: CollectionLimit = 100
    ) -> dict[str, Any]:
        return call(gateway.status, partition, limit=limit)

    @server.tool(
        name="purposebus_list_agents",
        title="List PurposeBus agents",
        description="List registered Agents in one configured Partition without changing state.",
        annotations=READ_ONLY_ANNOTATIONS,
        structured_output=True,
    )
    def purposebus_list_agents(
        partition: PartitionAlias, limit: CollectionLimit = 100
    ) -> dict[str, Any]:
        return call(gateway.list_agents, partition, limit=limit)

    @server.tool(
        name="purposebus_list_instances",
        title="List PurposeBus agent instances",
        description="List Agent Instances in one configured Partition without changing state.",
        annotations=READ_ONLY_ANNOTATIONS,
        structured_output=True,
    )
    def purposebus_list_instances(
        partition: PartitionAlias, limit: CollectionLimit = 100
    ) -> dict[str, Any]:
        return call(gateway.list_instances, partition, limit=limit)

    @server.tool(
        name="purposebus_match",
        title="Match PurposeBus offers",
        description="Read bounded Offer matches and unmet demand in one configured Partition.",
        annotations=READ_ONLY_ANNOTATIONS,
        structured_output=True,
    )
    def purposebus_match(
        partition: PartitionAlias,
        limit: CollectionLimit = 100,
        candidate_limit: CandidateLimit = 25,
    ) -> dict[str, Any]:
        return call(gateway.match, partition, limit=limit, candidate_limit=candidate_limit)

    @server.tool(
        name="purposebus_next",
        title="Read PurposeBus next guidance",
        description=(
            "Read bounded next-action guidance for an existing Instance; guidance grants no authority."
        ),
        annotations=READ_ONLY_ANNOTATIONS,
        structured_output=True,
    )
    def purposebus_next(
        partition: PartitionAlias,
        instance_id: PurposeBusIdentifier,
        limit: CollectionLimit = 100,
    ) -> dict[str, Any]:
        return call(gateway.next, partition, instance_id, limit=limit)

    @server.tool(
        name="purposebus_get_request",
        title="Read a PurposeBus request",
        description="Read one Request by exact ID in one configured Partition.",
        annotations=READ_ONLY_ANNOTATIONS,
        structured_output=True,
    )
    def purposebus_get_request(
        partition: PartitionAlias, request_id: PurposeBusIdentifier
    ) -> dict[str, Any]:
        return call(gateway.get_request, partition, request_id)

    return server


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="purposebus-mcp",
        description="Expose an allowlisted read-only PurposeBus MCP server over stdio.",
    )
    parser.add_argument(
        "--partition",
        action="append",
        required=True,
        metavar="ALIAS=/ABSOLUTE/PATH",
        help="bind one tool-visible alias to one local PurposeBus Partition",
    )
    parser.add_argument(
        "--timeout",
        type=float,
        default=10.0,
        help="maximum seconds for one PurposeBus CLI invocation (default: 10)",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    try:
        bindings = parse_bindings(args.partition)
        gateway = PurposeBusCliGateway(bindings, timeout_seconds=args.timeout)
        gateway.check_version()
    except (ConfigurationError, PurposeBusGatewayError) as exc:
        parser.error(str(exc))
    create_server(gateway).run(transport="stdio")
    return 0
