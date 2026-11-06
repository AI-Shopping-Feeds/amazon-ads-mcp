"""CLI: transports, the auth helpers, purge and describe."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any
from urllib.parse import parse_qs, urlparse

import click
import pytest
from click.testing import CliRunner

from amazon_ads_mcp import cli


class _FakeServer:
    def __init__(self) -> None:
        self.calls: list[tuple[str, dict[str, Any]]] = []

    def run(self, transport: str, **kwargs: Any) -> None:
        self.calls.append((transport, kwargs))


@pytest.fixture
def base_env(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    monkeypatch.setenv("AMAZON_ADS_CLIENT_ID", "amzn1.application-oa2-client.cli")
    monkeypatch.setenv("AMAZON_ADS_CLIENT_SECRET", "cli-secret-value")
    monkeypatch.setenv("AMAZON_ADS_REFRESH_TOKEN", "Atzr|cli-refresh")
    monkeypatch.setenv("AMAZON_ADS_AUDIT_LOG", str(tmp_path / "logs" / "audit.jsonl"))
    monkeypatch.setenv("AMAZON_ADS_TOKEN_FILE", str(tmp_path / "secrets" / "token.json"))
    for var in (
        "AMAZON_ADS_TRANSPORT",
        "AMAZON_ADS_HOST",
        "AMAZON_ADS_PORT",
        "AMAZON_ADS_TOOL_GROUPS",
        "AMAZON_ADS_REGION",
    ):
        monkeypatch.delenv(var, raising=False)
    return tmp_path


@pytest.fixture
def fake_run(base_env: Path, monkeypatch: pytest.MonkeyPatch):
    server = _FakeServer()
    monkeypatch.setattr(cli, "build_server", lambda config: server)
    warnings: list[str] = []
    monkeypatch.setattr(cli.logger, "warning", lambda msg, *args: warnings.append(msg % args))

    def invoke(*args: str):
        env_file = str(base_env / "missing.env")
        result = CliRunner().invoke(cli.cli, ["--env", env_file, *args, "run"], obj={})
        assert result.exit_code == 0, result.output
        return server.calls, warnings

    return invoke


def test_stdio_is_the_default(fake_run) -> None:
    calls, warnings = fake_run()
    assert calls == [("stdio", {})]
    assert warnings == []


def test_streamable_http_gets_host_and_port(fake_run) -> None:
    calls, _ = fake_run("--transport", "streamable-http", "--port", "9123")
    assert calls == [("streamable-http", {"host": "127.0.0.1", "port": 9123})]


def test_non_loopback_host_warns(fake_run) -> None:
    _, warnings = fake_run("--transport", "streamable-http", "--host", "0.0.0.0")
    assert any("no authentication" in w for w in warnings)


def test_authorization_url_uses_regional_consent_page() -> None:
    url = cli.authorization_url(
        region="EU", client_id="cid", redirect_uri="http://localhost:8765/callback", state="st"
    )
    parsed = urlparse(url)
    assert (
        f"{parsed.scheme}://{parsed.netloc}{parsed.path}" == "https://eu.account.amazon.com/ap/oa"
    )
    q = parse_qs(parsed.query)
    assert q["scope"] == ["advertising::campaign_management"]
    assert q["response_type"] == ["code"]
    assert q["state"] == ["st"]
    assert cli.authorization_url(
        region="NA", client_id="c", redirect_uri="r", state="s"
    ).startswith("https://www.amazon.com/ap/oa?")


def test_parse_redirect() -> None:
    assert cli.parse_redirect("https://amazon.com/?code=ABC&scope=x&state=st", "st") == "ABC"
    assert cli.parse_redirect("  ABC  ", "st") == "ABC"
    with pytest.raises(click.ClickException, match="state"):
        cli.parse_redirect("https://amazon.com/?code=ABC&state=other", "st")
    with pytest.raises(click.ClickException, match="error"):
        cli.parse_redirect("https://amazon.com/?error=access_denied&state=st&code=", "st")


def test_auth_manual_flow_saves_token_without_printing_it(
    base_env: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(cli.secrets, "token_urlsafe", lambda n: "fixedstate")
    monkeypatch.setattr(cli.webbrowser, "open", lambda url: True)
    seen: dict[str, Any] = {}

    def fake_exchange(**kwargs: Any) -> dict[str, Any]:
        seen.update(kwargs)
        return {"refresh_token": "Atzr|brand-new", "access_token": "Atza|x"}

    monkeypatch.setattr(cli, "exchange_code", fake_exchange)
    result = CliRunner().invoke(
        cli.cli,
        ["--env", str(base_env / "missing.env"), "auth", "--manual", "--no-browser"],
        input="https://amazon.com/?code=THECODE&state=fixedstate\n",
        obj={},
    )
    assert result.exit_code == 0, result.output
    assert seen["code"] == "THECODE"
    assert seen["redirect_uri"] == "https://amazon.com"
    assert seen["token_url"] == "https://api.amazon.co.uk/auth/o2/token"
    token_file = base_env / "secrets" / "token.json"
    assert json.loads(token_file.read_text())["refresh_token"] == "Atzr|brand-new"
    assert "brand-new" not in result.output
    assert "cli-secret-value" not in result.output


def test_purge_deletes_audit_and_token(base_env: Path) -> None:
    audit = base_env / "logs" / "audit.jsonl"
    token = base_env / "secrets" / "token.json"
    audit.parent.mkdir(parents=True)
    token.parent.mkdir(parents=True)
    audit.write_text("{}\n")
    token.write_text("{}")
    result = CliRunner().invoke(
        cli.cli, ["--env", str(base_env / "missing.env"), "purge", "--yes"], obj={}
    )
    assert result.exit_code == 0, result.output
    assert not audit.exists()
    assert not token.exists()


def test_describe_hides_secrets(base_env: Path) -> None:
    result = CliRunner().invoke(
        cli.cli, ["--env", str(base_env / "missing.env"), "describe"], obj={}
    )
    assert result.exit_code == 0, result.output
    assert "cli-secret-value" not in result.output
    assert "cli-refresh" not in result.output
    assert json.loads(result.output)["refresh_token"] == "set"


def test_unknown_transport_is_rejected() -> None:
    result = CliRunner().invoke(cli.cli, ["--transport", "websocket", "run"], obj={})
    assert result.exit_code != 0
    assert "streamable-http" in result.output
