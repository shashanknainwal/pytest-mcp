"""The 10-line quick start from the README.

pytest examples/test_calculator_server.py
"""

import pytest

from examples.calculator_server import mcp
from pytest_mcp import assert_tool_call, assert_tool_error

pytestmark = pytest.mark.mcp_server(mcp)  # in-process: no subprocess, no ports


async def test_add(mcp_client):
    await assert_tool_call(mcp_client, "add", {"a": 2, "b": 3}, expected=5)


async def test_divide_by_zero_fails_cleanly(mcp_client):
    await assert_tool_error(mcp_client, "divide", {"a": 1, "b": 0}, match="zero")
