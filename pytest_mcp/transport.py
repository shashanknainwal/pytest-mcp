"""Describe *what* to test: an in-process server, a stdio command, or an HTTP URL."""

from __future__ import annotations

import os
import shlex
import socket
import subprocess
import time
from collections.abc import Iterator, Mapping, Sequence
from contextlib import contextmanager
from dataclasses import dataclass
from pathlib import Path
from typing import Any
from urllib.parse import urlsplit

from mcp import StdioServerParameters
from mcp.server import Server
from mcp.server.mcpserver import MCPServer


@dataclass(frozen=True)
class HttpTarget:
    """An MCP server reachable over Streamable HTTP.

    When ``command`` is set, pytest-mcp starts it before connecting, waits for
    the URL's port to accept connections, and stops it after the test.
    """

    url: str
    command: tuple[str, ...] | None = None
    env: Mapping[str, str] | None = None
    cwd: str | Path | None = None
    startup_timeout: float = 15.0


Target = MCPServer | Server | StdioServerParameters | HttpTarget | str
"""Anything the ``mcp_server`` fixture may return.

A ``str`` is a URL when it starts with ``http://`` or ``https://``; otherwise
it is a shell-style command launched over stdio (``"python server.py"``).
"""


def stdio(
    command: str | Sequence[str],
    *args: str,
    env: Mapping[str, str] | None = None,
    cwd: str | Path | None = None,
) -> StdioServerParameters:
    """Launch ``command`` as a subprocess and talk MCP over its stdin/stdout.

    ``stdio("python", "server.py")``, ``stdio(["python", "server.py"])`` and
    ``stdio("python server.py")`` are equivalent.
    """
    if isinstance(command, str):
        argv = [command, *args] if args else shlex.split(command)
    else:
        argv = [*command, *args]
    if not argv:
        raise ValueError("stdio() needs a command to run")
    return StdioServerParameters(
        command=argv[0],
        args=argv[1:],
        env=dict(env) if env is not None else None,
        cwd=cwd,
    )


def http(
    url: str,
    command: str | Sequence[str] | None = None,
    *,
    env: Mapping[str, str] | None = None,
    cwd: str | Path | None = None,
    startup_timeout: float = 15.0,
) -> HttpTarget:
    """Connect over Streamable HTTP, optionally starting the server first."""
    if command is not None and isinstance(command, str):
        command = shlex.split(command)
    return HttpTarget(
        url=url,
        command=tuple(command) if command is not None else None,
        env=env,
        cwd=cwd,
        startup_timeout=startup_timeout,
    )


def resolve(target: Any) -> Target:
    """Normalise a user-supplied target, rejecting anything we cannot connect to."""
    if isinstance(target, str):
        if target.startswith(("http://", "https://")):
            return target
        return stdio(target)
    if isinstance(target, (MCPServer, Server, StdioServerParameters, HttpTarget)):
        return target
    raise TypeError(
        "mcp_server must be an MCPServer/Server instance, stdio(...), http(...), "
        f"a URL or a command string; got {type(target).__name__}"
    )


def describe(target: Target) -> str:
    """Human-readable label for failure messages."""
    if isinstance(target, MCPServer):
        return f"in-process MCPServer {target.name!r}"
    if isinstance(target, Server):
        return f"in-process Server {target.name!r}"
    if isinstance(target, StdioServerParameters):
        return "stdio: " + shlex.join([target.command, *target.args])
    if isinstance(target, HttpTarget):
        return f"http: {target.url}"
    return f"http: {target}"


def _wait_for_port(url: str, proc: subprocess.Popen[bytes], timeout: float) -> None:
    parts = urlsplit(url)
    host = parts.hostname or "127.0.0.1"
    port = parts.port or (443 if parts.scheme == "https" else 80)
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if proc.poll() is not None:
            raise RuntimeError(f"MCP server exited with code {proc.returncode} before {url} became reachable")
        try:
            with socket.create_connection((host, port), timeout=0.25):
                return
        except OSError:
            time.sleep(0.1)
    raise TimeoutError(f"MCP server did not start listening on {host}:{port} within {timeout}s")


@contextmanager
def running_http_server(target: HttpTarget) -> Iterator[str]:
    """Start ``target.command`` (if any) and yield the URL to connect to."""
    if target.command is None:
        yield target.url
        return
    env = {**os.environ, **(target.env or {})}
    # Inherit stdout/stderr so pytest's fd-level capture shows server output on failure.
    proc = subprocess.Popen(list(target.command), env=env, cwd=target.cwd)
    try:
        _wait_for_port(target.url, proc, target.startup_timeout)
        yield target.url
    finally:
        proc.terminate()
        try:
            proc.wait(timeout=5)
        except subprocess.TimeoutExpired:
            proc.kill()
            proc.wait()
