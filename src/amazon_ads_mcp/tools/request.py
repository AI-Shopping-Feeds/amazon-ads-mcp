"""Escape hatch: call any Amazon Ads API endpoint on the configured regional host."""

from __future__ import annotations

import re
from typing import Any

from .. import safety
from ..client import AmazonAdsClient, check_api_path

# POST endpoints that only read: list/query/search calls, recommendations,
# forecasts, insights and report requests.
_READ_POST = re.compile(
    r"(/list$|/query/|/search$|/retrieve/|recommendations|/forecasts$|/insights$"
    r"|/count$|/budget/usage$|^/reporting/reports$|^/adsApi/v1/create/reports$)",
    re.IGNORECASE,
)
# A POST to a path with one of these segments changes something, even if the
# path also matches _READ_POST (e.g. '.../recommendations/apply').
_ACTION_SEGMENTS = {
    "accept",
    "apply",
    "approve",
    "archive",
    "associate",
    "cancel",
    "create",
    "delete",
    "disassociate",
    "enable",
    "pause",
    "reject",
    "submit",
    "update",
}
# Report requests read data, though the v1 path says "create".
_READ_ACTION_PATHS = {"/reporting/reports", "/adsapi/v1/create/reports"}
_UNSCOPED = ("/v2/profiles", "/managerAccounts")


def _is_read_post(bare: str) -> bool:
    if not _READ_POST.search(bare):
        return False
    if bare.lower() in _READ_ACTION_PATHS:
        return True
    return not any(segment.lower() in _ACTION_SEGMENTS for segment in bare.split("/"))


def _classify(method: str, path: str) -> tuple[str, str, bool, bool]:
    method = method.upper()
    if method not in {"GET", "POST", "PUT", "PATCH", "DELETE"}:
        raise ValueError("method must be GET, POST, PUT, PATCH or DELETE.")
    check_api_path(path)
    bare = path.split("?", 1)[0]
    is_read = method == "GET" or (method == "POST" and _is_read_post(bare))
    scoped = not bare.startswith(_UNSCOPED)
    return method, bare, is_read, scoped


def register(mcp, client: AmazonAdsClient) -> None:
    @mcp.tool()
    def amazon_ads_read_request(
        method: str,
        path: str,
        body: Any | None = None,
        query: dict[str, Any] | None = None,
        content_type: str | None = None,
        accept: str | None = None,
        profile_id: str | None = None,
    ) -> Any:
        """Read from any Amazon Ads API endpoint the other tools don't cover.

        Only GET, and POSTs to list/query/search/recommendation/report endpoints,
        are allowed; use amazon_ads_request for writes. path is relative to the
        regional API host, e.g. '/sb/v4/campaigns/list'. Versioned endpoints need
        their media type in content_type (and accept), e.g.
        'application/vnd.sbcampaignresource.v4+json'; the API's error names it.
        """
        method, bare, is_read, scoped = _classify(method, path)
        if not is_read:
            raise ValueError(
                f"{method} {bare} may change the account; use amazon_ads_request instead."
            )
        return client.request(
            method,
            path,
            params=query,
            json_body=body,
            profile_id=profile_id,
            scoped=scoped,
            content_type=content_type,
            accept=accept,
            read_only=True,
        )

    @mcp.tool()
    def amazon_ads_request(
        method: str,
        path: str,
        body: Any | None = None,
        query: dict[str, Any] | None = None,
        content_type: str | None = None,
        accept: str | None = None,
        profile_id: str | None = None,
        confirm: str = "",
    ) -> Any:
        """Call any Amazon Ads API endpoint the other tools don't cover.

        path is relative to the regional API host and starts with '/', e.g.
        '/sp/campaigns/list'. Many endpoints need a versioned media type in
        content_type (and accept), e.g. 'application/vnd.spCampaign.v3+json'; the
        API's error message names the expected one. The profile scope header is
        sent except for /v2/profiles and /managerAccounts.

        GET, and POSTs to list/query/search/recommendation/report endpoints, are
        reads. Every other call is a write: it is audited, follows dry-run, and
        needs confirm='APPLY' because this tool can't check what it changes.
        """
        method, bare, is_read, scoped = _classify(method, path)
        if not is_read:
            decision = safety.Decision(
                required=safety.APPLY,
                reasons=["raw write through amazon_ads_request; its effect isn't checked"],
            )
            refused = safety.refusal(
                client.config,
                decision,
                confirm,
                preview={"method": method, "path": path, "body": body},
            )
            if refused:
                return refused
        return client.request(
            method,
            path,
            params=query,
            json_body=body,
            profile_id=profile_id,
            scoped=scoped,
            content_type=content_type,
            accept=accept,
            read_only=is_read,
            op=f"request {method} {bare}",
        )
