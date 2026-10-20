"""A small MCP server used to test pytest-mcp itself.

Run directly for stdio, or with ``--http PORT`` for Streamable HTTP.
"""

import sys

from mcp.server.mcpserver import MCPServer
from mcp.server.mcpserver.exceptions import ToolError

mcp = MCPServer("calculator")


@mcp.tool()
def add(a: int, b: int) -> int:
    """Add two integers."""
    return a + b


@mcp.tool()
def divide(a: float, b: float) -> float:
    """Divide a by b."""
    if b == 0:
        # ToolError's message reaches the client; any other exception is masked as a crash.
        raise ToolError("cannot divide by zero")
    return a / b


@mcp.tool()
def greet(name: str) -> str:
    """Say hello."""
    return f"Hello, {name}!"


@mcp.resource("config://calculator")
def config() -> str:
    """Calculator settings."""
    return "precision=2"


@mcp.prompt()
def explain(expression: str) -> str:
    """Ask the model to explain an expression."""
    return f"Explain step by step: {expression}"


if __name__ == "__main__":
    if len(sys.argv) == 3 and sys.argv[1] == "--http":
        mcp.run("streamable-http", port=int(sys.argv[2]))
    else:
        mcp.run()
