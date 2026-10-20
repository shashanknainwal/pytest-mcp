"""pytest-mcptest: test your MCP servers like you test everything else."""

from pytest_mcp.assertions import (
    assert_prompt_exists,
    assert_prompt_renders,
    assert_resource_exists,
    assert_resource_readable,
    assert_tool_call,
    assert_tool_error,
    assert_tool_exists,
    result_text,
)
from pytest_mcp.client import MCPConnectionError, MCPTestClient, connect
from pytest_mcp.conformance import Issue, assert_conformance, check_conformance
from pytest_mcp.transport import http, stdio

__version__ = "0.1.1"

__all__ = [
    "Issue",
    "MCPConnectionError",
    "MCPTestClient",
    "assert_conformance",
    "assert_prompt_exists",
    "assert_prompt_renders",
    "assert_resource_exists",
    "assert_resource_readable",
    "assert_tool_call",
    "assert_tool_error",
    "assert_tool_exists",
    "check_conformance",
    "connect",
    "http",
    "result_text",
    "stdio",
]
