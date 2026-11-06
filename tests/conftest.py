"""Shared fixtures for the test suite.

All tests run fully offline: HTTP is mocked with respx and no real Login with
Amazon credentials are used.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest

from amazon_ads_mcp.audit import AuditLog
from amazon_ads_mcp.client import AmazonAdsClient
from amazon_ads_mcp.config import Config

PROFILE = "1111111111"
BASE = "https://advertising-api-eu.amazon.com"
CLIENT_ID = "amzn1.application-oa2-client.testclient123456"


class FakeAuth:
    """Stand-in for LwaAuth in tests."""

    account_label = "fake:test"

    def __init__(self) -> None:
        self.invalidated = 0
        self.token = "Atza|fake-access-token"

    def access_token(self) -> str:
        return self.token

    def invalidate(self) -> None:
        self.invalidated += 1


@pytest.fixture(autouse=True)
def _isolated_home(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """Point ~ and the working folder at temp folders.

    The server reads ~/.amazon-ads-mcp/.env and ./.env, and writes its token
    and audit log under ~/.amazon-ads-mcp, so tests must never see the real ones.
    """
    home = tmp_path / "home"
    home.mkdir()
    monkeypatch.setenv("HOME", str(home))
    monkeypatch.setenv("USERPROFILE", str(home))
    work = tmp_path / "work"
    work.mkdir()
    monkeypatch.chdir(work)
    return home


@pytest.fixture(autouse=True)
def _no_sleep(monkeypatch: pytest.MonkeyPatch) -> list[float]:
    slept: list[float] = []
    monkeypatch.setattr("amazon_ads_mcp.client.time.sleep", lambda s: slept.append(s))
    return slept


@pytest.fixture
def tmp_audit_log(tmp_path: Path) -> Path:
    return tmp_path / "audit.jsonl"


@pytest.fixture
def config(tmp_audit_log: Path, tmp_path: Path) -> Config:
    return Config(
        client_id=CLIENT_ID,
        client_secret="test-client-secret-value",
        refresh_token="Atzr|fake-refresh-token",
        region="EU",
        profile_id=PROFILE,
        audit_log=tmp_audit_log,
        token_file=tmp_path / "token.json",
        page_size=100,
        timeout=5.0,
        dry_run=False,
    )


@pytest.fixture
def audit(tmp_audit_log: Path) -> AuditLog:
    return AuditLog(tmp_audit_log)


@pytest.fixture
def fake_auth() -> FakeAuth:
    return FakeAuth()


@pytest.fixture
def client(config: Config, audit: AuditLog, fake_auth: FakeAuth):
    c = AmazonAdsClient(config, fake_auth, audit)
    yield c
    c.close()


def audit_entries(path: Path) -> list[dict[str, Any]]:
    import json

    if not path.exists():
        return []
    return [json.loads(line) for line in path.read_text().splitlines() if line.strip()]
