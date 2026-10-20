"""Testing the official (Node.js) filesystem MCP server with pytest-mcp.

    pip install pytest-mcp
    pytest examples/test_filesystem_server.py

Set MCP_FILESYSTEM_SERVER to use a locally installed binary instead of npx.
"""

import os
import shlex

import pytest

from pytest_mcp import assert_conformance, assert_tool_call, assert_tool_error, assert_tool_exists, stdio

SERVER = os.environ.get("MCP_FILESYSTEM_SERVER", "npx -y @modelcontextprotocol/server-filesystem")


@pytest.fixture
def mcp_server(tmp_path):
    """Run the server against a fresh temporary directory for every test."""
    (tmp_path / "hello.txt").write_text("hello world\n")
    return stdio(*shlex.split(SERVER), str(tmp_path))


async def test_conformance(mcp_client):
    await assert_conformance(mcp_client)


async def test_read_file(mcp_client, tmp_path):
    await assert_tool_exists(mcp_client, "read_text_file")
    path = str(tmp_path / "hello.txt")
    await assert_tool_call(mcp_client, "read_text_file", {"path": path}, expected="hello world\n")


async def test_write_then_list(mcp_client, tmp_path):
    await assert_tool_call(mcp_client, "write_file", {"path": str(tmp_path / "new.txt"), "content": "hi"})
    await assert_tool_call(mcp_client, "list_directory", {"path": str(tmp_path)}, contains="[FILE] new.txt")
    assert (tmp_path / "new.txt").read_text() == "hi"


async def test_refuses_paths_outside_root(mcp_client):
    await assert_tool_error(mcp_client, "read_text_file", {"path": "/etc/passwd"}, match="Access denied")
