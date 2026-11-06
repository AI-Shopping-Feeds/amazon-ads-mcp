from __future__ import annotations

import json
import os
import stat
from pathlib import Path

import httpx
import pytest
import respx

from amazon_ads_mcp import auth as auth_mod
from amazon_ads_mcp.auth import LwaAuth, LwaError, redact, save_token_file

TOKEN_URL = "https://api.amazon.co.uk/auth/o2/token"


def _auth(tmp_path: Path, token_file: Path | None = None) -> LwaAuth:
    return LwaAuth(
        client_id="amzn1.application-oa2-client.abc123",
        client_secret="super-secret-client-value",
        refresh_token="Atzr|refresh-one",
        token_url=TOKEN_URL,
        token_file=token_file,
    )


@respx.mock
def test_refresh_sends_refresh_grant_and_caches(tmp_path: Path) -> None:
    route = respx.post(TOKEN_URL).mock(
        return_value=httpx.Response(
            200, json={"access_token": "Atza|access-1", "expires_in": 3600, "token_type": "bearer"}
        )
    )
    a = _auth(tmp_path)
    assert a.access_token() == "Atza|access-1"
    assert a.access_token() == "Atza|access-1"
    assert route.call_count == 1
    form = dict(x.split("=", 1) for x in route.calls.last.request.content.decode().split("&"))
    assert form["grant_type"] == "refresh_token"
    assert form["client_id"] == "amzn1.application-oa2-client.abc123"
    assert "refresh-one" in form["refresh_token"]


@respx.mock
def test_expired_token_is_refreshed(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    route = respx.post(TOKEN_URL).mock(
        side_effect=[
            httpx.Response(200, json={"access_token": "Atza|first", "expires_in": 3600}),
            httpx.Response(200, json={"access_token": "Atza|second", "expires_in": 3600}),
        ]
    )
    now = [1_000_000.0]
    monkeypatch.setattr(auth_mod.time, "time", lambda: now[0])
    a = _auth(tmp_path)
    assert a.access_token() == "Atza|first"
    now[0] += 3600 - 30  # inside the safety margin before expiry
    assert a.access_token() == "Atza|second"
    assert route.call_count == 2


@respx.mock
def test_invalidate_forces_refresh(tmp_path: Path) -> None:
    route = respx.post(TOKEN_URL).mock(
        return_value=httpx.Response(200, json={"access_token": "Atza|x", "expires_in": 3600})
    )
    a = _auth(tmp_path)
    a.access_token()
    a.invalidate()
    a.access_token()
    assert route.call_count == 2


@respx.mock
def test_refusal_is_redacted(tmp_path: Path) -> None:
    respx.post(TOKEN_URL).mock(
        return_value=httpx.Response(
            400,
            json={
                "error": "invalid_grant",
                "error_description": "bad token Atzr|refresh-one",
            },
        )
    )
    a = _auth(tmp_path)
    with pytest.raises(LwaError) as ei:
        a.access_token()
    msg = str(ei.value)
    assert "invalid_grant" in msg
    assert "refresh-one" not in msg
    assert "amazon-ads-mcp auth" in msg


@respx.mock
def test_rotated_refresh_token_is_saved(tmp_path: Path) -> None:
    token_file = tmp_path / "token.json"
    save_token_file(token_file, {"refresh_token": "Atzr|refresh-one", "region": "EU"})
    respx.post(TOKEN_URL).mock(
        return_value=httpx.Response(
            200,
            json={
                "access_token": "Atza|x",
                "expires_in": 3600,
                "refresh_token": "Atzr|refresh-two",
            },
        )
    )
    _auth(tmp_path, token_file).access_token()
    data = json.loads(token_file.read_text())
    assert data == {"refresh_token": "Atzr|refresh-two", "region": "EU"}


def test_token_file_is_owner_only(tmp_path: Path) -> None:
    path = tmp_path / "secrets" / "token.json"
    save_token_file(path, {"refresh_token": "Atzr|abc"})
    if os.name == "posix":
        assert stat.S_IMODE(path.stat().st_mode) == 0o600
        assert stat.S_IMODE(path.parent.stat().st_mode) == 0o700


def test_redact_hides_tokens_and_secret_keys() -> None:
    auth_mod.register_secret("my-very-secret-client-secret")
    out = redact(
        {
            "message": "token Atza|abcDEF123 and my-very-secret-client-secret",
            "refresh_token": "Atzr|zzz",
            "client_secret": "whatever",
            "nested": [{"Authorization": "Bearer Atza|q"}],
            "code": "SUCCESS",
        }
    )
    assert out["message"] == "token *** and ***"
    assert out["refresh_token"] == "***"
    assert out["client_secret"] == "***"
    assert out["nested"][0]["Authorization"] == "***"
    assert out["code"] == "SUCCESS"
