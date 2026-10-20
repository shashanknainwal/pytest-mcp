# Real-world suites

Test suites for official [MCP reference servers](https://github.com/modelcontextprotocol/servers), written with pytest-mcptest. They're full examples of testing a real server, and they're meant to be contributed upstream.

| Suite | Server | Tests | What it covers |
|---|---|---|---|
| [`test_filesystem.py`](test_filesystem.py) | `@modelcontextprotocol/server-filesystem` (Node) | 38 | Reading, writing, editing, moving, searching, and 17 sandbox-escape attempts, including regressions for CVE-2025-53109 and CVE-2025-53110 |
| [`test_git.py`](test_git.py) | `mcp-server-git` (Python) | 23 | Status, add, commit, log, diff, and branches, plus 9 flag-injection and 5 repo-escape attempts |
| [`test_memory.py`](test_memory.py) | `@modelcontextprotocol/server-memory` (Node) | 13 | Knowledge-graph CRUD, deduplication, cascading deletes, and persistence across restarts |
| [`test_time.py`](test_time.py) | `mcp-server-time` (Python) | 19 | Current time and conversions, checked against Python's `zoneinfo` (stays correct across DST changes), plus invalid input |

Security tests check two things. The call must fail, **and** the disk must be unchanged afterwards, so a server that reports an error but still writes the file fails the test.

## Run

```bash
pip install pytest-mcptest
pytest suites/                          # uses npx / uvx to launch each server
MCP_FILESYSTEM_SERVER=mcp-server-filesystem pytest suites/test_filesystem.py   # use an installed binary
```

If a server's launcher (`npx` or `uvx`) isn't installed, its suite is skipped.

| Variable | Default |
|---|---|
| `MCP_FILESYSTEM_SERVER` | `npx -y @modelcontextprotocol/server-filesystem` |
| `MCP_MEMORY_SERVER` | `npx -y @modelcontextprotocol/server-memory` |
| `MCP_GIT_SERVER` | `uvx mcp-server-git` |
| `MCP_TIME_SERVER` | `uvx mcp-server-time` |

## Known upstream bugs

These tests are marked `xfail(strict=True)`. They start failing loudly once the bug is fixed, as a reminder to drop the marker.

| Server | Bug |
|---|---|
| filesystem | `read_text_file` with `tail=N` counts the empty string after a trailing newline as a line. `tail=1` returns `""` for any file that ends in `\n`. |
