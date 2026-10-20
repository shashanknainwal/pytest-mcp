# Changelog

## 0.1.1 (2026-10-20)

- Async tests that use only the `mcp_server` fixture (for example, to call `connect()` themselves) now run under anyio automatically, like tests that use `mcp_client`.
- New `suites/`: 93 tests for the official filesystem, git, memory, and time MCP servers. They include sandbox-escape and flag-injection tests based on 2025 CVEs.

## 0.1.0 (2026-10-20)

- First release: `mcp_client` and `mcp_server` fixtures; in-process, stdio, and Streamable HTTP targets; assertion helpers; conformance checks; and the zero-code `pytest_mcp.suite`.
