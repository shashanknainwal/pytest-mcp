"""A thin test-friendly wrapper around ``mcp.Client``."""

from __future__ import annotations

import sys
from collections.abc import AsyncIterator
from contextlib import AsyncExitStack, asynccontextmanager
from typing import Any

from mcp import Client, MCPError
from mcp_types import CallToolResult, Prompt, Resource, Tool

if sys.version_info < (3, 11):
    from exceptiongroup import BaseExceptionGroup

from pytest_mcp.transport import HttpTarget, Target, describe, resolve, running_http_server


class MCPConnectionError(Exception):
    """The server could not be started or did not complete the MCP handshake."""


# Stop walking a paginated listing after this many pages; a server that never
# stops returning cursors should fail the test, not hang it.
_MAX_PAGES = 100


class MCPTestClient:
    """A connected ``mcp.Client`` plus listing helpers.

    Every ``mcp.Client`` method (``call_tool``, ``read_resource``,
    ``get_prompt``, ``list_tools``, ...) is available directly on this object.
    """

    def __init__(self, client: Client, target: Target | None = None) -> None:
        self.client = client
        self.target = target

    def __getattr__(self, name: str) -> Any:
        return getattr(self.client, name)

    def __repr__(self) -> str:
        label = describe(self.target) if self.target is not None else "unknown target"
        return f"<MCPTestClient {label}>"

    async def list_all_tools(self) -> list[Tool]:
        return await _walk(self.client.list_tools, "tools")

    async def list_all_resources(self) -> list[Resource]:
        return await _walk(self.client.list_resources, "resources")

    async def list_all_prompts(self) -> list[Prompt]:
        return await _walk(self.client.list_prompts, "prompts")

    async def tool_names(self) -> list[str]:
        return [tool.name for tool in await self.list_all_tools()]

    async def get_tool(self, name: str) -> Tool | None:
        return next((tool for tool in await self.list_all_tools() if tool.name == name), None)

    async def call(self, name: str, **arguments: Any) -> CallToolResult:
        """``call_tool`` with keyword arguments: ``await mcp_client.call("add", a=1, b=2)``."""
        return await self.client.call_tool(name, arguments)


def as_test_client(client: Any) -> MCPTestClient:
    """Accept either the ``mcp_client`` fixture or a bare ``mcp.Client``."""
    return client if isinstance(client, MCPTestClient) else MCPTestClient(client)


async def _walk(list_method: Any, attr: str) -> list[Any]:
    items: list[Any] = []
    cursor: str | None = None
    for _ in range(_MAX_PAGES):
        page = await list_method(cursor=cursor)
        items.extend(getattr(page, attr))
        cursor = page.next_cursor
        if not cursor:
            return items
    raise AssertionError(f"server returned more than {_MAX_PAGES} pages of {attr}; is its pagination cursor stuck?")


@asynccontextmanager
async def connect(target: Any, *, timeout: float | None = 30.0, **client_kwargs: Any) -> AsyncIterator[MCPTestClient]:
    """Connect to ``target`` and yield an :class:`MCPTestClient`.

    ``timeout`` bounds every request, including the initial handshake.
    Extra keyword arguments go to ``mcp.Client`` (``sampling_callback``,
    ``elicitation_callback``, ``mode``, ...).
    """
    resolved = resolve(target)
    client_kwargs.setdefault("read_timeout_seconds", timeout)
    async with AsyncExitStack() as stack:
        server: Any = resolved
        if isinstance(resolved, HttpTarget):
            server = stack.enter_context(running_http_server(resolved))
        try:
            client = await stack.enter_async_context(Client(server, **client_kwargs))
        except (OSError, BaseExceptionGroup, MCPError) as exc:
            raise MCPConnectionError(f"could not connect to {describe(resolved)}: {_root_cause(exc)}") from exc
        yield MCPTestClient(client, resolved)


def _root_cause(exc: BaseException) -> str:
    """Dig the first real error out of anyio's nested exception groups."""
    while isinstance(exc, BaseExceptionGroup) and exc.exceptions:
        exc = exc.exceptions[0]
    return f"{type(exc).__name__}: {exc}"
