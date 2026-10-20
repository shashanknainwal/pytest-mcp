"""pytest hooks and fixtures. Registered through the ``pytest11`` entry point."""

from __future__ import annotations

import inspect
from collections.abc import AsyncIterator
from typing import Any

import pytest

from pytest_mcp.client import MCPTestClient, connect
from pytest_mcp.transport import Target, resolve

DEFAULT_TIMEOUT = 30.0


def pytest_addoption(parser: pytest.Parser) -> None:
    group = parser.getgroup("mcp", "MCP server testing")
    group.addoption(
        "--mcp-server",
        dest="mcp_server",
        default=None,
        help="MCP server to test when no test or conftest says otherwise: "
        'a URL (http://localhost:8000/mcp) or a command run over stdio ("python server.py").',
    )
    group.addoption(
        "--mcp-timeout",
        dest="mcp_timeout",
        type=float,
        default=None,
        help=f"Seconds to wait for any single MCP request, including the handshake (default {DEFAULT_TIMEOUT:g}).",
    )
    group.addoption(
        "--mcp-spec-version",
        dest="mcp_spec_version",
        default=None,
        help="Require the server to negotiate this MCP protocol version (e.g. 2026-07-28) in conformance checks.",
    )
    parser.addini("mcp_server", "Default MCP server (URL or stdio command), like --mcp-server.", default=None)
    parser.addini("mcp_timeout", "Default for --mcp-timeout.", default=None)
    parser.addini("mcp_spec_version", "Default for --mcp-spec-version.", default=None)


def pytest_configure(config: pytest.Config) -> None:
    config.addinivalue_line(
        "markers",
        "mcp_server(target): MCP server for this test/class/module: an MCPServer, stdio(...), http(...), "
        "a URL or a command string. Overrides --mcp-server.",
    )


def pytest_collection_modifyitems(items: list[pytest.Item]) -> None:
    """Run async tests that use MCP fixtures under anyio without an explicit marker."""
    for item in items:
        if not isinstance(item, pytest.Function):
            continue
        uses_mcp = "mcp_client" in item.fixturenames or "mcp_server" in item.fixturenames
        if not uses_mcp or not inspect.iscoroutinefunction(item.obj):
            continue
        if item.get_closest_marker("anyio") or item.get_closest_marker("asyncio"):
            continue
        item.add_marker(pytest.mark.anyio)


def _setting(config: pytest.Config, name: str) -> Any:
    value = config.getoption(name)
    return value if value is not None else config.getini(name)


@pytest.fixture
def mcp_timeout(request: pytest.FixtureRequest) -> float:
    """Per-request timeout in seconds, from --mcp-timeout / ``mcp_timeout`` ini."""
    value = _setting(request.config, "mcp_timeout")
    return float(value) if value else DEFAULT_TIMEOUT


@pytest.fixture
def mcp_spec_version(request: pytest.FixtureRequest) -> str | None:
    """Protocol version required by --mcp-spec-version / ``mcp_spec_version`` ini, if any."""
    return _setting(request.config, "mcp_spec_version") or None


@pytest.fixture
def mcp_server(request: pytest.FixtureRequest) -> Target:
    """The MCP server under test.

    Resolved from, in order: the nearest ``@pytest.mark.mcp_server(...)``,
    ``--mcp-server``, then the ``mcp_server`` ini option. Override this
    fixture in ``conftest.py`` to point every test at your server.
    """
    marker = request.node.get_closest_marker("mcp_server")
    if marker is not None:
        if len(marker.args) != 1 or marker.kwargs:
            raise pytest.UsageError("@pytest.mark.mcp_server takes exactly one positional argument")
        return resolve(marker.args[0])
    configured = _setting(request.config, "mcp_server")
    if configured:
        return resolve(configured)
    raise pytest.UsageError(
        "pytest-mcptest: no MCP server configured. Use one of:\n"
        "  - @pytest.mark.mcp_server(my_server) on the test, class or module\n"
        "  - an `mcp_server` fixture in conftest.py returning the server\n"
        '  - pytest --mcp-server "python server.py"  (or a http:// URL)\n'
        "  - mcp_server = ... in the [pytest] ini section"
    )


@pytest.fixture
def mcp_client_kwargs() -> dict[str, Any]:
    """Extra keyword arguments for ``mcp.Client``. Override to add callbacks or pin ``mode``."""
    return {}


@pytest.fixture
async def mcp_client(
    anyio_backend: Any,
    mcp_server: Target,
    mcp_timeout: float,
    mcp_client_kwargs: dict[str, Any],
) -> AsyncIterator[MCPTestClient]:
    """A connected :class:`~pytest_mcp.MCPTestClient`; a fresh connection per test."""
    async with connect(mcp_server, timeout=mcp_timeout, **mcp_client_kwargs) as client:
        yield client
