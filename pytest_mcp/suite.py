"""Ready-made conformance tests for any MCP server, no test code required.

pytest --pyargs pytest_mcp.suite --mcp-server "python server.py"
pytest --pyargs pytest_mcp.suite --mcp-server "npx -y @modelcontextprotocol/server-everything"
pytest --pyargs pytest_mcp.suite --mcp-server http://localhost:8000/mcp --mcp-spec-version 2026-07-28
"""

from __future__ import annotations

import pytest

from pytest_mcp.client import MCPTestClient
from pytest_mcp.conformance import (
    check_prompts,
    check_protocol_version,
    check_resources,
    check_tools,
    raise_for_issues,
)


async def test_handshake(mcp_client: MCPTestClient) -> None:
    # Ping is gone as of 2026-07-28, so a completed handshake is the liveness check.
    assert mcp_client.protocol_version
    assert mcp_client.server_capabilities is not None


async def test_protocol_version(mcp_client: MCPTestClient, mcp_spec_version: str | None) -> None:
    raise_for_issues(check_protocol_version(mcp_client, mcp_spec_version))


async def test_tools(mcp_client: MCPTestClient) -> None:
    if mcp_client.server_capabilities.tools is None:
        pytest.skip("server does not advertise tools")
    raise_for_issues(await check_tools(mcp_client))


async def test_resources(mcp_client: MCPTestClient) -> None:
    if mcp_client.server_capabilities.resources is None:
        pytest.skip("server does not advertise resources")
    raise_for_issues(await check_resources(mcp_client))


async def test_prompts(mcp_client: MCPTestClient) -> None:
    if mcp_client.server_capabilities.prompts is None:
        pytest.skip("server does not advertise prompts")
    raise_for_issues(await check_prompts(mcp_client))
