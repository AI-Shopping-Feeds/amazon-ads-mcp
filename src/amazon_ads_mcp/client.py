from __future__ import annotations

import gzip
import json
import random
import time
from typing import Any
from urllib.parse import urlparse

import httpx

from . import __version__
from ._logging import get_logger
from .audit import AuditLog
from .auth import Auth, redact
from .config import Config

WRITE_METHODS = {"POST", "PUT", "PATCH", "DELETE"}
RETRYABLE_STATUSES = {429, 500, 502, 503, 504}
MAX_ATTEMPTS = 5
MAX_BACKOFF = 300.0  # cap on honouring a very long Retry-After
# Report files are served from Amazon-owned storage; nothing else is fetched.
DOWNLOAD_HOST_SUFFIXES = (".amazonaws.com", ".amazon.com")

logger = get_logger("client")


class AmazonAdsAPIError(Exception):
    def __init__(self, status: int, body: Any, message: str = ""):
        self.status = status
        self.body = redact(body)
        super().__init__(message or f"Amazon Ads API error {status}: {self.body}")


class AmazonAdsClient:
    """Thin HTTP wrapper over the Amazon Ads API.

    Adds the auth, client-ID and profile-scope headers, retries throttled and
    failed requests with backoff (honouring Retry-After), paginates, and sends
    every write through dry-run and the audit log. It only talks to the
    configured regional API host and, for report files, Amazon's storage.
    """

    def __init__(self, config: Config, auth: Auth, audit: AuditLog):
        self.config = config
        self.auth = auth
        self.audit = audit
        self._http = httpx.Client(
            timeout=config.timeout,
            headers={"User-Agent": f"amazon-ads-mcp/{__version__}"},
            follow_redirects=False,
        )

    def close(self) -> None:
        self._http.close()

    def __enter__(self) -> AmazonAdsClient:
        return self

    def __exit__(self, *exc: object) -> None:
        self.close()

    @property
    def base_url(self) -> str:
        return self.config.api_host

    def resolve_profile(self, profile_id: str | int | None) -> str:
        pid = str(profile_id).strip() if profile_id not in (None, "") else self.config.profile_id
        if not pid:
            raise ValueError(
                "No profile_id. Pass profile_id (see amazon_ads_list_profiles) or set "
                "AMAZON_ADS_PROFILE_ID."
            )
        if not pid.lstrip("-").isdigit():
            raise ValueError(f"profile_id must be numeric, got '{pid}'.")
        return pid

    def _headers(
        self,
        path: str,
        profile: str | None,
        content_type: str | None,
        accept: str | None,
        has_body: bool,
    ) -> dict[str, str]:
        headers = {
            "Authorization": f"Bearer {self.auth.access_token()}",
            "Amazon-Advertising-API-ClientId": self.config.client_id,
        }
        if path.startswith("/adsApi/"):
            headers["Amazon-Ads-ClientId"] = self.config.client_id
        if profile:
            headers["Amazon-Advertising-API-Scope"] = profile
        if has_body:
            headers["Content-Type"] = content_type or "application/json"
        headers["Accept"] = accept or content_type or "application/json"
        return headers

    def request(
        self,
        method: str,
        path: str,
        *,
        params: dict[str, Any] | None = None,
        json_body: Any | None = None,
        profile_id: str | int | None = None,
        scoped: bool = True,
        content_type: str | None = None,
        accept: str | None = None,
        op: str | None = None,
        before: Any | None = None,
        read_only: bool = False,
    ) -> Any:
        """Perform one API request and return parsed JSON ({} for an empty body).

        path: relative to the regional host, starting with '/'.
        scoped: send Amazon-Advertising-API-Scope (the profile). Only the
            profiles and manager-account endpoints work without it.
        read_only: set True for POST endpoints that don't change anything (list,
            query, recommendations, report requests). They then bypass dry-run
            and are not written to the audit log.
        """
        method = method.upper()
        if not path.startswith("/") or "://" in path:
            raise ValueError(
                "path must be relative to the Amazon Ads API host, e.g. '/v2/profiles'."
            )
        profile = self.resolve_profile(profile_id) if scoped else None
        url = f"{self.base_url}{path}"
        is_write = method in WRITE_METHODS and not read_only

        if is_write and self.config.dry_run:
            audit_id = self.audit.record(
                op=op or f"{method} {path}",
                resource=path,
                method=method,
                url=url,
                profile_id=profile,
                request_body=json_body,
                dry_run=True,
                before=before,
            )
            logger.info("dry-run %s %s (audit=%s)", method, path, audit_id)
            return {
                "_dry_run": True,
                "method": method,
                "url": url,
                "profile_id": profile,
                "body": json_body,
                "audit_id": audit_id,
            }

        last_exc: Exception | None = None
        refreshed = False
        attempt = 0
        while attempt < MAX_ATTEMPTS:
            try:
                headers = self._headers(path, profile, content_type, accept, json_body is not None)
                resp = self._http.request(
                    method,
                    url,
                    params=params,
                    content=None if json_body is None else json.dumps(json_body),
                    headers=headers,
                )
            except httpx.RequestError as e:
                last_exc = e
                logger.warning("transport error attempt=%d %s %s: %s", attempt + 1, method, path, e)
                self._sleep_backoff(attempt)
                attempt += 1
                continue

            if resp.status_code == 401 and not refreshed:
                # The cached access token may have been revoked early; refresh once.
                refreshed = True
                self.auth.invalidate()
                continue

            if resp.status_code in RETRYABLE_STATUSES and attempt < MAX_ATTEMPTS - 1:
                logger.warning(
                    "retryable status=%d attempt=%d %s %s",
                    resp.status_code,
                    attempt + 1,
                    method,
                    path,
                )
                self._sleep_backoff(attempt, resp)
                attempt += 1
                continue

            payload: Any = self._safe_json(resp)

            if not (200 <= resp.status_code < 300):
                if is_write:
                    self.audit.record(
                        op=op or f"{method} {path}",
                        resource=path,
                        method=method,
                        url=url,
                        profile_id=profile,
                        request_body=json_body,
                        response_status=resp.status_code,
                        response_body=payload,
                        before=before,
                        error=f"HTTP {resp.status_code}",
                    )
                logger.error(
                    "api error %d %s %s: %s", resp.status_code, method, path, redact(payload)
                )
                raise AmazonAdsAPIError(resp.status_code, payload)

            if is_write:
                audit_id = self.audit.record(
                    op=op or f"{method} {path}",
                    resource=path,
                    method=method,
                    url=url,
                    profile_id=profile,
                    request_body=json_body,
                    response_status=resp.status_code,
                    response_body=payload,
                    before=before,
                )
                logger.info(
                    "write %s %s -> %d (audit=%s)", method, path, resp.status_code, audit_id
                )
                if isinstance(payload, dict):
                    payload = {**payload, "audit_id": audit_id}
                else:
                    payload = {"result": payload, "audit_id": audit_id}
            else:
                logger.debug("read  %s %s -> %d", method, path, resp.status_code)
            return payload

        raise AmazonAdsAPIError(0, str(last_exc) if last_exc else "exhausted retries")

    def paginate_token(
        self,
        path: str,
        body: dict[str, Any],
        *,
        items_key: str,
        content_type: str,
        profile_id: str | int | None = None,
        max_results: int = 500,
        page_size_key: str = "maxResults",
        token_key: str = "nextToken",
    ) -> tuple[list[Any], bool]:
        """Follow nextToken on POST .../list endpoints. Returns (items, truncated)."""
        body = dict(body)
        items: list[Any] = []
        while True:
            body[page_size_key] = max(1, min(self.config.page_size, max_results - len(items)))
            payload = self.request(
                "POST",
                path,
                json_body=body,
                profile_id=profile_id,
                content_type=content_type,
                read_only=True,
            )
            items.extend(payload.get(items_key) or [])
            token = payload.get(token_key)
            if not token:
                return items, False
            if len(items) >= max_results:
                return items[:max_results], True
            body[token_key] = token

    def paginate_offset(
        self,
        path: str,
        params: dict[str, Any],
        *,
        accept: str | None = None,
        profile_id: str | int | None = None,
        max_results: int = 500,
    ) -> tuple[list[Any], bool]:
        """Page through GET endpoints that take startIndex/count and return a list."""
        params = dict(params)
        items: list[Any] = []
        start = 0
        while True:
            count = max(1, min(self.config.page_size, max_results - len(items)))
            page = self.request(
                "GET",
                path,
                params={**params, "startIndex": start, "count": count},
                profile_id=profile_id,
                accept=accept,
            )
            page = page if isinstance(page, list) else []
            items.extend(page)
            if len(page) < count:
                return items, False
            if len(items) >= max_results:
                return items[:max_results], True
            start += len(page)

    def snapshot(self, fn: Any, *args: Any, **kwargs: Any) -> Any | None:
        """Run a read for a `before` snapshot; returns None instead of raising."""
        try:
            return fn(*args, **kwargs)
        except Exception as e:
            logger.warning("before-snapshot failed: %s", redact(str(e)))
            return None

    def download_report(self, url: str) -> list[Any]:
        """Fetch a finished report file and return its rows, kept in memory only.

        The URL is a short-lived signed link to Amazon's storage, so no auth
        headers are sent with it.
        """
        host = urlparse(url).hostname or ""
        if urlparse(url).scheme != "https" or not host.endswith(DOWNLOAD_HOST_SUFFIXES):
            raise ValueError(f"Refusing to download a report from a non-Amazon host: {host!r}")
        last: Exception | None = None
        for attempt in range(MAX_ATTEMPTS):
            try:
                resp = httpx.get(url, timeout=max(self.config.timeout, 120.0))
            except httpx.RequestError as e:
                last = e
                self._sleep_backoff(attempt)
                continue
            if resp.status_code in RETRYABLE_STATUSES and attempt < MAX_ATTEMPTS - 1:
                self._sleep_backoff(attempt, resp)
                continue
            if resp.status_code != 200:
                raise AmazonAdsAPIError(resp.status_code, resp.text[:300])
            raw = resp.content
            if raw[:2] == b"\x1f\x8b":
                raw = gzip.decompress(raw)
            data = json.loads(raw.decode("utf-8")) if raw.strip() else []
            return data if isinstance(data, list) else [data]
        raise AmazonAdsAPIError(0, str(last) if last else "report download failed")

    @staticmethod
    def _safe_json(resp: httpx.Response) -> Any:
        if resp.status_code == 204 or not resp.content:
            return {}
        try:
            return resp.json()
        except ValueError:
            return {"_raw": resp.text[:2000]}

    @staticmethod
    def _sleep_backoff(attempt: int, resp: httpx.Response | None = None) -> None:
        retry_after = 0.0
        if resp is not None and "Retry-After" in resp.headers:
            try:
                retry_after = float(resp.headers["Retry-After"])
            except ValueError:
                retry_after = 0.0
        base = min(max(retry_after, min(2**attempt, 30)), MAX_BACKOFF)
        time.sleep(base + random.uniform(0, 0.5))
