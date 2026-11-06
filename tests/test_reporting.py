"""Report create -> poll -> download, through the MCP client."""

from __future__ import annotations

import dataclasses
import gzip
import json

import httpx
import pytest
import respx
from mcp import Client

from amazon_ads_mcp import server
from amazon_ads_mcp.config import Config

from .conftest import BASE, FakeAuth, audit_entries

REPORT_ID = "12345678-aaaa-bbbb-cccc-1234567890ab"
URL = "https://offline-report-storage-eu-west-1-prod.s3.eu-west-1.amazonaws.com/r.json.gz?sig=x"
ROWS = [{"campaignId": i, "clicks": i * 2, "cost": 1.5} for i in range(5)]
ARGS = {
    "report_type_id": "spCampaigns",
    "start_date": "2026-10-01",
    "end_date": "2026-10-31",
    "columns": ["campaignId", "clicks", "cost"],
    "group_by": ["campaign"],
}


@pytest.fixture(autouse=True)
def fake_auth(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(server, "load_auth", lambda config: FakeAuth())


def _mock_flow(router) -> tuple:
    create = router.post(f"{BASE}/reporting/reports").mock(
        return_value=httpx.Response(200, json={"reportId": REPORT_ID, "status": "PENDING"})
    )
    status = router.get(f"{BASE}/reporting/reports/{REPORT_ID}").mock(
        side_effect=[
            httpx.Response(200, json={"reportId": REPORT_ID, "status": "PENDING"}),
            httpx.Response(200, json={"reportId": REPORT_ID, "status": "PROCESSING"}),
            httpx.Response(200, json={"reportId": REPORT_ID, "status": "COMPLETED", "url": URL}),
        ]
    )
    download = router.get(URL).mock(
        return_value=httpx.Response(200, content=gzip.compress(json.dumps(ROWS).encode()))
    )
    return create, status, download


async def test_run_report_creates_polls_and_downloads(config: Config) -> None:
    progress: list[tuple[float, str | None]] = []

    async def on_progress(p: float, total: float | None, message: str | None) -> None:
        progress.append((p, message))

    with respx.mock() as router:
        create, status, _download = _mock_flow(router)
        async with Client(server.build_server(config)) as c:
            result = await c.call_tool(
                "amazon_ads_run_report",
                {**ARGS, "poll_seconds": 0, "max_rows": 3},
                progress_callback=on_progress,
            )
    out = result.structured_content or json.loads(result.content[0].text)
    assert not result.is_error
    assert out["row_count"] == 5
    assert out["rows"] == ROWS[:3]
    assert out["truncated"] is True
    body = json.loads(create.calls.last.request.content)
    assert body["configuration"] == {
        "adProduct": "SPONSORED_PRODUCTS",
        "reportTypeId": "spCampaigns",
        "columns": ["campaignId", "clicks", "cost"],
        "groupBy": ["campaign"],
        "timeUnit": "SUMMARY",
        "format": "GZIP_JSON",
    }
    assert create.calls.last.request.headers["Content-Type"] == (
        "application/vnd.createasyncreportrequest.v3+json"
    )
    assert status.call_count == 3
    steps = [p for p, _ in progress]
    assert steps == sorted(steps) and len(set(steps)) == len(steps)
    assert progress[-1][1] == "Downloaded 5 rows"
    # Report requests and rows never go to the audit log.
    assert audit_entries(config.audit_log) == []


async def test_report_tools_work_in_dry_run_and_read_only(config: Config) -> None:
    with respx.mock() as router:
        _mock_flow(router)
        mcp = server.build_server(dataclasses.replace(config, dry_run=True, read_only=True))
        async with Client(mcp) as c:
            created = await c.call_tool("amazon_ads_create_report", ARGS)
            first = await c.call_tool("amazon_ads_download_report", {"report_id": REPORT_ID})
            await c.call_tool("amazon_ads_get_report", {"report_id": REPORT_ID})
            done = await c.call_tool("amazon_ads_download_report", {"report_id": REPORT_ID})
    assert json.loads(created.content[0].text)["reportId"] == REPORT_ID
    assert "isn't ready" in json.loads(first.content[0].text)["message"]
    assert json.loads(done.content[0].text)["row_count"] == 5


async def test_duplicate_request_reuses_existing_report(config: Config) -> None:
    with respx.mock() as router:
        router.post(f"{BASE}/reporting/reports").mock(
            return_value=httpx.Response(
                425, json={"code": "425", "detail": f"The Request is a duplicate of : {REPORT_ID}"}
            )
        )
        async with Client(server.build_server(config)) as c:
            result = await c.call_tool("amazon_ads_create_report", ARGS)
    out = json.loads(result.content[0].text)
    assert out["reportId"] == REPORT_ID
    assert out["duplicate_of_existing"] is True


async def test_failed_report_is_reported(config: Config) -> None:
    with respx.mock() as router:
        router.post(f"{BASE}/reporting/reports").mock(
            return_value=httpx.Response(200, json={"reportId": REPORT_ID})
        )
        router.get(f"{BASE}/reporting/reports/{REPORT_ID}").mock(
            return_value=httpx.Response(
                200, json={"reportId": REPORT_ID, "status": "FAILED", "failureReason": "bad column"}
            )
        )
        async with Client(server.build_server(config)) as c:
            result = await c.call_tool("amazon_ads_run_report", {**ARGS, "poll_seconds": 0})
    out = json.loads(result.content[0].text)
    assert out["status"] == "FAILED"
    assert out["failure_reason"] == "bad column"


async def test_bad_ad_product_is_rejected(config: Config) -> None:
    async with Client(server.build_server(config)) as c:
        result = await c.call_tool("amazon_ads_create_report", {**ARGS, "ad_product": "TV"})
    assert result.is_error
    assert "ad_product" in result.content[0].text
