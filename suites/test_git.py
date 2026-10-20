"""Test suite for mcp-server-git (modelcontextprotocol/servers, Python).

    pytest suites/test_git.py
    MCP_GIT_SERVER=mcp-server-git pytest suites/test_git.py

The server is locked to one repository with ``--repository``; every test
also checks it cannot be steered into another repo or into git flags.
"""

import subprocess

import pytest

from pytest_mcp import assert_conformance, assert_tool_call, assert_tool_error, result_text, stdio
from suites._command import server_argv


def git(repo, *args):
    return subprocess.run(["git", "-C", str(repo), *args], check=True, capture_output=True, text=True).stdout


def make_repo(path):
    path.mkdir()
    git(path, "init", "-q", "-b", "main")
    git(path, "config", "user.email", "suite@example.com")
    git(path, "config", "user.name", "Suite")
    (path / "README.md").write_text("hello\n")
    git(path, "add", "README.md")
    git(path, "commit", "-q", "-m", "initial commit")
    return path


@pytest.fixture
def repo(tmp_path):
    return make_repo(tmp_path.resolve() / "repo")


@pytest.fixture
def other_repo(tmp_path):
    return make_repo(tmp_path.resolve() / "other")


@pytest.fixture
def mcp_server(repo):
    argv = server_argv("MCP_GIT_SERVER", "uvx mcp-server-git")
    return stdio(*argv, "--repository", str(repo))


async def test_conformance(mcp_client):
    await assert_conformance(mcp_client)


async def test_status_clean(mcp_client, repo):
    await assert_tool_call(mcp_client, "git_status", {"repo_path": str(repo)}, contains="working tree clean")


async def test_add_commit_log_workflow(mcp_client, repo):
    (repo / "README.md").write_text("hello\nworld\n")
    await assert_tool_call(mcp_client, "git_diff_unstaged", {"repo_path": str(repo)}, contains="+world")
    await assert_tool_call(mcp_client, "git_add", {"repo_path": str(repo), "files": ["README.md"]})
    await assert_tool_call(mcp_client, "git_diff_staged", {"repo_path": str(repo)}, contains="+world")
    result = await assert_tool_call(mcp_client, "git_commit", {"repo_path": str(repo), "message": "add world"})
    head = git(repo, "rev-parse", "HEAD").strip()
    assert head in result_text(result)
    log = await assert_tool_call(mcp_client, "git_log", {"repo_path": str(repo), "max_count": 1})
    assert "add world" in result_text(log) and "initial commit" not in result_text(log)


async def test_diff_against_revision(mcp_client, repo):
    (repo / "README.md").write_text("changed\n")
    git(repo, "commit", "-qam", "change")
    await assert_tool_call(mcp_client, "git_diff", {"repo_path": str(repo), "target": "HEAD~1"}, contains="+changed")


async def test_show(mcp_client, repo):
    await assert_tool_call(
        mcp_client, "git_show", {"repo_path": str(repo), "revision": "HEAD"}, contains="initial commit"
    )


async def test_branches(mcp_client, repo):
    await assert_tool_call(mcp_client, "git_create_branch", {"repo_path": str(repo), "branch_name": "feature"})
    await assert_tool_call(mcp_client, "git_checkout", {"repo_path": str(repo), "branch_name": "feature"})
    assert git(repo, "branch", "--show-current").strip() == "feature"
    result = await assert_tool_call(mcp_client, "git_branch", {"repo_path": str(repo), "branch_type": "local"})
    assert result_text(result).splitlines() == ["* feature", "  main"]


async def test_reset_unstages(mcp_client, repo):
    (repo / "README.md").write_text("staged\n")
    git(repo, "add", "README.md")
    await assert_tool_call(mcp_client, "git_reset", {"repo_path": str(repo)})
    assert git(repo, "diff", "--cached") == ""
    assert (repo / "README.md").read_text() == "staged\n"


async def test_checkout_unknown_branch(mcp_client, repo):
    await assert_tool_error(mcp_client, "git_checkout", {"repo_path": str(repo), "branch_name": "no-such-branch"})


async def test_invalid_branch_type(mcp_client, repo):
    await assert_tool_error(mcp_client, "git_branch", {"repo_path": str(repo), "branch_type": "bogus"})


# --- argument injection: values starting with "-" must never reach git as flags.
# --output=<file> makes git write a file anywhere; these tests check nothing is written.

INJECTIONS = {
    "git_diff target": ("git_diff", {"target": "--output={pwned}"}),
    "git_show revision": ("git_show", {"revision": "--output={pwned}"}),
    "git_log start_timestamp": ("git_log", {"start_timestamp": "--output={pwned}"}),
    "git_log end_timestamp": ("git_log", {"end_timestamp": "--output={pwned}"}),
    "git_checkout branch_name": ("git_checkout", {"branch_name": "--orphan=pwned"}),
    "git_create_branch branch_name": ("git_create_branch", {"branch_name": "--help"}),
    "git_create_branch base_branch": ("git_create_branch", {"branch_name": "ok", "base_branch": "--output={pwned}"}),
    "git_branch contains": ("git_branch", {"branch_type": "local", "contains": "--output={pwned}"}),
    "git_branch not_contains": ("git_branch", {"branch_type": "local", "not_contains": "--output={pwned}"}),
}


@pytest.mark.parametrize("injection", INJECTIONS.values(), ids=INJECTIONS.keys())
async def test_flag_injection_is_rejected(mcp_client, repo, tmp_path, injection):
    tool, template = injection
    pwned = tmp_path / "pwned.txt"
    arguments = {"repo_path": str(repo)} | {k: v.format(pwned=pwned) for k, v in template.items()}
    branches_before = git(repo, "branch", "--list")
    await assert_tool_error(mcp_client, tool, arguments)
    assert not pwned.exists()
    assert git(repo, "branch", "--list") == branches_before


# --- repository escapes: the server is pinned to one repo with --repository.


async def test_other_repo_is_denied(mcp_client, other_repo):
    await assert_tool_error(mcp_client, "git_status", {"repo_path": str(other_repo)}, match="outside the allowed")


async def test_dot_dot_escape_is_denied(mcp_client, repo):
    await assert_tool_error(mcp_client, "git_status", {"repo_path": f"{repo}/../other"}, match="outside the allowed")


async def test_symlink_escape_is_denied(mcp_client, repo, other_repo):
    (repo / "link").symlink_to(other_repo, target_is_directory=True)
    await assert_tool_error(mcp_client, "git_status", {"repo_path": str(repo / "link")}, match="outside the allowed")


async def test_commit_in_other_repo_is_denied(mcp_client, other_repo):
    head = git(other_repo, "rev-parse", "HEAD")
    await assert_tool_error(mcp_client, "git_commit", {"repo_path": str(other_repo), "message": "pwned"})
    assert git(other_repo, "rev-parse", "HEAD") == head


async def test_add_outside_repo_is_denied(mcp_client, repo, tmp_path):
    (tmp_path / "outside.txt").write_text("x")
    await assert_tool_error(mcp_client, "git_add", {"repo_path": str(repo), "files": ["../outside.txt"]})
    assert git(repo, "diff", "--cached") == ""
