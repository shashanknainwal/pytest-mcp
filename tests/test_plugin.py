"""End-to-end tests of the plugin as a user would run it."""

import shlex

from tests.conftest import CALCULATOR, PYTHON, SLOPPY

CALC_CMD = shlex.join([PYTHON, str(CALCULATOR)])

TEST_ADD = """
from pytest_mcp import assert_tool_call

async def test_add(mcp_client):
    await assert_tool_call(mcp_client, "add", {"a": 1, "b": 2}, expected=3)
"""


def test_mcp_server_option(pytester):
    pytester.makepyfile(TEST_ADD)
    result = pytester.runpytest_subprocess("--mcp-server", CALC_CMD)
    result.assert_outcomes(passed=1)


def test_mcp_server_ini(pytester):
    pytester.makeini(f"[pytest]\nmcp_server = {CALC_CMD}\n")
    pytester.makepyfile(TEST_ADD)
    pytester.runpytest_subprocess().assert_outcomes(passed=1)


def test_conftest_fixture_override(pytester):
    pytester.makeconftest(
        f"""
        import pytest
        from pytest_mcp import stdio

        @pytest.fixture
        def mcp_server():
            return stdio({PYTHON!r}, {str(CALCULATOR)!r})
        """
    )
    pytester.makepyfile(TEST_ADD)
    pytester.runpytest_subprocess().assert_outcomes(passed=1)


def test_marker_beats_option(pytester):
    pytester.makepyfile(
        f"""
        import pytest
        from pytest_mcp import assert_tool_exists

        @pytest.mark.mcp_server({shlex.join([PYTHON, str(SLOPPY)])!r})
        async def test_sloppy(mcp_client):
            await assert_tool_exists(mcp_client, "undocumented")
        """
    )
    pytester.runpytest_subprocess("--mcp-server", CALC_CMD).assert_outcomes(passed=1)


def test_missing_server_explains_options(pytester):
    pytester.makepyfile(TEST_ADD)
    result = pytester.runpytest_subprocess()
    result.stdout.fnmatch_lines(["*no MCP server configured*", "*--mcp-server*"])
    assert result.ret != 0


def test_suite_passes_for_clean_server(pytester):
    result = pytester.runpytest_subprocess("--pyargs", "pytest_mcp.suite", "--mcp-server", CALC_CMD)
    result.assert_outcomes(passed=5)


def test_suite_flags_sloppy_server(pytester):
    cmd = shlex.join([PYTHON, str(SLOPPY)])
    result = pytester.runpytest_subprocess("--pyargs", "pytest_mcp.suite", "--mcp-server", cmd)
    result.assert_outcomes(passed=4, failed=1)
    result.stdout.fnmatch_lines(["*test_tools*", "*tool 'bad name!'*"])


def test_suite_spec_version(pytester):
    args = ["--pyargs", "pytest_mcp.suite", "--mcp-server", CALC_CMD, "-k", "protocol_version"]
    pytester.runpytest_subprocess(*args, "--mcp-spec-version", "2026-07-28").assert_outcomes(passed=1)
    result = pytester.runpytest_subprocess(*args, "--mcp-spec-version", "2024-11-05")
    result.assert_outcomes(failed=1)
    result.stdout.fnmatch_lines(["*'2024-11-05' is required*"])


def test_timeout_option(pytester):
    pytester.makepyfile(
        """
        def test_timeout(mcp_timeout):
            assert mcp_timeout == 2.5
        """
    )
    pytester.runpytest_subprocess("--mcp-timeout", "2.5").assert_outcomes(passed=1)
