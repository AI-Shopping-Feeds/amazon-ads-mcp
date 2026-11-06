from __future__ import annotations

import json
from pathlib import Path

import pytest

from amazon_ads_mcp.config import load_config

VARS = (
    "AMAZON_ADS_CLIENT_ID",
    "AMAZON_ADS_CLIENT_SECRET",
    "AMAZON_ADS_REFRESH_TOKEN",
    "AMAZON_ADS_TOKEN_FILE",
    "AMAZON_ADS_REGION",
    "AMAZON_ADS_PROFILE_ID",
    "AMAZON_ADS_AUDIT_LOG",
    "AMAZON_ADS_TOOL_GROUPS",
    "AMAZON_ADS_READ_ONLY",
    "AMAZON_ADS_DRY_RUN",
    "AMAZON_ADS_MAX_BUDGET",
    "AMAZON_ADS_AUDIT_RETENTION_DAYS",
)


@pytest.fixture
def env(monkeypatch: pytest.MonkeyPatch, tmp_path: Path):
    for v in VARS:
        monkeypatch.delenv(v, raising=False)
    monkeypatch.setenv("AMAZON_ADS_AUDIT_LOG", str(tmp_path / "audit.jsonl"))
    monkeypatch.setenv("AMAZON_ADS_TOKEN_FILE", str(tmp_path / "token.json"))

    def set_(**values: str) -> Path:
        for k, val in values.items():
            monkeypatch.setenv(k, val)
        return tmp_path / "missing.env"

    return set_


def _creds() -> dict[str, str]:
    return {
        "AMAZON_ADS_CLIENT_ID": "amzn1.application-oa2-client.x",
        "AMAZON_ADS_CLIENT_SECRET": "s3cr3t-value",
    }


def test_missing_client_credentials(env) -> None:
    with pytest.raises(RuntimeError, match="AMAZON_ADS_CLIENT_ID"):
        load_config(env_file=env())


def test_missing_refresh_token_points_to_auth(env) -> None:
    with pytest.raises(RuntimeError, match="amazon-ads-mcp auth"):
        load_config(env_file=env(**_creds()))
    cfg = load_config(env_file=env(**_creds()), require_refresh_token=False)
    assert cfg.refresh_token is None


def test_defaults(env) -> None:
    cfg = load_config(env_file=env(**_creds(), AMAZON_ADS_REFRESH_TOKEN="Atzr|x"))
    assert cfg.region == "EU"
    assert cfg.api_host == "https://advertising-api-eu.amazon.com"
    assert cfg.region_info.token_url == "https://api.amazon.co.uk/auth/o2/token"
    assert cfg.dry_run is False
    assert cfg.read_only is False
    assert cfg.audit_retention_days == 30
    assert cfg.max_increase_pct == 25.0
    assert cfg.max_budget is None


def test_token_file_is_read(env, tmp_path: Path) -> None:
    (tmp_path / "token.json").write_text(json.dumps({"refresh_token": "Atzr|from-file"}))
    cfg = load_config(env_file=env(**_creds()))
    assert cfg.refresh_token == "Atzr|from-file"


@pytest.mark.parametrize(
    ("region", "host"),
    [("na", "https://advertising-api.amazon.com"), ("FE", "https://advertising-api-fe.amazon.com")],
)
def test_regions(env, region: str, host: str) -> None:
    cfg = load_config(
        env_file=env(**_creds(), AMAZON_ADS_REFRESH_TOKEN="Atzr|x", AMAZON_ADS_REGION=region)
    )
    assert cfg.api_host == host


def test_bad_values(env) -> None:
    with pytest.raises(RuntimeError, match="AMAZON_ADS_REGION"):
        load_config(env_file=env(**_creds(), AMAZON_ADS_REFRESH_TOKEN="x", AMAZON_ADS_REGION="US"))
    with pytest.raises(RuntimeError, match="AMAZON_ADS_PROFILE_ID"):
        load_config(env_file=env(AMAZON_ADS_REGION="EU", AMAZON_ADS_PROFILE_ID="abc"))
    with pytest.raises(RuntimeError, match="AMAZON_ADS_MAX_BUDGET"):
        load_config(env_file=env(AMAZON_ADS_PROFILE_ID="1", AMAZON_ADS_MAX_BUDGET="lots"))


def test_flags(env) -> None:
    cfg = load_config(
        env_file=env(
            **_creds(),
            AMAZON_ADS_REFRESH_TOKEN="Atzr|x",
            AMAZON_ADS_DRY_RUN="true",
            AMAZON_ADS_READ_ONLY="1",
            AMAZON_ADS_MAX_BUDGET="100",
            AMAZON_ADS_AUDIT_RETENTION_DAYS="7",
            AMAZON_ADS_PROFILE_ID="123",
        )
    )
    assert cfg.dry_run and cfg.read_only
    assert cfg.max_budget == 100.0
    assert cfg.audit_retention_days == 7
    assert cfg.profile_id == "123"
