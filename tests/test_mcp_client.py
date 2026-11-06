"""End-to-end tests through `mcp.Client` against the real server (fake auth, mocked HTTP)."""

from __future__ import annotations

import dataclasses
import json
from pathlib import Path
from typing import Any

import httpx
import pytest
import respx
from mcp import Client
from mcp.server.mcpserver import MCPServer
from mcp.types import Tool

from amazon_ads_mcp import __version__, server, tools
from amazon_ads_mcp.client import AmazonAdsClient
from amazon_ads_mcp.config import Config, load_config
from amazon_ads_mcp.tool_catalog import ALWAYS_REGISTERED, TOOL_SPECS

from .conftest import BASE, FakeAuth

META_TOOLS = [
    "amazon_ads_describe_server",
    "amazon_ads_health_check",
    "amazon_ads_audit_lookup",
    "amazon_ads_audit_tail",
    "amazon_ads_set_dry_run",
]
EXPECTED_TOOL_COUNT = 100


@pytest.fixture(autouse=True)
def _fake_auth(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(server, "load_auth", lambda config: FakeAuth())


def _build(config: Config, **changes: Any) -> MCPServer:
    return server.build_server(dataclasses.replace(config, **changes))


async def _tools(mcp: MCPServer) -> list[Tool]:
    async with Client(mcp) as c:
        return (await c.list_tools()).tools


def _group_tool_names(client: AmazonAdsClient) -> dict[str, list[str]]:
    """Tool names per group, by registering each module on its own server."""
    out: dict[str, list[str]] = {}
    for group in tools.TOOL_GROUPS:
        mcp = MCPServer("probe")
        getattr(tools, group).register(mcp, client)
        out[group] = list(mcp._tool_manager._tools)
    return out


# ---------------------------------------------------------------- metadata


async def test_server_reports_version_and_instructions(config: Config) -> None:
    async with Client(_build(config)) as c:
        assert c.server_info is not None
        assert c.server_info.name == "amazon-ads-mcp"
        assert c.server_info.version == __version__
        assert c.instructions
        assert "amazon_ads_describe_server" in c.instructions
        assert "dry-run" in c.instructions
        assert "AMAZON_ADS_TOOL_GROUPS" in c.instructions
        assert "other ad platforms" in c.instructions
        assert 4 <= len(c.instructions.splitlines()) <= 8


async def test_every_tool_has_a_catalog_entry(config: Config) -> None:
    listed = await _tools(_build(config))
    assert len(listed) == EXPECTED_TOOL_COUNT
    for tool in listed:
        assert tool.name.startswith("amazon_ads_"), tool.name
        assert tool.name in TOOL_SPECS, f"{tool.name} has no tool_catalog entry"
        assert tool.title, tool.name
        assert tool.title[0].isupper(), tool.name
        assert tool.description, tool.name
        a = tool.annotations
        assert a is not None, tool.name
        assert a.read_only_hint is not None, tool.name
        assert a.destructive_hint is not None, tool.name
        assert a.idempotent_hint is not None, tool.name
        assert a.open_world_hint is not None, tool.name
    # The catalog has no stale entries either.
    assert {t.name for t in listed} == set(TOOL_SPECS)


async def test_annotations_are_plausible(config: Config) -> None:
    by_name = {t.name: t.annotations for t in await _tools(_build(config))}
    read_only = {n for n, a in by_name.items() if a and a.read_only_hint}
    destructive = {n for n, a in by_name.items() if a and a.destructive_hint}
    assert not read_only & destructive
    for name in by_name:
        verb_part = name.removeprefix("amazon_ads_")
        for pfx in ("sp_", "sb_", "sd_", "v1_"):
            verb_part = verb_part.removeprefix(pfx)
        verb = verb_part.split("_")[0]
        if verb in {"list", "get", "query", "download"}:
            assert name in read_only, name
        if verb in {"archive", "delete", "detach"}:
            assert name in destructive, name
        if verb in {"create", "update", "adjust", "set", "attach"} and name not in {
            "amazon_ads_create_report",
            "amazon_ads_set_dry_run",
        }:
            assert name not in read_only, name
    assert "amazon_ads_request" in destructive
    assert {"amazon_ads_run_report", "amazon_ads_read_request"} <= read_only
    closed = {n for n, a in by_name.items() if a and a.open_world_hint is False}
    assert closed == set(META_TOOLS) - {"amazon_ads_health_check"}


async def test_tools_list_order_is_deterministic(config: Config, client: AmazonAdsClient) -> None:
    first = [t.name for t in await _tools(_build(config))]
    second = [t.name for t in await _tools(_build(config))]
    assert first == second
    per_group = _group_tool_names(client)
    expected = META_TOOLS + [n for g in tools.TOOL_GROUPS for n in per_group[g]]
    assert first == expected


# ---------------------------------------------------------------- filtering


async def test_tool_groups_limit_registration(config: Config, client: AmazonAdsClient) -> None:
    names = [t.name for t in await _tools(_build(config, tool_groups=["reporting", "profiles"]))]
    per_group = _group_tool_names(client)
    assert names == META_TOOLS + per_group["profiles"] + per_group["reporting"]


async def test_read_only_registers_only_read_tools(config: Config) -> None:
    listed = await _tools(_build(config, read_only=True))
    names = {t.name for t in listed}
    assert set(META_TOOLS) <= names
    for tool in listed:
        if tool.name not in ALWAYS_REGISTERED:
            assert tool.annotations and tool.annotations.read_only_hint, tool.name
    assert "amazon_ads_sp_update_campaigns" not in names
    assert "amazon_ads_request" not in names
    assert "amazon_ads_sp_list_campaigns" in names
    assert "amazon_ads_run_report" in names
    expected = {n for n, s in TOOL_SPECS.items() if s.annotations.read_only_hint}
    assert names == expected | set(META_TOOLS)


async def test_read_only_combines_with_groups(config: Config) -> None:
    names = {t.name for t in await _tools(_build(config, tool_groups=["bulk"], read_only=True))}
    assert names == set(META_TOOLS)


def _env(monkeypatch: pytest.MonkeyPatch, tmp_path: Path, **values: str) -> Path:
    monkeypatch.setenv("AMAZON_ADS_CLIENT_ID", "amzn1.application-oa2-client.x")
    monkeypatch.setenv("AMAZON_ADS_CLIENT_SECRET", "secret-for-tests")
    monkeypatch.setenv("AMAZON_ADS_REFRESH_TOKEN", "Atzr|test")
    monkeypatch.setenv("AMAZON_ADS_AUDIT_LOG", str(tmp_path / "audit.jsonl"))
    monkeypatch.setenv("AMAZON_ADS_TOKEN_FILE", str(tmp_path / "token.json"))
    for var in (
        "AMAZON_ADS_PROFILE_ID",
        "AMAZON_ADS_TOOL_GROUPS",
        "AMAZON_ADS_READ_ONLY",
        "AMAZON_ADS_REGION",
        "AMAZON_ADS_DRY_RUN",
    ):
        monkeypatch.delenv(var, raising=False)
    for k, v in values.items():
        monkeypatch.setenv(k, v)
    return tmp_path / "missing.env"


async def test_env_vars_filter_tools(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    env_file = _env(
        monkeypatch,
        tmp_path,
        AMAZON_ADS_TOOL_GROUPS="profiles,portfolios",
        AMAZON_ADS_READ_ONLY="1",
    )
    names = {t.name for t in await _tools(server.build_server(env_file=env_file))}
    assert names == set(META_TOOLS) | {
        "amazon_ads_list_profiles",
        "amazon_ads_get_profile",
        "amazon_ads_list_manager_accounts",
        "amazon_ads_list_portfolios",
    }


def test_unknown_group_fails_at_startup(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    env_file = _env(monkeypatch, tmp_path, AMAZON_ADS_TOOL_GROUPS="profiles,nope")
    with pytest.raises(RuntimeError) as exc_info:
        server.build_server(env_file=env_file)
    message = str(exc_info.value)
    assert "nope" in message
    for group in tools.TOOL_GROUPS:
        assert group in message


def test_load_config_normalises_group_names(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    env_file = _env(monkeypatch, tmp_path, AMAZON_ADS_TOOL_GROUPS="Reporting, sp-campaigns")
    assert load_config(env_file=env_file).tool_groups == ["sp_campaigns", "reporting"]


# ---------------------------------------------------------------- calls


@respx.mock
async def test_api_error_reaches_the_client(config: Config) -> None:
    respx.post(f"{BASE}/sp/campaigns/list").mock(
        return_value=httpx.Response(403, json={"code": "UNAUTHORIZED", "details": "Not authorized"})
    )
    async with Client(_build(config)) as c:
        result = await c.call_tool("amazon_ads_sp_list_campaigns", {})
    assert result.is_error
    text = " ".join(getattr(block, "text", "") for block in result.content)
    assert "Amazon Ads API error 403" in text
    assert "UNAUTHORIZED" in text


async def test_describe_server_reports_settings(config: Config) -> None:
    async with Client(_build(config, tool_groups=["reporting"], read_only=True)) as c:
        result = await c.call_tool("amazon_ads_describe_server", {})
    payload = result.structured_content or json.loads(result.content[0].text)
    assert payload["tool_groups"] == ["reporting"]
    assert payload["read_only"] is True
    assert payload["region"] == "EU"
    assert payload["api_host"] == BASE
    assert payload["version"] == __version__
    assert "secret" not in json.dumps(payload).lower()


@respx.mock
async def test_health_check_refreshes_and_lists_profiles(config: Config) -> None:
    respx.get(f"{BASE}/v2/profiles").mock(
        return_value=httpx.Response(
            200,
            json=[
                {
                    "profileId": int(config.profile_id or 0),
                    "countryCode": "UK",
                    "accountInfo": {"name": "Shop", "type": "seller"},
                }
            ],
        )
    )
    async with Client(_build(config)) as c:
        result = await c.call_tool("amazon_ads_health_check", {})
    payload = result.structured_content or json.loads(result.content[0].text)
    assert payload["ok"] is True
    assert [c["check"] for c in payload["checks"]] == [
        "token_refresh",
        "list_profiles",
        "default_profile_visible",
    ]
    assert payload["profiles"][0]["countryCode"] == "UK"


async def test_set_dry_run_and_audit_tail(config: Config) -> None:
    with respx.mock(assert_all_called=False) as router:
        router.post(f"{BASE}/sp/campaigns").mock(return_value=httpx.Response(207, json={}))
        async with Client(_build(config)) as c:
            await c.call_tool("amazon_ads_set_dry_run", {"enabled": True})
            created = await c.call_tool(
                "amazon_ads_sp_create_campaigns",
                {
                    "items": [
                        {
                            "name": "x",
                            "state": "PAUSED",
                            "targetingType": "AUTO",
                            "budget": {"budget": 5, "budgetType": "DAILY"},
                        }
                    ]
                },
            )
            tail = await c.call_tool("amazon_ads_audit_tail", {"limit": 5})
            lookup_id = json.loads(created.content[0].text)["audit_id"]
            found = await c.call_tool("amazon_ads_audit_lookup", {"audit_id": lookup_id})
    assert json.loads(created.content[0].text)["_dry_run"] is True
    assert json.loads(tail.content[0].text)["count"] == 1
    assert json.loads(found.content[0].text)["found"] is True


def test_version_matches_pyproject() -> None:
    root = Path(__file__).resolve().parent.parent
    pyproject = (root / "pyproject.toml").read_text(encoding="utf-8")
    assert f'\nversion = "{__version__}"\n' in pyproject


def test_docs_list_every_tool() -> None:
    root = Path(__file__).resolve().parent.parent
    docs = (root / "docs" / "tools.md").read_text(encoding="utf-8")
    missing = [name for name in TOOL_SPECS if f"`{name}`" not in docs]
    assert not missing, f"docs/tools.md is missing {missing}"
    assert f"**{len(TOOL_SPECS)} tools" in docs
