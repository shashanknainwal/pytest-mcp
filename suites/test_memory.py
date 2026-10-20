"""Test suite for @modelcontextprotocol/server-memory (knowledge graph).

pytest suites/test_memory.py
MCP_MEMORY_SERVER=mcp-server-memory pytest suites/test_memory.py
"""

import pytest

from pytest_mcp import assert_conformance, assert_tool_call, assert_tool_error, connect, stdio
from suites._command import server_argv

ADA = {"name": "Ada", "entityType": "person", "observations": ["wrote the first program"]}
ENGINE = {"name": "Engine", "entityType": "machine", "observations": []}
PROGRAMMED = {"from": "Ada", "to": "Engine", "relationType": "programmed"}


@pytest.fixture
def memory_file(tmp_path):
    return tmp_path / "memory.jsonl"


@pytest.fixture
def mcp_server(memory_file):
    argv = server_argv("MCP_MEMORY_SERVER", "npx -y @modelcontextprotocol/server-memory")
    return stdio(*argv, env={"MEMORY_FILE_PATH": str(memory_file)})


async def graph(client):
    return (await assert_tool_call(client, "read_graph")).structured_content


async def seed(client):
    await assert_tool_call(client, "create_entities", {"entities": [ADA, ENGINE]})
    await assert_tool_call(client, "create_relations", {"relations": [PROGRAMMED]})


async def test_conformance(mcp_client):
    await assert_conformance(mcp_client)


async def test_starts_empty(mcp_client):
    assert await graph(mcp_client) == {"entities": [], "relations": []}


async def test_create_and_read(mcp_client):
    await seed(mcp_client)
    assert await graph(mcp_client) == {"entities": [ADA, ENGINE], "relations": [PROGRAMMED]}


async def test_duplicate_entity_is_skipped_not_merged(mcp_client):
    await seed(mcp_client)
    duplicate = {**ADA, "observations": ["should not be added"]}
    result = await assert_tool_call(mcp_client, "create_entities", {"entities": [duplicate]})
    assert result.structured_content["skipped"] == ["Ada"]
    assert (await graph(mcp_client))["entities"][0] == ADA


async def test_relation_to_missing_entity_is_an_error(mcp_client):
    await seed(mcp_client)
    ghost = {"from": "Ada", "to": "Ghost", "relationType": "knows"}
    await assert_tool_error(mcp_client, "create_relations", {"relations": [ghost]}, match="Ghost")
    assert (await graph(mcp_client))["relations"] == [PROGRAMMED]


async def test_add_observations_deduplicates(mcp_client):
    await seed(mcp_client)
    new = [{"entityName": "Ada", "contents": ["mathematician", "wrote the first program"]}]
    result = await assert_tool_call(mcp_client, "add_observations", {"observations": new})
    assert result.structured_content["results"] == [{"entityName": "Ada", "addedObservations": ["mathematician"]}]


async def test_add_observations_to_missing_entity(mcp_client):
    await assert_tool_error(
        mcp_client, "add_observations", {"observations": [{"entityName": "Nobody", "contents": ["x"]}]}
    )


async def test_search_is_case_insensitive_and_matches_observations(mcp_client):
    await seed(mcp_client)
    by_observation = await assert_tool_call(mcp_client, "search_nodes", {"query": "FIRST PROGRAM"})
    assert [e["name"] for e in by_observation.structured_content["entities"]] == ["Ada"]
    by_type = await assert_tool_call(mcp_client, "search_nodes", {"query": "machine"})
    assert [e["name"] for e in by_type.structured_content["entities"]] == ["Engine"]


async def test_open_nodes_ignores_unknown_names(mcp_client):
    await seed(mcp_client)
    result = await assert_tool_call(mcp_client, "open_nodes", {"names": ["Ada", "Missing"]})
    assert [e["name"] for e in result.structured_content["entities"]] == ["Ada"]


async def test_delete_observations(mcp_client):
    await seed(mcp_client)
    deletions = [{"entityName": "Ada", "observations": ["wrote the first program"]}]
    await assert_tool_call(mcp_client, "delete_observations", {"deletions": deletions})
    assert (await graph(mcp_client))["entities"][0]["observations"] == []


async def test_delete_entity_removes_its_relations(mcp_client):
    await seed(mcp_client)
    await assert_tool_call(mcp_client, "delete_entities", {"entityNames": ["Engine"]})
    assert await graph(mcp_client) == {"entities": [ADA], "relations": []}


async def test_delete_relations(mcp_client):
    await seed(mcp_client)
    await assert_tool_call(mcp_client, "delete_relations", {"relations": [PROGRAMMED]})
    assert (await graph(mcp_client))["relations"] == []


async def test_graph_survives_restart(mcp_server, memory_file):
    async with connect(mcp_server) as first:
        await seed(first)
    assert memory_file.exists()
    async with connect(mcp_server) as second:
        assert await graph(second) == {"entities": [ADA, ENGINE], "relations": [PROGRAMMED]}
