"""Tool errors must reach the client: MCP SDK 2 hides unexpected exception text."""

from __future__ import annotations

import asyncio

import pytest
from mcp.server.mcpserver.exceptions import ToolError

from amazon_ads_mcp.client import AmazonAdsAPIError
from amazon_ads_mcp.server import AmazonAdsMCPServer


def _server() -> AmazonAdsMCPServer:
    mcp = AmazonAdsMCPServer("test")

    @mcp.tool()
    def amazon_ads_refuses(confirm: str = "") -> dict:
        """Refuses unless confirmed."""
        raise ValueError("Pass confirm='ARCHIVE' to proceed.")

    @mcp.tool()
    def amazon_ads_api_fails() -> dict:
        """Fails like the Amazon Ads API."""
        raise AmazonAdsAPIError(403, {"code": "UNAUTHORIZED"})

    @mcp.tool()
    def amazon_ads_leaks() -> dict:
        """Fails with a token in the message."""
        raise RuntimeError("token Atza|should-not-leak")

    @mcp.tool()
    def amazon_ads_crashes() -> dict:
        """Crashes with an unexpected error."""
        raise KeyError("internal detail")

    return mcp


@pytest.mark.parametrize(
    ("tool", "message"),
    [
        ("amazon_ads_refuses", "Pass confirm='ARCHIVE' to proceed."),
        ("amazon_ads_api_fails", "Amazon Ads API error 403"),
    ],
)
def test_expected_errors_keep_their_message(tool: str, message: str) -> None:
    with pytest.raises(ToolError, match=message.split(":")[0]):
        asyncio.run(_server().call_tool(tool, {}))


def test_error_messages_are_redacted() -> None:
    with pytest.raises(ToolError) as exc_info:
        asyncio.run(_server().call_tool("amazon_ads_leaks", {}))
    assert "should-not-leak" not in str(exc_info.value)


def test_unexpected_errors_stay_hidden() -> None:
    with pytest.raises(Exception) as exc_info:
        asyncio.run(_server().call_tool("amazon_ads_crashes", {}))
    assert "internal detail" not in str(exc_info.value)


def test_wrapper_keeps_the_tool_schema() -> None:
    tools = {t.name: t for t in asyncio.run(_server().list_tools())}
    assert "confirm" in tools["amazon_ads_refuses"].input_schema["properties"]
