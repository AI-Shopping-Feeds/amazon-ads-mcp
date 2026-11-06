"""Login with Amazon (LwA) tokens for the Amazon Ads API.

`LwaAuth` swaps a long-lived refresh token for short-lived access tokens and
caches each one until shortly before it expires. The refresh token comes from
`amazon-ads-mcp auth` (stored in a 0600 file) or from AMAZON_ADS_REFRESH_TOKEN.

Secrets are never logged: use `redact()` on anything that might contain one.
"""

from __future__ import annotations

import json
import os
import re
import threading
import time
from pathlib import Path
from typing import Any, Protocol

import httpx

from .config import Config, make_private_dir

SCOPE = "advertising::campaign_management"
# Refresh this many seconds before the access token's stated expiry.
EXPIRY_MARGIN = 60

_TOKEN_RE = re.compile(r"Atz[ar]\|[A-Za-z0-9\-_|.+/=]+")
_SECRET_KEYS = {
    "access_token",
    "refresh_token",
    "client_secret",
    "authorization",
    "password",
}
_extra_secrets: set[str] = set()


def register_secret(value: str | None) -> None:
    """Remember a secret value (e.g. the client secret) so redact() hides it."""
    if value and len(value) >= 8:
        _extra_secrets.add(value)


def redact(value: Any) -> Any:
    """Return a copy of value with tokens and known secrets replaced by '***'."""
    if isinstance(value, str):
        out = _TOKEN_RE.sub("***", value)
        for secret in _extra_secrets:
            out = out.replace(secret, "***")
        return out
    if isinstance(value, dict):
        return {
            k: ("***" if str(k).lower() in _SECRET_KEYS and v else redact(v))
            for k, v in value.items()
        }
    if isinstance(value, list | tuple):
        return [redact(v) for v in value]
    return value


class Auth(Protocol):
    @property
    def account_label(self) -> str: ...

    def access_token(self) -> str: ...

    def invalidate(self) -> None: ...


class LwaError(RuntimeError):
    """The token endpoint refused the refresh (bad client, revoked or expired token)."""


class LwaAuth:
    """Thread-safe LwA refresh-token holder that caches access tokens until expiry."""

    def __init__(
        self,
        *,
        client_id: str,
        client_secret: str,
        refresh_token: str,
        token_url: str,
        token_file: Path | None = None,
        timeout: float = 30.0,
    ):
        self.client_id = client_id
        self._client_secret = client_secret
        self._refresh_token = refresh_token
        self.token_url = token_url
        self.token_file = token_file
        self._timeout = timeout
        self._lock = threading.Lock()
        self._token: str | None = None
        self._expires_at = 0.0
        register_secret(client_secret)
        register_secret(refresh_token)

    @property
    def account_label(self) -> str:
        return f"lwa:{self.client_id[-6:]}"

    @property
    def expires_in(self) -> int:
        return max(0, int(self._expires_at - time.time()))

    def invalidate(self) -> None:
        with self._lock:
            self._token = None
            self._expires_at = 0.0

    def access_token(self) -> str:
        with self._lock:
            if self._token and time.time() < self._expires_at - EXPIRY_MARGIN:
                return self._token
            data = {
                "grant_type": "refresh_token",
                "refresh_token": self._refresh_token,
                "client_id": self.client_id,
                "client_secret": self._client_secret,
            }
            try:
                resp = httpx.post(self.token_url, data=data, timeout=self._timeout)
            except httpx.HTTPError as e:
                raise LwaError(f"Could not reach the Login with Amazon token endpoint: {e}") from e
            if resp.status_code != 200:
                raise LwaError(
                    f"Login with Amazon refused the token refresh (HTTP {resp.status_code}): "
                    f"{redact(_safe_json(resp))}. If the refresh token was revoked or has "
                    "expired, run `amazon-ads-mcp auth` again."
                )
            payload = _safe_json(resp)
            token = payload.get("access_token") if isinstance(payload, dict) else None
            if not token:
                raise LwaError("Login with Amazon returned no access token.")
            self._token = token
            register_secret(token)
            self._expires_at = time.time() + float(payload.get("expires_in", 3600))
            new_refresh = payload.get("refresh_token")
            if new_refresh and new_refresh != self._refresh_token:
                self._refresh_token = new_refresh
                register_secret(new_refresh)
                if self.token_file is not None and self.token_file.exists():
                    save_token_file(self.token_file, {"refresh_token": new_refresh})
            return token


def _safe_json(resp: httpx.Response) -> Any:
    try:
        return resp.json()
    except ValueError:
        return {"_raw": resp.text[:500]}


def save_token_file(path: Path, data: dict[str, Any]) -> None:
    """Write (or merge into) the token file with owner-only (0600) permissions.

    Folders created for it are owner-only (0700) too.
    """
    make_private_dir(path.parent)
    existing: dict[str, Any] = {}
    if path.exists():
        try:
            existing = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            existing = {}
    existing.update(data)
    fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
    with os.fdopen(fd, "w", encoding="utf-8") as f:
        json.dump(existing, f, indent=2)
    os.chmod(path, 0o600)


def exchange_code(
    *, code: str, redirect_uri: str, client_id: str, client_secret: str, token_url: str
) -> dict[str, Any]:
    """Swap a one-time authorization code for access and refresh tokens."""
    resp = httpx.post(
        token_url,
        data={
            "grant_type": "authorization_code",
            "code": code,
            "redirect_uri": redirect_uri,
            "client_id": client_id,
            "client_secret": client_secret,
        },
        timeout=30.0,
    )
    payload = _safe_json(resp)
    if resp.status_code != 200 or not isinstance(payload, dict) or "refresh_token" not in payload:
        raise LwaError(
            f"Login with Amazon refused the authorization code (HTTP {resp.status_code}): "
            f"{redact(payload)}. Codes expire after a few minutes; run the command again."
        )
    return payload


def load_auth(config: Config) -> LwaAuth:
    if not config.refresh_token:
        raise RuntimeError("No refresh token configured. Run `amazon-ads-mcp auth` first.")
    return LwaAuth(
        client_id=config.client_id,
        client_secret=config.client_secret,
        refresh_token=config.refresh_token,
        token_url=config.region_info.token_url,
        token_file=config.token_file,
        timeout=config.timeout,
    )
