"""Assertion helpers for MCP servers.

Every helper is ``async``, takes the ``mcp_client`` fixture (or any
``mcp.Client``) as its first argument, and returns what it fetched so a test
can keep asserting on it.
"""

from __future__ import annotations

import re
from collections.abc import Callable
from typing import Any

from mcp import MCPError
from mcp_types import CallToolResult, GetPromptResult, Prompt, ReadResourceResult, Resource, Tool

from pytest_mcp.client import as_test_client

_MISSING: Any = object()


def result_text(result: CallToolResult | ReadResourceResult | GetPromptResult) -> str:
    """Concatenate every text block in a tool result, resource read or prompt."""
    if isinstance(result, CallToolResult):
        blocks = result.content
    elif isinstance(result, ReadResourceResult):
        blocks = result.contents
    else:
        blocks = [message.content for message in result.messages]
    return "\n".join(block.text for block in blocks if isinstance(getattr(block, "text", None), str))


def _structured_matches(result: CallToolResult, expected: Any) -> bool:
    structured = result.structured_content
    if structured is None:
        return False
    # MCPServer wraps non-object return values as {"result": value}.
    return structured == expected or structured == {"result": expected}


def _describe_result(result: CallToolResult) -> str:
    lines = [f"  is_error: {result.is_error}", f"  text: {result_text(result)!r}"]
    if result.structured_content is not None:
        lines.append(f"  structured_content: {result.structured_content!r}")
    return "\n".join(lines)


async def assert_tool_exists(client: Any, name: str) -> Tool:
    """Fail unless the server lists a tool called ``name``. Returns the ``Tool``."""
    tools = await as_test_client(client).list_all_tools()
    for tool in tools:
        if tool.name == name:
            return tool
    raise AssertionError(f"tool {name!r} not found; server lists: {sorted(t.name for t in tools)}")


async def assert_tool_call(
    client: Any,
    name: str,
    arguments: dict[str, Any] | None = None,
    expected: Any = _MISSING,
    *,
    contains: str | None = None,
    match: str | re.Pattern[str] | None = None,
    check: Callable[[CallToolResult], Any] | None = None,
) -> CallToolResult:
    """Call ``name`` and assert it succeeded and returned what you expect.

    ``expected`` is compared to the structured output when the server sends
    one (a bare value also matches MCPServer's ``{"result": value}`` wrapping),
    otherwise to the concatenated text content. ``contains`` and ``match``
    test the text content; ``check`` receives the raw result and fails the
    assertion if it returns a falsy value other than ``None``.
    """
    try:
        result = await client.call_tool(name, arguments or {})
    except MCPError as exc:
        raise AssertionError(f"tool {name!r} raised a protocol error: {exc}") from exc

    if result.is_error:
        raise AssertionError(f"tool {name!r} returned an error result:\n{_describe_result(result)}")

    text = result_text(result)
    if expected is not _MISSING:
        ok = _structured_matches(result, expected) or (isinstance(expected, str) and text == expected)
        if not ok and result.structured_content is None and not isinstance(expected, str):
            ok = text == str(expected)
        if not ok:
            raise AssertionError(
                f"tool {name!r} returned an unexpected value\n  expected: {expected!r}\n{_describe_result(result)}"
            )
    if contains is not None and contains not in text:
        raise AssertionError(f"tool {name!r} text does not contain {contains!r}\n{_describe_result(result)}")
    if match is not None and not re.search(match, text):
        pattern = match.pattern if isinstance(match, re.Pattern) else match
        raise AssertionError(f"tool {name!r} text does not match /{pattern}/\n{_describe_result(result)}")
    if check is not None:
        verdict = check(result)
        if verdict is not None and not verdict:
            raise AssertionError(f"check {check!r} rejected tool {name!r} result\n{_describe_result(result)}")
    return result


async def assert_tool_error(
    client: Any,
    name: str,
    arguments: dict[str, Any] | None = None,
    *,
    match: str | re.Pattern[str] | None = None,
) -> CallToolResult | MCPError:
    """Assert that calling ``name`` fails *cleanly*.

    A clean failure is either a ``CallToolResult`` with ``is_error=True`` and a
    non-empty text explanation, or a JSON-RPC error. A tool that "succeeds"
    with bad input, or errors with no message, fails this assertion.
    ``match`` is a regex searched in the error message.
    """
    try:
        result = await client.call_tool(name, arguments or {})
    except MCPError as exc:
        message = str(exc)
        if match is not None and not re.search(match, message):
            raise AssertionError(f"tool {name!r} protocol error {message!r} does not match {match!r}") from exc
        return exc

    if not result.is_error:
        raise AssertionError(f"tool {name!r} was expected to fail but succeeded:\n{_describe_result(result)}")
    message = result_text(result)
    if not message.strip():
        raise AssertionError(f"tool {name!r} returned is_error=True with no text explaining the failure")
    if match is not None and not re.search(match, message):
        raise AssertionError(f"tool {name!r} error {message!r} does not match {match!r}")
    return result


async def assert_resource_exists(client: Any, uri: str) -> Resource:
    """Fail unless the server lists a resource at ``uri``. Returns the ``Resource``."""
    resources = await as_test_client(client).list_all_resources()
    for resource in resources:
        if str(resource.uri) == uri:
            return resource
    raise AssertionError(f"resource {uri!r} not found; server lists: {sorted(str(r.uri) for r in resources)}")


async def assert_resource_readable(
    client: Any,
    uri: str,
    *,
    contains: str | None = None,
    mime_type: str | None = None,
) -> ReadResourceResult:
    """Read ``uri`` and assert it returned at least one content block."""
    try:
        result = await client.read_resource(uri)
    except MCPError as exc:
        raise AssertionError(f"reading resource {uri!r} failed: {exc}") from exc
    if not result.contents:
        raise AssertionError(f"resource {uri!r} returned no contents")
    if mime_type is not None:
        found = [content.mime_type for content in result.contents]
        if mime_type not in found:
            raise AssertionError(f"resource {uri!r} has mime types {found}, expected {mime_type!r}")
    if contains is not None and contains not in result_text(result):
        raise AssertionError(f"resource {uri!r} text does not contain {contains!r}: {result_text(result)!r}")
    return result


async def assert_prompt_exists(client: Any, name: str) -> Prompt:
    """Fail unless the server lists a prompt called ``name``. Returns the ``Prompt``."""
    prompts = await as_test_client(client).list_all_prompts()
    for prompt in prompts:
        if prompt.name == name:
            return prompt
    raise AssertionError(f"prompt {name!r} not found; server lists: {sorted(p.name for p in prompts)}")


async def assert_prompt_renders(
    client: Any,
    name: str,
    arguments: dict[str, str] | None = None,
    *,
    contains: str | None = None,
) -> GetPromptResult:
    """Render prompt ``name`` and assert it produced at least one message."""
    try:
        result = await client.get_prompt(name, arguments)
    except MCPError as exc:
        raise AssertionError(f"rendering prompt {name!r} failed: {exc}") from exc
    if not result.messages:
        raise AssertionError(f"prompt {name!r} rendered no messages")
    if contains is not None and contains not in result_text(result):
        raise AssertionError(f"prompt {name!r} text does not contain {contains!r}: {result_text(result)!r}")
    return result
