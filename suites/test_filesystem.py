"""Test suite for @modelcontextprotocol/server-filesystem.

    pytest suites/test_filesystem.py
    MCP_FILESYSTEM_SERVER=mcp-server-filesystem pytest suites/test_filesystem.py

Each test gets a fresh allowed directory (``root``) next to directories the
server must never touch (``outside`` and a prefix-sibling ``root_evil``).
"""

import json

import pytest

from pytest_mcp import (
    assert_conformance,
    assert_tool_call,
    assert_tool_error,
    result_text,
    stdio,
)
from suites._command import server_argv

# Planted in every file outside the root; it must never appear in a tool result.
SECRET = "SECRET-7f3a9c"


@pytest.fixture
def sandbox(tmp_path):
    # resolve() so macOS's /var -> /private/var symlink doesn't trip the server's own checks.
    base = tmp_path.resolve()
    root = base / "root"
    (root / "sub").mkdir(parents=True)
    (root / "notes.txt").write_text("line1\nline2\nline3\nline4\n")
    (root / "sub" / "deep.md").write_text("# deep\n")
    outside = base / "outside"
    outside.mkdir()
    (outside / "secret.txt").write_text(f"{SECRET}\n")
    # Shares the "root" prefix: a naive startswith() check lets it through (CVE-2025-53110).
    evil = base / "root_evil"
    evil.mkdir()
    (evil / "loot.txt").write_text(f"{SECRET}\n")
    # Symlinks inside the root that point outside it (CVE-2025-53109).
    (root / "link_dir").symlink_to(outside, target_is_directory=True)
    (root / "link_file.txt").symlink_to(outside / "secret.txt")
    return base


@pytest.fixture
def root(sandbox):
    return sandbox / "root"


@pytest.fixture
def mcp_server(root):
    argv = server_argv("MCP_FILESYSTEM_SERVER", "npx -y @modelcontextprotocol/server-filesystem")
    return stdio(*argv, str(root))


async def test_conformance(mcp_client):
    await assert_conformance(mcp_client)


async def test_list_allowed_directories(mcp_client, root):
    await assert_tool_call(mcp_client, "list_allowed_directories", contains=str(root))


# --- reading ---------------------------------------------------------------


async def test_read_text_file(mcp_client, root):
    await assert_tool_call(
        mcp_client, "read_text_file", {"path": str(root / "notes.txt")}, expected="line1\nline2\nline3\nline4\n"
    )


async def test_read_head(mcp_client, root):
    await assert_tool_call(
        mcp_client, "read_text_file", {"path": str(root / "notes.txt"), "head": 2}, expected="line1\nline2"
    )


@pytest.mark.xfail(
    strict=True,
    reason="upstream bug: tail counts the empty string after a trailing newline as a line, so tail=1 returns ''",
)
async def test_read_tail(mcp_client, root):
    result = await assert_tool_call(mcp_client, "read_text_file", {"path": str(root / "notes.txt"), "tail": 1})
    assert result_text(result).strip() == "line4"


async def test_read_tail_without_trailing_newline(mcp_client, root):
    (root / "plain.txt").write_text("a\nb")
    await assert_tool_call(mcp_client, "read_text_file", {"path": str(root / "plain.txt"), "tail": 1}, expected="b")


async def test_read_missing_file(mcp_client, root):
    await assert_tool_error(mcp_client, "read_text_file", {"path": str(root / "missing.txt")}, match="ENOENT")


async def test_read_multiple_files_reports_each_failure(mcp_client, root):
    paths = [str(root / "notes.txt"), str(root / "missing.txt")]
    result = await assert_tool_call(mcp_client, "read_multiple_files", {"paths": paths})
    text = result_text(result)
    assert "line1" in text
    assert "missing.txt: Error" in text


# --- writing ---------------------------------------------------------------


async def test_write_creates_and_overwrites(mcp_client, root):
    target = root / "new.txt"
    await assert_tool_call(mcp_client, "write_file", {"path": str(target), "content": "v1"})
    await assert_tool_call(mcp_client, "write_file", {"path": str(target), "content": "v2"})
    assert target.read_text() == "v2"


async def test_edit_file(mcp_client, root):
    target = root / "notes.txt"
    edits = [{"oldText": "line2", "newText": "LINE2"}]
    await assert_tool_call(mcp_client, "edit_file", {"path": str(target), "edits": edits}, contains="+LINE2")
    assert target.read_text() == "line1\nLINE2\nline3\nline4\n"


async def test_edit_file_dry_run_does_not_write(mcp_client, root):
    target = root / "notes.txt"
    edits = [{"oldText": "line2", "newText": "LINE2"}]
    await assert_tool_call(
        mcp_client, "edit_file", {"path": str(target), "edits": edits, "dryRun": True}, contains="-line2\n+LINE2"
    )
    assert target.read_text() == "line1\nline2\nline3\nline4\n"


async def test_edit_file_without_match_changes_nothing(mcp_client, root):
    target = root / "notes.txt"
    edits = [{"oldText": "line2", "newText": "X"}, {"oldText": "not there", "newText": "Y"}]
    await assert_tool_error(mcp_client, "edit_file", {"path": str(target), "edits": edits}, match="exact match")
    assert target.read_text() == "line1\nline2\nline3\nline4\n"


async def test_create_directory_is_recursive_and_idempotent(mcp_client, root):
    target = root / "a" / "b" / "c"
    await assert_tool_call(mcp_client, "create_directory", {"path": str(target)})
    await assert_tool_call(mcp_client, "create_directory", {"path": str(target)})
    assert target.is_dir()


async def test_move_file(mcp_client, root):
    source, destination = root / "notes.txt", root / "sub" / "moved.txt"
    await assert_tool_call(mcp_client, "move_file", {"source": str(source), "destination": str(destination)})
    assert not source.exists()
    assert destination.read_text().startswith("line1")


async def test_move_file_refuses_to_overwrite(mcp_client, root):
    source, destination = root / "notes.txt", root / "sub" / "deep.md"
    await assert_tool_error(
        mcp_client, "move_file", {"source": str(source), "destination": str(destination)}, match="already exists"
    )
    assert destination.read_text() == "# deep\n"


# --- listing and searching -------------------------------------------------


async def test_list_directory(mcp_client, root):
    result = await assert_tool_call(mcp_client, "list_directory", {"path": str(root)})
    lines = set(result_text(result).splitlines())
    assert {"[FILE] notes.txt", "[DIR] sub"} <= lines


async def test_directory_tree_is_json(mcp_client, root):
    result = await assert_tool_call(mcp_client, "directory_tree", {"path": str(root)})
    tree = {entry["name"]: entry for entry in json.loads(result_text(result))}
    assert tree["notes.txt"]["type"] == "file"
    assert tree["sub"]["type"] == "directory"
    assert [child["name"] for child in tree["sub"]["children"]] == ["deep.md"]


@pytest.mark.parametrize(
    ("pattern", "expected"),
    [("*.txt", {"notes.txt"}), ("**/*.md", {"sub/deep.md"}), ("*.md", set())],
)
async def test_search_files_glob(mcp_client, root, pattern, expected):
    result = await assert_tool_call(mcp_client, "search_files", {"path": str(root), "pattern": pattern})
    text = result_text(result)
    found = set() if text == "No matches found" else {p.removeprefix(f"{root}/") for p in text.splitlines()}
    # link_file.txt also matches *.txt; it's a symlink, covered by the escape tests below.
    assert found - {"link_file.txt"} == expected


async def test_get_file_info(mcp_client, root):
    result = await assert_tool_call(mcp_client, "get_file_info", {"path": str(root / "notes.txt")})
    info = dict(line.split(": ", 1) for line in result_text(result).splitlines())
    assert info["size"] == "24"
    assert info["isFile"] == "true"


# --- sandbox escapes: every attempt must fail AND leave the disk untouched --


ESCAPES = {
    "dot-dot traversal": ("read_text_file", {"path": "{root}/../outside/secret.txt"}),
    "absolute path outside": ("read_text_file", {"path": "{base}/outside/secret.txt"}),
    "prefix sibling (CVE-2025-53110)": ("read_text_file", {"path": "{base}/root_evil/loot.txt"}),
    "symlinked file (CVE-2025-53109)": ("read_text_file", {"path": "{root}/link_file.txt"}),
    "through symlinked dir": ("read_text_file", {"path": "{root}/link_dir/secret.txt"}),
    "list symlinked dir": ("list_directory", {"path": "{root}/link_dir"}),
    "list prefix sibling": ("list_directory", {"path": "{base}/root_evil"}),
    "write outside": ("write_file", {"path": "{base}/outside/pwned.txt", "content": "x"}),
    "write via symlinked dir": ("write_file", {"path": "{root}/link_dir/pwned.txt", "content": "x"}),
    "write prefix sibling": ("write_file", {"path": "{base}/root_evil/pwned.txt", "content": "x"}),
    "overwrite via symlinked file": ("write_file", {"path": "{root}/link_file.txt", "content": "x"}),
    "edit via symlinked file": (
        "edit_file",
        {"path": "{root}/link_file.txt", "edits": [{"oldText": "SECRET", "newText": "x"}]},
    ),
    "mkdir outside": ("create_directory", {"path": "{base}/outside/pwned"}),
    "move file out": ("move_file", {"source": "{root}/notes.txt", "destination": "{base}/outside/pwned.txt"}),
    "move file in": ("move_file", {"source": "{base}/outside/secret.txt", "destination": "{root}/stolen.txt"}),
    "search outside": ("search_files", {"path": "{base}/outside", "pattern": "*"}),
    "info outside": ("get_file_info", {"path": "{base}/outside/secret.txt"}),
}


def _snapshot(base):
    return {str(p.relative_to(base)): p.read_bytes() for p in base.rglob("*") if p.is_file() and not p.is_symlink()}


@pytest.mark.parametrize("escape", ESCAPES.values(), ids=ESCAPES.keys())
async def test_sandbox_escape_is_denied(mcp_client, sandbox, escape):
    tool, template = escape
    filled = json.dumps(template).replace("{root}", str(sandbox / "root")).replace("{base}", str(sandbox))
    arguments = json.loads(filled)
    before = _snapshot(sandbox)
    result = await assert_tool_error(mcp_client, tool, arguments, match="Access denied")
    assert SECRET not in result_text(result)
    assert _snapshot(sandbox) == before
