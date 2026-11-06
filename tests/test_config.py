from __future__ import annotations

import json
import os
import stat
from pathlib import Path

import pytest

from amazon_ads_mcp import config as config_module
from amazon_ads_mcp.config import env_files, load_config, make_private_dir

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
    "AMAZON_ADS_ALLOW_REMOTE",
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


def test_default_paths_live_in_the_home_folder(
    env, monkeypatch: pytest.MonkeyPatch, _isolated_home: Path
) -> None:
    monkeypatch.delenv("AMAZON_ADS_AUDIT_LOG")
    monkeypatch.delenv("AMAZON_ADS_TOKEN_FILE")
    cfg = load_config(env_file=env(**_creds()), require_refresh_token=False)
    app = _isolated_home / ".amazon-ads-mcp"
    assert cfg.token_file == app / "secrets" / "amazon-ads-token.json"
    assert cfg.audit_log == app / "logs" / "audit.jsonl"
    # Nothing depends on where the package is installed.
    package_dir = Path(config_module.__file__).resolve().parent
    assert package_dir not in cfg.audit_log.parents
    assert cfg.audit_log.parent.is_dir()
    if os.name == "posix":
        assert stat.S_IMODE(app.stat().st_mode) == 0o700
        assert stat.S_IMODE(cfg.audit_log.parent.stat().st_mode) == 0o700


def test_make_private_dir_leaves_existing_folders_alone(tmp_path: Path) -> None:
    shared = tmp_path / "shared"
    shared.mkdir(mode=0o755)
    os.chmod(shared, 0o755)
    make_private_dir(shared / "a" / "b")
    assert (shared / "a" / "b").is_dir()
    if os.name == "posix":
        assert stat.S_IMODE(shared.stat().st_mode) == 0o755
        assert stat.S_IMODE((shared / "a").stat().st_mode) == 0o700
        assert stat.S_IMODE((shared / "a" / "b").stat().st_mode) == 0o700


def test_env_files_priority(env, monkeypatch: pytest.MonkeyPatch, _isolated_home: Path) -> None:
    for var in ("AMAZON_ADS_CLIENT_ID", "AMAZON_ADS_CLIENT_SECRET", "AMAZON_ADS_REFRESH_TOKEN"):
        monkeypatch.delenv(var, raising=False)
    app = _isolated_home / ".amazon-ads-mcp"
    app.mkdir()
    (app / ".env").write_text(
        "AMAZON_ADS_CLIENT_ID=amzn1.application-oa2-client.home\n"
        "AMAZON_ADS_CLIENT_SECRET=home-secret\n"
        "AMAZON_ADS_REFRESH_TOKEN=Atzr|home\n"
        "AMAZON_ADS_PROFILE_ID=1\n"
    )
    local = Path.cwd() / ".env"
    local.write_text("AMAZON_ADS_CLIENT_SECRET=local-secret\nAMAZON_ADS_PROFILE_ID=2\n")
    monkeypatch.setenv("AMAZON_ADS_PROFILE_ID", "3")

    assert env_files() == [local, app / ".env"]
    cfg = load_config()
    assert cfg.client_id.endswith(".home")  # only in ~/.amazon-ads-mcp/.env
    assert cfg.client_secret == "local-secret"  # ./.env beats the home .env
    assert cfg.profile_id == "3"  # the environment beats both


def test_explicit_env_file_replaces_the_local_one(
    env, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    for var in ("AMAZON_ADS_CLIENT_ID", "AMAZON_ADS_CLIENT_SECRET", "AMAZON_ADS_REFRESH_TOKEN"):
        monkeypatch.delenv(var, raising=False)
    (Path.cwd() / ".env").write_text("AMAZON_ADS_CLIENT_SECRET=local-secret\n")
    chosen = tmp_path / "chosen.env"
    chosen.write_text(
        "AMAZON_ADS_CLIENT_ID=amzn1.application-oa2-client.chosen\n"
        "AMAZON_ADS_CLIENT_SECRET=chosen-secret\n"
        "AMAZON_ADS_REFRESH_TOKEN=Atzr|chosen\n"
    )
    assert env_files(chosen) == [chosen]
    assert load_config(env_file=chosen).client_secret == "chosen-secret"


def test_allow_remote_flag(env) -> None:
    cfg = load_config(env_file=env(**_creds(), AMAZON_ADS_REFRESH_TOKEN="Atzr|x"))
    assert cfg.allow_remote is False
    cfg = load_config(
        env_file=env(**_creds(), AMAZON_ADS_REFRESH_TOKEN="Atzr|x", AMAZON_ADS_ALLOW_REMOTE="true")
    )
    assert cfg.allow_remote is True
