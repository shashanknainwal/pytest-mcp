"""Test suite for mcp-server-time (modelcontextprotocol/servers, Python).

    pytest suites/test_time.py
    MCP_TIME_SERVER=mcp-server-time pytest suites/test_time.py

Expected values come from Python's zoneinfo for today's date, so the suite
stays correct across DST changes.
"""

from datetime import date, datetime, timedelta
from zoneinfo import ZoneInfo

import pytest

from pytest_mcp import assert_conformance, assert_tool_call, assert_tool_error, stdio
from suites._command import server_argv

ZONES = ["UTC", "Asia/Tokyo", "America/New_York", "Asia/Kolkata", "Australia/Adelaide", "Europe/London"]


@pytest.fixture
def mcp_server():
    argv = server_argv("MCP_TIME_SERVER", "uvx mcp-server-time")
    return stdio(*argv, "--local-timezone", "UTC")


async def test_conformance(mcp_client):
    await assert_conformance(mcp_client)


@pytest.mark.parametrize("zone", ZONES)
async def test_get_current_time(mcp_client, zone):
    result = await assert_tool_call(mcp_client, "get_current_time", {"timezone": zone})
    data = result.structured_content
    reported = datetime.fromisoformat(data["datetime"])
    now = datetime.now(ZoneInfo(zone))
    assert data["timezone"] == zone
    assert abs(reported - now) < timedelta(seconds=30)
    assert reported.utcoffset() == now.utcoffset()
    assert data["day_of_week"] == reported.strftime("%A")
    assert data["is_dst"] == bool(now.dst())


@pytest.mark.parametrize(
    ("source", "target"),
    [("America/New_York", "Asia/Kolkata"), ("Europe/London", "Australia/Adelaide"), ("Asia/Tokyo", "UTC")],
)
async def test_convert_time(mcp_client, source, target):
    result = await assert_tool_call(
        mcp_client, "convert_time", {"source_timezone": source, "time": "09:30", "target_timezone": target}
    )
    data = result.structured_content
    today = datetime.now(ZoneInfo(source)).date()
    expected_source = datetime.combine(today, datetime.strptime("09:30", "%H:%M").time(), ZoneInfo(source))
    expected_target = expected_source.astimezone(ZoneInfo(target))
    assert datetime.fromisoformat(data["source"]["datetime"]) == expected_source
    assert datetime.fromisoformat(data["target"]["datetime"]).isoformat() == expected_target.isoformat()
    hours = (expected_target.utcoffset() - expected_source.utcoffset()).total_seconds() / 3600
    assert data["time_difference"] == f"{hours:+.1f}h"


async def test_convert_across_date_line(mcp_client):
    result = await assert_tool_call(
        mcp_client, "convert_time", {"source_timezone": "UTC", "time": "23:00", "target_timezone": "Asia/Tokyo"}
    )
    source_day = date.fromisoformat(result.structured_content["source"]["datetime"][:10])
    target_day = date.fromisoformat(result.structured_content["target"]["datetime"][:10])
    assert target_day - source_day == timedelta(days=1)


@pytest.mark.parametrize("zone", ["Mars/Olympus", "", "EST5EDT; rm -rf /"])
async def test_invalid_timezone(mcp_client, zone):
    await assert_tool_error(mcp_client, "get_current_time", {"timezone": zone}, match="(?i)timezone")


@pytest.mark.parametrize("time", ["25:00", "12:60", "noon", "9:30pm", ""])
async def test_invalid_time_format(mcp_client, time):
    await assert_tool_error(
        mcp_client,
        "convert_time",
        {"source_timezone": "UTC", "time": time, "target_timezone": "UTC"},
        match="HH:MM",
    )
