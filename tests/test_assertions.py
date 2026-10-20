import pytest

from pytest_mcp import (
    assert_prompt_exists,
    assert_prompt_renders,
    assert_resource_exists,
    assert_resource_readable,
    assert_tool_call,
    assert_tool_error,
    assert_tool_exists,
    result_text,
)
from tests.servers.calculator import mcp as calculator

pytestmark = pytest.mark.mcp_server(calculator)


async def test_tool_exists(mcp_client):
    tool = await assert_tool_exists(mcp_client, "add")
    assert tool.description == "Add two integers."


async def test_tool_exists_fails_with_listing(mcp_client):
    with pytest.raises(AssertionError, match=r"'subtract' not found; server lists: \['add', 'divide', 'greet'\]"):
        await assert_tool_exists(mcp_client, "subtract")


async def test_tool_call_structured(mcp_client):
    result = await assert_tool_call(mcp_client, "add", {"a": 2, "b": 3}, expected=5)
    assert result.structured_content == {"result": 5}


async def test_tool_call_text(mcp_client):
    await assert_tool_call(mcp_client, "greet", {"name": "Ada"}, expected="Hello, Ada!")
    await assert_tool_call(mcp_client, "greet", {"name": "Ada"}, contains="Ada", match=r"^Hello")


async def test_tool_call_check(mcp_client):
    quarter = lambda r: r.structured_content["result"] == 0.25  # noqa: E731
    await assert_tool_call(mcp_client, "divide", {"a": 1, "b": 4}, check=quarter)
    with pytest.raises(AssertionError, match="rejected"):
        await assert_tool_call(mcp_client, "divide", {"a": 1, "b": 4}, check=lambda r: False)


async def test_tool_call_wrong_value(mcp_client):
    with pytest.raises(AssertionError, match=r"unexpected value\n  expected: 6"):
        await assert_tool_call(mcp_client, "add", {"a": 2, "b": 3}, expected=6)


async def test_tool_call_reports_error_result(mcp_client):
    with pytest.raises(AssertionError, match="returned an error result"):
        await assert_tool_call(mcp_client, "divide", {"a": 1, "b": 0})


async def test_tool_error(mcp_client):
    result = await assert_tool_error(mcp_client, "divide", {"a": 1, "b": 0}, match="cannot divide by zero")
    assert result.is_error


async def test_tool_error_on_unknown_tool(mcp_client):
    await assert_tool_error(mcp_client, "nope", match="Unknown tool")


async def test_tool_error_fails_when_tool_succeeds(mcp_client):
    with pytest.raises(AssertionError, match="expected to fail but succeeded"):
        await assert_tool_error(mcp_client, "add", {"a": 1, "b": 1})


async def test_call_shorthand(mcp_client):
    assert result_text(await mcp_client.call("add", a=1, b=1)) == "2"


async def test_resources(mcp_client):
    await assert_resource_exists(mcp_client, "config://calculator")
    await assert_resource_readable(mcp_client, "config://calculator", contains="precision", mime_type="text/plain")
    with pytest.raises(AssertionError, match="reading resource 'config://missing' failed"):
        await assert_resource_readable(mcp_client, "config://missing")


async def test_prompts(mcp_client):
    prompt = await assert_prompt_exists(mcp_client, "explain")
    assert [a.name for a in prompt.arguments] == ["expression"]
    await assert_prompt_renders(mcp_client, "explain", {"expression": "1+1"}, contains="1+1")
    with pytest.raises(AssertionError, match="prompt 'missing' not found"):
        await assert_prompt_exists(mcp_client, "missing")


@pytest.mark.parametrize(("a", "b", "total"), [(1, 1, 2), (-1, 1, 0), (10**6, 1, 10**6 + 1)])
async def test_parametrized(mcp_client, a, b, total):
    await assert_tool_call(mcp_client, "add", {"a": a, "b": b}, expected=total)
