from __future__ import annotations

import json
import os
from dataclasses import dataclass, field
from pathlib import Path

from dotenv import load_dotenv

DEFAULT_AUDIT_LOG_NAME = "audit.jsonl"
DEFAULT_TOKEN_FILE = Path("secrets") / "amazon-ads-token.json"
# The checkout this package runs from (for an editable install); logs/ and
# secrets/ live here and are gitignored.
_REPO_ROOT = Path(__file__).resolve().parent.parent.parent
# "sse" (HTTP+SSE) is deprecated by the MCP spec; prefer "streamable-http".
TRANSPORTS = ("stdio", "streamable-http", "sse")


@dataclass(frozen=True)
class Region:
    """Amazon Ads API region: API host, Login with Amazon token and consent URLs."""

    code: str
    api_host: str
    token_url: str
    authorize_url: str
    marketplaces: str


# Hosts and LwA URLs from Amazon's "API overview", "Create an authorization grant"
# and "Generate access and refresh tokens" guides.
REGIONS: dict[str, Region] = {
    "NA": Region(
        "NA",
        "https://advertising-api.amazon.com",
        "https://api.amazon.com/auth/o2/token",
        "https://www.amazon.com/ap/oa",
        "US, CA, MX, BR",
    ),
    "EU": Region(
        "EU",
        "https://advertising-api-eu.amazon.com",
        "https://api.amazon.co.uk/auth/o2/token",
        "https://eu.account.amazon.com/ap/oa",
        "UK, FR, IT, ES, DE, NL, AE, PL, TR, EG, SA, SE, BE, IN, ZA",
    ),
    "FE": Region(
        "FE",
        "https://advertising-api-fe.amazon.com",
        "https://api.amazon.co.jp/auth/o2/token",
        "https://apac.account.amazon.com/ap/oa",
        "JP, AU, SG",
    ),
}


def _truthy(value: str | None) -> bool:
    return (value or "").strip().lower() in {"1", "true", "yes", "on"}


def parse_tool_groups(raw: str | None) -> list[str]:
    """Split a comma-separated AMAZON_ADS_TOOL_GROUPS value and check every name.

    Names are case-insensitive and may use '-' for '_'. Empty means all groups.
    """
    from .tools import resolve_tool_groups  # local: tools imports this module

    names = [p.strip().lower().replace("-", "_") for p in (raw or "").split(",")]
    names = [n for n in names if n]
    return resolve_tool_groups(names) if names else []


@dataclass
class Config:
    client_id: str
    client_secret: str
    refresh_token: str | None
    region: str
    profile_id: str | None
    audit_log: Path
    token_file: Path | None = None
    page_size: int = 100
    timeout: float = 30.0
    dry_run: bool = False
    log_level: str = "INFO"
    transport: str = "stdio"
    host: str = "127.0.0.1"
    port: int = 8000
    # Tool modules to register; empty means all (see amazon_ads_mcp.tools.TOOL_GROUPS).
    tool_groups: list[str] = field(default_factory=list)
    # Register only tools annotated read-only (plus the meta tools).
    read_only: bool = False
    # Writes touching more than this many entities need confirm='APPLY'.
    bulk_threshold: int = 10
    # Bid or budget increases above this percentage need confirm='APPLY'.
    max_increase_pct: float = 25.0
    # Optional absolute caps; values above them need confirm='APPLY'.
    max_budget: float | None = None
    max_bid: float | None = None
    # Audit entries older than this are pruned at startup; 0 keeps them.
    audit_retention_days: int = 30

    @property
    def region_info(self) -> Region:
        return REGIONS[self.region]

    @property
    def api_host(self) -> str:
        return self.region_info.api_host


def _path_or_none(raw: str | None) -> Path | None:
    if not raw or not raw.strip():
        return None
    return Path(raw).expanduser().resolve()


def _float_or_none(name: str) -> float | None:
    raw = os.environ.get(name, "").strip()
    if not raw:
        return None
    try:
        return float(raw)
    except ValueError as e:
        raise RuntimeError(f"{name} must be a number, got '{raw}'") from e


def token_file_path() -> Path:
    """Where `amazon-ads-mcp auth` stores the refresh token.

    AMAZON_ADS_TOKEN_FILE, default secrets/amazon-ads-token.json in the checkout.
    """
    return _path_or_none(os.environ.get("AMAZON_ADS_TOKEN_FILE")) or (
        _REPO_ROOT / DEFAULT_TOKEN_FILE
    )


def audit_log_path() -> Path:
    """The audit log location (AMAZON_ADS_AUDIT_LOG, default ./logs/audit.jsonl in the repo)."""
    default = _REPO_ROOT / "logs" / DEFAULT_AUDIT_LOG_NAME
    return _path_or_none(os.environ.get("AMAZON_ADS_AUDIT_LOG")) or default


def read_token_file(path: Path) -> str | None:
    """Return the refresh token stored by `amazon-ads-mcp auth`, or None."""
    if not path.exists():
        return None
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError) as e:
        raise RuntimeError(f"Could not read the token file {path}: {e}") from e
    token = data.get("refresh_token") if isinstance(data, dict) else None
    return token or None


def load_config(env_file: Path | None = None, *, require_refresh_token: bool = True) -> Config:
    """Read configuration from environment (and optional .env file).

    Raises RuntimeError with actionable messages on misconfiguration."""
    if env_file is not None:
        load_dotenv(dotenv_path=env_file, override=False)
    else:
        load_dotenv(override=False)

    client_id = os.environ.get("AMAZON_ADS_CLIENT_ID", "").strip()
    client_secret = os.environ.get("AMAZON_ADS_CLIENT_SECRET", "").strip()
    if not client_id or not client_secret:
        raise RuntimeError(
            "AMAZON_ADS_CLIENT_ID and AMAZON_ADS_CLIENT_SECRET must be set.\n"
            "  - Find them in the Amazon Developer console -> Login with Amazon -> your\n"
            "    security profile -> Show Client ID and Client Secret.\n"
            "  - The client ID starts with 'amzn1.application-oa2-client.'"
        )

    region = os.environ.get("AMAZON_ADS_REGION", "EU").strip().upper() or "EU"
    if region not in REGIONS:
        raise RuntimeError(f"AMAZON_ADS_REGION must be one of NA, EU or FE, got '{region}'.")

    token_file = token_file_path()
    refresh_token = os.environ.get("AMAZON_ADS_REFRESH_TOKEN", "").strip() or None
    if refresh_token is None:
        refresh_token = read_token_file(token_file)
    if refresh_token is None and require_refresh_token:
        raise RuntimeError(
            "No refresh token configured. Either:\n"
            "  - run `amazon-ads-mcp auth` once (saves it to "
            f"{token_file}), or\n"
            "  - set AMAZON_ADS_REFRESH_TOKEN (starts with 'Atzr|'), or\n"
            "  - set AMAZON_ADS_TOKEN_FILE to the file `amazon-ads-mcp auth` wrote."
        )

    profile_id = os.environ.get("AMAZON_ADS_PROFILE_ID", "").strip() or None
    if profile_id and not profile_id.lstrip("-").isdigit():
        raise RuntimeError(f"AMAZON_ADS_PROFILE_ID must be numeric, got '{profile_id}'.")

    audit_path = audit_log_path()
    audit_path.parent.mkdir(parents=True, exist_ok=True)

    transport = os.environ.get("AMAZON_ADS_TRANSPORT", "stdio").strip().lower()
    if transport not in TRANSPORTS:
        raise RuntimeError(
            f"AMAZON_ADS_TRANSPORT must be one of {', '.join(TRANSPORTS)}, got '{transport}'."
        )

    def _int(name: str, default: str) -> int:
        try:
            return int(os.environ.get(name, default))
        except ValueError as e:
            raise RuntimeError(f"{name} must be an integer") from e

    def _float(name: str, default: str) -> float:
        try:
            return float(os.environ.get(name, default))
        except ValueError as e:
            raise RuntimeError(f"{name} must be a number") from e

    return Config(
        client_id=client_id,
        client_secret=client_secret,
        refresh_token=refresh_token,
        region=region,
        profile_id=profile_id,
        audit_log=audit_path,
        token_file=token_file,
        page_size=_int("AMAZON_ADS_PAGE_SIZE", "100"),
        timeout=_float("AMAZON_ADS_TIMEOUT", "30"),
        dry_run=_truthy(os.environ.get("AMAZON_ADS_DRY_RUN")),
        log_level=os.environ.get("AMAZON_ADS_LOG_LEVEL", "INFO").upper(),
        transport=transport,
        host=os.environ.get("AMAZON_ADS_HOST", "127.0.0.1"),
        port=_int("AMAZON_ADS_PORT", "8000"),
        tool_groups=parse_tool_groups(os.environ.get("AMAZON_ADS_TOOL_GROUPS")),
        read_only=_truthy(os.environ.get("AMAZON_ADS_READ_ONLY")),
        bulk_threshold=_int("AMAZON_ADS_BULK_THRESHOLD", "10"),
        max_increase_pct=_float("AMAZON_ADS_MAX_INCREASE_PCT", "25"),
        max_budget=_float_or_none("AMAZON_ADS_MAX_BUDGET"),
        max_bid=_float_or_none("AMAZON_ADS_MAX_BID"),
        audit_retention_days=_int("AMAZON_ADS_AUDIT_RETENTION_DAYS", "30"),
    )
