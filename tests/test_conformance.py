import pytest

from pytest_mcp import assert_conformance, check_conformance
from pytest_mcp.conformance import LATEST_PROTOCOL_VERSION
from tests.servers.calculator import mcp as calculator
from tests.servers.sloppy import mcp as sloppy


@pytest.mark.mcp_server(calculator)
async def test_clean_server_passes_strict(mcp_client):
    assert await assert_conformance(mcp_client, strict=True) == []


@pytest.mark.mcp_server(calculator)
async def test_in_process_server_speaks_latest_spec(mcp_client):
    await assert_conformance(mcp_client, spec_version=LATEST_PROTOCOL_VERSION)


@pytest.mark.mcp_server(calculator)
async def test_spec_version_mismatch(mcp_client):
    with pytest.raises(AssertionError, match="negotiated '.*' but '2024-11-05' is required"):
        await assert_conformance(mcp_client, spec_version="2024-11-05")


@pytest.mark.mcp_server(sloppy)
async def test_sloppy_server_issues(mcp_client):
    issues = {str(issue) for issue in await check_conformance(mcp_client)}
    assert any(i.startswith("[error] tool 'bad name!'") for i in issues), issues
    assert "[warning] tool 'undocumented': has no description; models pick tools by their description" in issues


@pytest.mark.mcp_server(sloppy)
async def test_sloppy_server_fails(mcp_client):
    with pytest.raises(AssertionError, match="conformance issue"):
        await assert_conformance(mcp_client)
