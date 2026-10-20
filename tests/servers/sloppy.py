"""An MCP server with conformance problems, to prove the checks catch them."""

from mcp.server.mcpserver import MCPServer

mcp = MCPServer("sloppy")


@mcp.tool(name="bad name!")
def bad_name() -> str:
    return "ok"


@mcp.tool()
def undocumented(x: int) -> int:
    return x


@mcp.tool()
def silent_failure() -> str:
    """Claims success but returns an error-looking string."""
    return "error: something broke"


if __name__ == "__main__":
    mcp.run()
