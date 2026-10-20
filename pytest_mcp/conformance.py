"""Static checks every MCP server should pass, independent of what its tools do."""

from __future__ import annotations

from collections import Counter
from dataclasses import dataclass
from typing import Any, Literal

from jsonschema import Draft202012Validator, SchemaError
from mcp import MCPError
from mcp.shared.tool_name_validation import validate_tool_name
from mcp_types.version import HANDSHAKE_PROTOCOL_VERSIONS, MODERN_PROTOCOL_VERSIONS

from pytest_mcp.client import MCPTestClient, as_test_client

KNOWN_PROTOCOL_VERSIONS: tuple[str, ...] = (*HANDSHAKE_PROTOCOL_VERSIONS, *MODERN_PROTOCOL_VERSIONS)
LATEST_PROTOCOL_VERSION: str = KNOWN_PROTOCOL_VERSIONS[-1]

Severity = Literal["error", "warning"]


@dataclass(frozen=True)
class Issue:
    severity: Severity
    where: str
    message: str

    def __str__(self) -> str:
        return f"[{self.severity}] {self.where}: {self.message}"


def check_protocol_version(client: Any, spec_version: str | None = None) -> list[Issue]:
    """The negotiated version must be one the SDK knows, and ``spec_version`` if given."""
    negotiated = client.protocol_version
    if negotiated not in KNOWN_PROTOCOL_VERSIONS:
        return [Issue("error", "protocol", f"negotiated unknown protocol version {negotiated!r}")]
    if spec_version is not None and negotiated != spec_version:
        return [
            Issue(
                "error",
                "protocol",
                f"server negotiated {negotiated!r} but {spec_version!r} is required "
                f"(the server may not support that spec revision yet)",
            )
        ]
    return []


def _check_schema(where: str, schema: Any, label: str) -> list[Issue]:
    if not isinstance(schema, dict):
        return [Issue("error", where, f"{label} must be a JSON object, got {type(schema).__name__}")]
    issues: list[Issue] = []
    if label == "inputSchema" and schema.get("type") != "object":
        issues.append(Issue("error", where, f'inputSchema must have "type": "object", got {schema.get("type")!r}'))
    try:
        Draft202012Validator.check_schema(schema)
    except SchemaError as exc:
        issues.append(Issue("error", where, f"{label} is not a valid JSON Schema: {exc.message}"))
    return issues


async def check_tools(client: MCPTestClient) -> list[Issue]:
    """Tool names follow SEP-986, are unique, are described, and have valid schemas."""
    tools = await client.list_all_tools()
    issues: list[Issue] = []
    for name, count in Counter(tool.name for tool in tools).items():
        if count > 1:
            issues.append(Issue("error", f"tool {name!r}", f"listed {count} times; tool names must be unique"))
    for tool in tools:
        where = f"tool {tool.name!r}"
        naming = validate_tool_name(tool.name)
        if naming.warnings:
            severity: Severity = "warning" if naming.is_valid else "error"
            issues.append(Issue(severity, where, "name does not follow SEP-986: " + "; ".join(naming.warnings)))
        if not (tool.description or "").strip():
            issues.append(Issue("warning", where, "has no description; models pick tools by their description"))
        issues.extend(_check_schema(where, tool.input_schema, "inputSchema"))
        if tool.output_schema is not None:
            issues.extend(_check_schema(where, tool.output_schema, "outputSchema"))
    return issues


async def check_resources(client: MCPTestClient) -> list[Issue]:
    """Every listed resource can be read and returns content."""
    if client.server_capabilities.resources is None:
        return []
    issues: list[Issue] = []
    for resource in await client.list_all_resources():
        where = f"resource {str(resource.uri)!r}"
        try:
            result = await client.read_resource(str(resource.uri))
        except MCPError as exc:
            issues.append(Issue("error", where, f"is listed but reading it failed: {exc}"))
            continue
        if not result.contents:
            issues.append(Issue("error", where, "is listed but returned no contents"))
    return issues


async def check_prompts(client: MCPTestClient) -> list[Issue]:
    """Prompt names are unique and every argument is named."""
    if client.server_capabilities.prompts is None:
        return []
    prompts = await client.list_all_prompts()
    issues: list[Issue] = []
    for name, count in Counter(prompt.name for prompt in prompts).items():
        if count > 1:
            issues.append(Issue("error", f"prompt {name!r}", f"listed {count} times; prompt names must be unique"))
    for prompt in prompts:
        for argument in prompt.arguments or []:
            if not argument.name.strip():
                issues.append(Issue("error", f"prompt {prompt.name!r}", "has an argument with an empty name"))
    return issues


async def check_conformance(client: MCPTestClient, *, spec_version: str | None = None) -> list[Issue]:
    """Run every check and return all issues found."""
    client = as_test_client(client)
    issues = check_protocol_version(client, spec_version)
    if client.server_capabilities.tools is not None:
        issues += await check_tools(client)
    issues += await check_resources(client)
    issues += await check_prompts(client)
    return issues


def raise_for_issues(issues: list[Issue], *, strict: bool = False) -> None:
    """Fail on errors, and on warnings too when ``strict``."""
    failing = [issue for issue in issues if strict or issue.severity == "error"]
    if failing:
        raise AssertionError(f"{len(failing)} conformance issue(s):\n" + "\n".join(f"  {i}" for i in failing))


async def assert_conformance(
    client: MCPTestClient,
    *,
    spec_version: str | None = None,
    strict: bool = False,
) -> list[Issue]:
    """Fail if the server has conformance errors (or warnings, when ``strict``).

    Returns every issue found, so non-failing warnings can still be inspected.
    """
    issues = await check_conformance(as_test_client(client), spec_version=spec_version)
    raise_for_issues(issues, strict=strict)
    return issues
