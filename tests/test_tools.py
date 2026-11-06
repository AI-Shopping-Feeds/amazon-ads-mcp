"""Entity tools through the real server (fake auth, mocked HTTP)."""

from __future__ import annotations

import dataclasses
import json
from typing import Any

import httpx
import pytest
import respx
from mcp import Client

from amazon_ads_mcp import server
from amazon_ads_mcp.config import Config

from .conftest import BASE, PROFILE, FakeAuth, audit_entries

SP_CAMPAIGN = "application/vnd.spCampaign.v3+json"


@pytest.fixture(autouse=True)
def fake_auth(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(server, "load_auth", lambda config: FakeAuth())


def _payload(result: Any) -> Any:
    assert not result.is_error, result.content
    return result.structured_content or json.loads(result.content[0].text)


async def _call(config: Config, tool: str, args: dict[str, Any], **changes: Any) -> Any:
    mcp = server.build_server(dataclasses.replace(config, **changes))
    async with Client(mcp) as c:
        return await c.call_tool(tool, args)


@respx.mock
async def test_list_campaigns_builds_filters(config: Config) -> None:
    route = respx.post(f"{BASE}/sp/campaigns/list").mock(
        return_value=httpx.Response(200, json={"campaigns": [{"campaignId": "1"}]})
    )
    out = _payload(
        await _call(
            config, "amazon_ads_sp_list_campaigns", {"portfolio_ids": ["9"], "profile_id": "222"}
        )
    )
    assert out["count"] == 1
    sent = route.calls.last.request
    body = json.loads(sent.content)
    assert body["portfolioIdFilter"] == {"include": ["9"]}
    assert body["stateFilter"] == {"include": ["ENABLED", "PAUSED"]}
    assert sent.headers["Amazon-Advertising-API-Scope"] == "222"
    assert sent.headers["Content-Type"] == SP_CAMPAIGN


async def test_unsupported_filter_is_an_error(config: Config) -> None:
    result = await _call(config, "amazon_ads_sp_list_campaigns", {"ad_group_ids": ["1"]})
    assert result.is_error
    assert "can't be filtered by ad_group_ids" in result.content[0].text


@respx.mock
async def test_budget_rise_is_refused_without_confirm(config: Config) -> None:
    respx.post(f"{BASE}/sp/campaigns/list").mock(
        return_value=httpx.Response(
            200,
            json={
                "campaigns": [{"campaignId": "1", "budget": {"budget": 10, "budgetType": "DAILY"}}]
            },
        )
    )
    put = respx.put(f"{BASE}/sp/campaigns").mock(return_value=httpx.Response(207, json={}))
    items = [{"campaignId": "1", "budget": {"budget": 20, "budgetType": "DAILY"}}]
    out = _payload(await _call(config, "amazon_ads_sp_update_campaigns", {"items": items}))
    assert out["refused"] is True
    assert out["required_confirm"] == "APPLY"
    assert out["money_changes"][0] == {
        "id": "1",
        "kind": "budget",
        "old": 10.0,
        "new": 20.0,
        "change_pct": 100.0,
    }
    assert not put.called


@respx.mock
async def test_budget_rise_applies_with_confirm_and_keeps_before(config: Config) -> None:
    respx.post(f"{BASE}/sp/campaigns/list").mock(
        return_value=httpx.Response(
            200, json={"campaigns": [{"campaignId": "1", "budget": {"budget": 10}}]}
        )
    )
    put = respx.put(f"{BASE}/sp/campaigns").mock(
        return_value=httpx.Response(207, json={"campaigns": {"success": [{"campaignId": "1"}]}})
    )
    items = [{"campaignId": "1", "budget": {"budget": 20, "budgetType": "DAILY"}}]
    out = _payload(
        await _call(config, "amazon_ads_sp_update_campaigns", {"items": items, "confirm": "APPLY"})
    )
    assert put.called
    assert json.loads(put.calls.last.request.content) == {"campaigns": items}
    assert out["safety"]["required_confirm"] == "APPLY"
    [entry] = audit_entries(config.audit_log)
    assert entry["before"] == [{"campaignId": "1", "budget": {"budget": 10}}]
    assert entry["audit_id"] == out["audit_id"]


@respx.mock
async def test_small_bid_change_needs_no_confirm(config: Config) -> None:
    respx.post(f"{BASE}/sp/keywords/list").mock(
        return_value=httpx.Response(200, json={"keywords": [{"keywordId": "7", "bid": 1.0}]})
    )
    put = respx.put(f"{BASE}/sp/keywords").mock(return_value=httpx.Response(207, json={}))
    _payload(
        await _call(
            config, "amazon_ads_sp_update_keywords", {"items": [{"keywordId": "7", "bid": 1.1}]}
        )
    )
    assert put.called


@respx.mock
async def test_archive_needs_archive_confirm(config: Config) -> None:
    delete = respx.post(f"{BASE}/sp/keywords/delete").mock(
        return_value=httpx.Response(207, json={})
    )
    respx.post(f"{BASE}/sp/keywords/list").mock(
        return_value=httpx.Response(200, json={"keywords": []})
    )
    refused = _payload(await _call(config, "amazon_ads_sp_archive_keywords", {"ids": ["7"]}))
    assert refused["required_confirm"] == "ARCHIVE"
    assert not delete.called
    _payload(
        await _call(config, "amazon_ads_sp_archive_keywords", {"ids": ["7"], "confirm": "ARCHIVE"})
    )
    assert json.loads(delete.calls.last.request.content) == {"keywordIdFilter": {"include": ["7"]}}


async def test_dry_run_rehearses_guarded_writes(config: Config) -> None:
    with respx.mock(assert_all_called=False) as router:
        router.post(f"{BASE}/sp/keywords/list").mock(
            return_value=httpx.Response(200, json={"keywords": []})
        )
        delete = router.post(f"{BASE}/sp/keywords/delete").mock(
            return_value=httpx.Response(207, json={})
        )
        out = _payload(
            await _call(config, "amazon_ads_sp_archive_keywords", {"ids": ["7"]}, dry_run=True)
        )
    assert out["_dry_run"] is True
    assert out["safety"]["required_confirm"] == "ARCHIVE"
    assert not delete.called
    assert audit_entries(config.audit_log)[0]["dry_run"] is True


@respx.mock
async def test_sd_archive_reports_progress_per_id(config: Config) -> None:
    respx.get(f"{BASE}/sd/campaigns").mock(
        return_value=httpx.Response(200, json=[{"campaignId": 1, "state": "enabled"}])
    )
    for cid in (1, 2):
        respx.delete(f"{BASE}/sd/campaigns/{cid}").mock(
            return_value=httpx.Response(200, json={"campaignId": cid, "code": "SUCCESS"})
        )
    seen: list[float] = []

    async def on_progress(progress: float, total: float | None, message: str | None) -> None:
        seen.append(progress)

    mcp = server.build_server(config)
    async with Client(mcp) as c:
        result = await c.call_tool(
            "amazon_ads_sd_archive_campaigns",
            {"ids": ["1", "2"], "confirm": "ARCHIVE"},
            progress_callback=on_progress,
        )
    out = _payload(result)
    assert out["archived_count"] == 2
    assert seen == [1, 2]
    ops = [e["op"] for e in audit_entries(config.audit_log)]
    assert ops == ["sd_archive_campaigns", "sd_archive_campaigns"]
    assert audit_entries(config.audit_log)[0]["before"] == {"campaignId": 1, "state": "enabled"}


@respx.mock
async def test_sd_list_uses_query_filters(config: Config) -> None:
    route = respx.get(f"{BASE}/sd/targets").mock(return_value=httpx.Response(200, json=[]))
    _payload(await _call(config, "amazon_ads_sd_list_targets", {"campaign_ids": ["5", "6"]}))
    params = route.calls.last.request.url.params
    assert params["campaignIdFilter"] == "5,6"
    assert params["stateFilter"] == "enabled, paused"


@respx.mock
async def test_adjust_bids_computes_and_guards(config: Config) -> None:
    respx.post(f"{BASE}/sp/keywords/list").mock(
        return_value=httpx.Response(
            200,
            json={"keywords": [{"keywordId": "1", "bid": 1.0}, {"keywordId": "2", "bid": 0.5}]},
        )
    )
    put = respx.put(f"{BASE}/sp/keywords").mock(return_value=httpx.Response(207, json={}))
    args = {"entity": "keywords", "ids": ["1", "2", "3"], "change_pct": 40}
    refused = _payload(await _call(config, "amazon_ads_sp_adjust_bids", args))
    assert refused["refused"] is True
    assert refused["not_found"] == ["3"]
    assert not put.called
    out = _payload(await _call(config, "amazon_ads_sp_adjust_bids", {**args, "confirm": "APPLY"}))
    assert out["to_change"] == 2
    assert json.loads(put.calls.last.request.content) == {
        "keywords": [{"keywordId": "1", "bid": 1.4}, {"keywordId": "2", "bid": 0.7}]
    }


@respx.mock
async def test_bulk_threshold_applies(config: Config) -> None:
    put = respx.put(f"{BASE}/sp/campaigns").mock(return_value=httpx.Response(207, json={}))
    respx.post(f"{BASE}/sp/campaigns/list").mock(return_value=httpx.Response(200, json={}))
    ids = [str(i) for i in range(config.bulk_threshold + 1)]
    out = _payload(
        await _call(
            config,
            "amazon_ads_sp_set_states",
            {"entity": "campaigns", "ids": ids, "state": "paused"},
        )
    )
    assert out["required_confirm"] == "APPLY"
    assert not put.called


@respx.mock
async def test_raw_request_reads_freely_but_writes_need_confirm(config: Config) -> None:
    respx.post(f"{BASE}/sb/v4/campaigns/list").mock(
        return_value=httpx.Response(200, json={"campaigns": []})
    )
    put = respx.put(f"{BASE}/sb/v4/campaigns").mock(return_value=httpx.Response(207, json={}))
    out = _payload(
        await _call(
            config,
            "amazon_ads_read_request",
            {"method": "POST", "path": "/sb/v4/campaigns/list", "body": {}},
        )
    )
    assert out == {"campaigns": []}
    bad = await _call(
        config, "amazon_ads_read_request", {"method": "PUT", "path": "/sb/v4/campaigns"}
    )
    assert bad.is_error
    refused = _payload(
        await _call(
            config, "amazon_ads_request", {"method": "PUT", "path": "/sb/v4/campaigns", "body": {}}
        )
    )
    assert refused["refused"] is True
    assert not put.called
    _payload(
        await _call(
            config,
            "amazon_ads_request",
            {"method": "PUT", "path": "/sb/v4/campaigns", "body": {}, "confirm": "APPLY"},
        )
    )
    assert put.called
    assert audit_entries(config.audit_log)[0]["op"] == "request PUT /sb/v4/campaigns"


async def test_raw_request_rejects_other_hosts(config: Config) -> None:
    result = await _call(
        config, "amazon_ads_read_request", {"method": "GET", "path": "https://example.com/x"}
    )
    assert result.is_error


@respx.mock
async def test_profiles_are_unscoped(config: Config) -> None:
    route = respx.get(f"{BASE}/v2/profiles").mock(
        return_value=httpx.Response(200, json=[{"profileId": int(PROFILE), "countryCode": "UK"}])
    )
    out = _payload(await _call(config, "amazon_ads_list_profiles", {}))
    assert out["count"] == 1
    assert "Amazon-Advertising-API-Scope" not in route.calls.last.request.headers


@respx.mock
async def test_v1_delete_needs_delete_confirm(config: Config) -> None:
    route = respx.post(f"{BASE}/adsApi/v1/delete/campaigns").mock(
        return_value=httpx.Response(207, json={})
    )
    refused = _payload(
        await _call(config, "amazon_ads_v1_delete", {"entity": "campaigns", "ids": ["1"]})
    )
    assert refused["required_confirm"] == "DELETE"
    _payload(
        await _call(
            config,
            "amazon_ads_v1_delete",
            {"entity": "campaigns", "ids": ["1"], "confirm": "DELETE"},
        )
    )
    assert json.loads(route.calls.last.request.content) == {"campaignIds": ["1"]}
