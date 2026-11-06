from __future__ import annotations

import gzip
import json

import httpx
import pytest
import respx

from amazon_ads_mcp.client import AmazonAdsAPIError, AmazonAdsClient

from .conftest import BASE, CLIENT_ID, PROFILE, FakeAuth, audit_entries


@respx.mock
def test_scoped_request_sends_auth_client_and_scope_headers(client: AmazonAdsClient) -> None:
    route = respx.post(f"{BASE}/sp/campaigns/list").mock(
        return_value=httpx.Response(200, json={"campaigns": []})
    )
    client.request(
        "POST",
        "/sp/campaigns/list",
        json_body={},
        content_type="application/vnd.spCampaign.v3+json",
        read_only=True,
    )
    sent = route.calls.last.request
    assert sent.headers["Authorization"] == "Bearer Atza|fake-access-token"
    assert sent.headers["Amazon-Advertising-API-ClientId"] == CLIENT_ID
    assert sent.headers["Amazon-Advertising-API-Scope"] == PROFILE
    assert sent.headers["Content-Type"] == "application/vnd.spCampaign.v3+json"
    assert sent.headers["Accept"] == "application/vnd.spCampaign.v3+json"


@respx.mock
def test_profile_override_and_unscoped(client: AmazonAdsClient) -> None:
    route = respx.get(f"{BASE}/x").mock(return_value=httpx.Response(200, json={}))
    client.request("GET", "/x", profile_id="999")
    assert route.calls.last.request.headers["Amazon-Advertising-API-Scope"] == "999"
    client.request("GET", "/x", scoped=False)
    assert "Amazon-Advertising-API-Scope" not in route.calls.last.request.headers


@respx.mock
def test_v1_paths_also_send_ads_client_id(client: AmazonAdsClient) -> None:
    route = respx.post(f"{BASE}/adsApi/v1/query/campaigns").mock(
        return_value=httpx.Response(200, json={"campaigns": []})
    )
    client.request("POST", "/adsApi/v1/query/campaigns", json_body={}, read_only=True)
    assert route.calls.last.request.headers["Amazon-Ads-ClientId"] == CLIENT_ID


def test_missing_profile_is_a_clear_error(client: AmazonAdsClient) -> None:
    client.config.profile_id = None
    with pytest.raises(ValueError, match="profile_id"):
        client.request("GET", "/sp/whatever")


def test_absolute_urls_are_rejected(client: AmazonAdsClient) -> None:
    with pytest.raises(ValueError, match="relative"):
        client.request("GET", "https://example.com/steal")


@respx.mock
def test_dry_run_skips_network_and_audits(client: AmazonAdsClient) -> None:
    client.config.dry_run = True
    route = respx.put(f"{BASE}/sp/campaigns").mock(return_value=httpx.Response(207, json={}))
    out = client.request(
        "PUT", "/sp/campaigns", json_body={"campaigns": [{"campaignId": "1"}]}, op="t"
    )
    assert out["_dry_run"] is True
    assert out["profile_id"] == PROFILE
    assert not route.called
    [entry] = audit_entries(client.audit.path)
    assert entry["dry_run"] is True
    assert entry["request_body"] == {"campaigns": [{"campaignId": "1"}]}


@respx.mock
def test_write_is_audited_with_before_and_response(client: AmazonAdsClient) -> None:
    respx.put(f"{BASE}/sp/keywords").mock(
        return_value=httpx.Response(207, json={"keywords": {"success": [{"keywordId": "5"}]}})
    )
    out = client.request(
        "PUT",
        "/sp/keywords",
        json_body={"keywords": [{"keywordId": "5", "bid": 1}]},
        op="sp_update_keywords",
        before=[{"keywordId": "5", "bid": 0.5}],
    )
    [entry] = audit_entries(client.audit.path)
    assert out["audit_id"] == entry["audit_id"]
    assert entry["op"] == "sp_update_keywords"
    assert entry["before"] == [{"keywordId": "5", "bid": 0.5}]
    assert entry["response_status"] == 207
    assert entry["profile_id"] == PROFILE


@respx.mock
def test_reads_and_read_only_posts_are_not_audited(client: AmazonAdsClient) -> None:
    respx.get(f"{BASE}/v2/profiles").mock(return_value=httpx.Response(200, json=[{"profileId": 1}]))
    respx.post(f"{BASE}/sp/keywords/list").mock(return_value=httpx.Response(200, json={}))
    client.request("GET", "/v2/profiles", scoped=False)
    client.request("POST", "/sp/keywords/list", json_body={}, read_only=True)
    assert audit_entries(client.audit.path) == []


@respx.mock
def test_401_refreshes_token_once(client: AmazonAdsClient, fake_auth: FakeAuth) -> None:
    route = respx.get(f"{BASE}/x").mock(
        side_effect=[httpx.Response(401, json={}), httpx.Response(200, json={"ok": 1})]
    )
    assert client.request("GET", "/x") == {"ok": 1}
    assert fake_auth.invalidated == 1
    assert route.call_count == 2


@respx.mock
def test_429_honours_retry_after(client: AmazonAdsClient, _no_sleep: list[float]) -> None:
    route = respx.get(f"{BASE}/x").mock(
        side_effect=[
            httpx.Response(429, headers={"Retry-After": "7"}, json={}),
            httpx.Response(200, json={"ok": True}),
        ]
    )
    assert client.request("GET", "/x") == {"ok": True}
    assert route.call_count == 2
    assert _no_sleep and _no_sleep[0] >= 7


@respx.mock
def test_errors_raise_and_are_redacted(client: AmazonAdsClient) -> None:
    respx.get(f"{BASE}/x").mock(
        return_value=httpx.Response(400, json={"code": "BAD", "details": "Atza|leaky"})
    )
    with pytest.raises(AmazonAdsAPIError) as ei:
        client.request("GET", "/x")
    assert ei.value.status == 400
    assert "Atza|leaky" not in str(ei.value)
    assert "BAD" in str(ei.value)


@respx.mock
def test_failed_write_is_audited(client: AmazonAdsClient) -> None:
    respx.post(f"{BASE}/sp/campaigns").mock(return_value=httpx.Response(422, json={"code": "X"}))
    with pytest.raises(AmazonAdsAPIError):
        client.request("POST", "/sp/campaigns", json_body={"campaigns": []}, op="c")
    [entry] = audit_entries(client.audit.path)
    assert entry["error"] == "HTTP 422"


@respx.mock
def test_paginate_token_follows_next_token(client: AmazonAdsClient) -> None:
    route = respx.post(f"{BASE}/sp/campaigns/list").mock(
        side_effect=[
            httpx.Response(200, json={"campaigns": [{"campaignId": "1"}], "nextToken": "t1"}),
            httpx.Response(200, json={"campaigns": [{"campaignId": "2"}]}),
        ]
    )
    items, truncated = client.paginate_token(
        "/sp/campaigns/list", {}, items_key="campaigns", content_type="application/json"
    )
    assert [i["campaignId"] for i in items] == ["1", "2"]
    assert truncated is False
    assert json.loads(route.calls[1].request.content)["nextToken"] == "t1"


@respx.mock
def test_paginate_token_stops_at_max_results(client: AmazonAdsClient) -> None:
    respx.post(f"{BASE}/l").mock(
        return_value=httpx.Response(200, json={"items": [{"id": 1}, {"id": 2}], "nextToken": "t"})
    )
    items, truncated = client.paginate_token(
        "/l", {}, items_key="items", content_type="application/json", max_results=3
    )
    assert len(items) == 3
    assert truncated is True


@respx.mock
def test_paginate_offset(client: AmazonAdsClient) -> None:
    client.config.page_size = 2
    route = respx.get(f"{BASE}/sd/campaigns").mock(
        side_effect=[
            httpx.Response(200, json=[{"campaignId": 1}, {"campaignId": 2}]),
            httpx.Response(200, json=[{"campaignId": 3}]),
        ]
    )
    items, truncated = client.paginate_offset("/sd/campaigns", {"stateFilter": "enabled"})
    assert [i["campaignId"] for i in items] == [1, 2, 3]
    assert not truncated
    assert route.calls[1].request.url.params["startIndex"] == "2"


@respx.mock
def test_download_report_reads_gzip_in_memory(client: AmazonAdsClient) -> None:
    url = "https://offline-report-storage-eu-west-1-prod.s3.eu-west-1.amazonaws.com/r.json.gz"
    rows = [{"campaignId": 1, "clicks": 3}]
    route = respx.get(url).mock(
        return_value=httpx.Response(200, content=gzip.compress(json.dumps(rows).encode()))
    )
    assert client.download_report(url) == rows
    assert "Authorization" not in route.calls.last.request.headers


def test_download_report_refuses_other_hosts(client: AmazonAdsClient) -> None:
    with pytest.raises(ValueError, match="non-Amazon"):
        client.download_report("https://evil.example.com/r.json.gz")
