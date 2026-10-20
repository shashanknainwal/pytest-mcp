import pytest

from pytest_mcp import MCPConnectionError, assert_tool_call, connect, http, stdio
from tests.conftest import CALCULATOR, PYTHON

# Tests that call connect() directly need the marker; mcp_client tests get it automatically.
pytestmark = pytest.mark.anyio


@pytest.mark.mcp_server(stdio(PYTHON, str(CALCULATOR)))
async def test_stdio(mcp_client):
    await assert_tool_call(mcp_client, "add", {"a": 2, "b": 2}, expected=4)


@pytest.mark.mcp_server(f"{PYTHON} {CALCULATOR}")
async def test_stdio_command_string(mcp_client):
    await assert_tool_call(mcp_client, "greet", {"name": "stdio"}, expected="Hello, stdio!")


async def test_http_starts_and_stops_server(free_port):
    target = http(f"http://127.0.0.1:{free_port}/mcp", [PYTHON, str(CALCULATOR), "--http", str(free_port)])
    async with connect(target) as client:
        await assert_tool_call(client, "add", {"a": 40, "b": 2}, expected=42)
        assert "http" in repr(client)


async def test_http_reports_server_that_dies(free_port):
    target = http(f"http://127.0.0.1:{free_port}/mcp", [PYTHON, "-c", "raise SystemExit(3)"])
    with pytest.raises(RuntimeError, match="exited with code 3"):
        async with connect(target):
            pass


async def test_stdio_timeout_on_unresponsive_server():
    # A process that never answers must fail fast, not hang the suite.
    with pytest.raises(MCPConnectionError, match=r"could not connect to stdio: .* timed out"):
        async with connect(stdio(PYTHON, "-c", "import time; time.sleep(30)"), timeout=1):
            pass


async def test_stdio_missing_command():
    with pytest.raises(MCPConnectionError, match="could not connect to stdio: definitely-not-a-real-mcp-server"):
        async with connect(stdio("definitely-not-a-real-mcp-server")):
            pass


def test_stdio_argument_forms():
    assert stdio("python server.py --flag").args == ["server.py", "--flag"]
    assert stdio("python", "server.py").args == ["server.py"]
    assert stdio(["node", "dist/index.js"]).command == "node"
    with pytest.raises(ValueError):
        stdio("")


async def test_rejects_unknown_target():
    with pytest.raises(TypeError, match="got int"):
        async with connect(42):
            pass
