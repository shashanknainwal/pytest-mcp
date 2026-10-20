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


if __name__ == "__main__":
    mcp.run()
