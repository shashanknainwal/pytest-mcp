# pytest-mcptest

**Test your MCP servers like you test everything else.**

A pytest plugin for [Model Context Protocol](https://modelcontextprotocol.io) servers. It starts your server, connects a client, and gives you fixtures and assertions for tools, resources, and prompts. It works in-process, over stdio, or over Streamable HTTP. It also tests servers written in other languages, such as Node.js or Go, as long as they speak MCP over stdio or HTTP.

```bash
pip install pytest-mcptest
```

The import name is `pytest_mcp`. Requires Python 3.10+ and the official `mcp` SDK 2.x.

## Quick start

```python
# test_server.py
import pytest
from pytest_mcp import assert_tool_call, assert_tool_error

from my_server import mcp  # your MCPServer instance

pytestmark = pytest.mark.mcp_server(mcp)


async def test_add(mcp_client):
    await assert_tool_call(mcp_client, "add", {"a": 2, "b": 3}, expected=5)


async def test_divide_by_zero_fails_cleanly(mcp_client):
    await assert_tool_error(mcp_client, "divide", {"a": 1, "b": 0}, match="zero")
```

```bash
pytest
```

You don't need `@pytest.mark.anyio` or `pytest-asyncio`. Any async test that uses `mcp_client` runs automatically.

## Test any server with zero code

```bash
pytest --pyargs pytest_mcp.suite --mcp-server "python server.py"
pytest --pyargs pytest_mcp.suite --mcp-server "npx -y @modelcontextprotocol/server-filesystem /tmp"
pytest --pyargs pytest_mcp.suite --mcp-server http://localhost:8000/mcp
```

The built-in suite checks these things:

- The handshake completes.
- Tool names follow [SEP-986](https://modelcontextprotocol.io/specification/2025-11-25/server/tools#tool-names) and are unique.
- Every tool is described.
- `inputSchema` and `outputSchema` are valid JSON Schema.
- Every listed resource is readable.
- Prompt names are unique.

### Has your server migrated to the 2026-07-28 spec?

```bash
pytest --pyargs pytest_mcp.suite --mcp-server "python server.py" --mcp-spec-version 2026-07-28
```

The suite fails if the server negotiates an older protocol version. For example, the official filesystem server still speaks `2025-11-25`.

## Pointing at your server

Pick one. They are listed from most specific to least specific.

| Where | Example |
|---|---|
| Marker on a test, class, or module | `@pytest.mark.mcp_server(mcp)` |
| Fixture override in `conftest.py` | `def mcp_server(): return stdio("python", "server.py")` |
| Command line | `pytest --mcp-server "python server.py"` |
| Ini file | `mcp_server = python server.py` under `[pytest]` |

A target can be any of these:

| Target | Transport |
|---|---|
| An `MCPServer` or low-level `Server` instance | In-process (fastest, no subprocess) |
| `stdio("python", "server.py", env={...}, cwd=...)` or `"python server.py"` | stdio subprocess |
| `"http://localhost:8000/mcp"` | Streamable HTTP, already running |
| `http("http://127.0.0.1:8000/mcp", "python server.py --port 8000")` | Streamable HTTP. pytest-mcptest starts the command, waits for the port, and stops the server afterwards |

Per-test setup, such as a fresh temp directory for each test:

```python
@pytest.fixture
def mcp_server(tmp_path):
    return stdio("npx", "-y", "@modelcontextprotocol/server-filesystem", str(tmp_path))
```

## Assertions

Each assertion is `async`, takes `mcp_client` first, and returns what it fetched, so you can keep asserting on the result.

| Assertion | Passes when |
|---|---|
| `assert_tool_exists(c, name)` | The tool is listed. Returns the `Tool`. |
| `assert_tool_call(c, name, args, expected=..., contains=..., match=..., check=...)` | The call succeeds and the result matches. `expected` compares structured output when present, otherwise text. |
| `assert_tool_error(c, name, args, match=...)` | The call fails **cleanly**: `isError` with an explanation, or a JSON-RPC error. |
| `assert_resource_exists(c, uri)` | The resource is listed. |
| `assert_resource_readable(c, uri, contains=..., mime_type=...)` | The read returns content. |
| `assert_prompt_exists(c, name)` | The prompt is listed. |
| `assert_prompt_renders(c, name, args, contains=...)` | The prompt renders at least one message. |
| `assert_conformance(c, spec_version=..., strict=...)` | No conformance errors. With `strict=True`, warnings fail too. |

Failure messages show what the server actually returned:

```text
AssertionError: tool 'add' returned an unexpected value
  expected: 6
  is_error: False
  text: '5'
  structured_content: {'result': 5}
```

`mcp_client` also exposes every `mcp.Client` method (`call_tool`, `read_resource`, `get_prompt`, and so on), plus `call(name, **kwargs)`, `tool_names()`, and `list_all_tools()`, `list_all_resources()`, and `list_all_prompts()`, which follow pagination. Use `result_text(result)` to get the text of any result.

## Fixtures and options

| Fixture | What it is |
|---|---|
| `mcp_client` | A connected `MCPTestClient`, with a fresh connection for each test |
| `mcp_server` | The target. Override it to configure your server |
| `mcp_client_kwargs` | Extra `mcp.Client` arguments, such as `sampling_callback`, `elicitation_callback`, or `mode="legacy"` |
| `mcp_timeout` | Timeout in seconds for each request. Defaults to 30 |
| `mcp_spec_version` | The value of `--mcp-spec-version`, or `None` |

| Option / ini key | Meaning |
|---|---|
| `--mcp-server` / `mcp_server` | The default target |
| `--mcp-timeout` / `mcp_timeout` | The timeout for each request, including the handshake |
| `--mcp-spec-version` / `mcp_spec_version` | The protocol version that the conformance checks require |

Outside pytest, `async with pytest_mcp.connect(target) as client:` gives you the same client.

## GitHub Actions

```yaml
name: test
on: [push, pull_request]
jobs:
  test:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with: { python-version: "3.13" }
      - run: pip install -e . pytest-mcptest
      - run: pytest
      - run: pytest --pyargs pytest_mcp.suite --mcp-server "python server.py"
```

## Tips

- With `MCPServer`, raise `ToolError` (from `mcp.server.mcpserver.exceptions`) for expected failures. The client only sees messages from `ToolError`. Any other exception is masked as `"Error executing tool <name>"`, and `assert_tool_error(..., match=...)` makes that easy to catch.
- Use in-process targets for speed and stdio targets for realism. Run both if you can.

## Roadmap

- **v0.1** (this release): fixtures, assertions, stdio, HTTP, and in-process transports, plus the conformance suite.
- **v0.2**: `mcp-mock`, which adds record/replay and mock MCP servers for testing agents.
- Later: session-scoped clients, tool-description poisoning checks, and Windows CI.

## Contributing

```bash
python -m venv .venv && source .venv/bin/activate
pip install -e ".[dev]"
pytest && ruff check . && ruff format --check .
```

### Releasing

1. Bump `version` in `pyproject.toml` (and `__version__` in `pytest_mcp/__init__.py`), then merge to `main`.
2. Run `git tag v0.1.1 && git push origin v0.1.1`.

The [Release workflow](.github/workflows/release.yml) checks the tag matches the version, runs the tests, builds, and publishes to PyPI with trusted publishing.

MIT licensed.
