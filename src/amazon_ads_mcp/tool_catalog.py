"""Title and MCP annotations for every amazon_ads_* tool.

`AmazonAdsMCPServer.tool()` looks each tool up here by name, so the tool modules
stay free of metadata. Every tool must have an entry: tests/test_mcp_client.py
fails if a registered tool is missing or an entry has no tool.

Annotation kinds (all API tools are open-world: they call the Amazon Ads API):

* READ: changes nothing in the ads account. Includes read-only POSTs such as
  list and query calls and recommendations.
* REPORT: requests a report. Changes nothing in the ads account, but each call
  starts a new report job, so it isn't idempotent.
* WRITE: creates something; repeating it creates it again.
* UPSERT: an update or state change; repeating it changes nothing more.
* DESTRUCTIVE: archives, deletes or detaches; archived entities can't be re-enabled.
* DESTRUCTIVE_ONCE: the raw request tool, which may do anything.
* LOCAL_*: touches only this server (audit log, session settings).
"""

from __future__ import annotations

from typing import NamedTuple

from mcp.types import ToolAnnotations


def _ann(*, read_only: bool, destructive: bool, idempotent: bool, open_world: bool = True):
    return ToolAnnotations(
        read_only_hint=read_only,
        destructive_hint=destructive,
        idempotent_hint=idempotent,
        open_world_hint=open_world,
    )


READ = _ann(read_only=True, destructive=False, idempotent=True)
REPORT = _ann(read_only=True, destructive=False, idempotent=False)
WRITE = _ann(read_only=False, destructive=False, idempotent=False)
UPSERT = _ann(read_only=False, destructive=False, idempotent=True)
DESTRUCTIVE = _ann(read_only=False, destructive=True, idempotent=True)
DESTRUCTIVE_ONCE = _ann(read_only=False, destructive=True, idempotent=False)
LOCAL_READ = _ann(read_only=True, destructive=False, idempotent=True, open_world=False)
LOCAL_SETTING = _ann(read_only=False, destructive=False, idempotent=True, open_world=False)


class ToolSpec(NamedTuple):
    title: str
    annotations: ToolAnnotations


# Registered regardless of AMAZON_ADS_TOOL_GROUPS and AMAZON_ADS_READ_ONLY.
ALWAYS_REGISTERED = frozenset(
    {
        "amazon_ads_describe_server",
        "amazon_ads_health_check",
        "amazon_ads_audit_lookup",
        "amazon_ads_audit_tail",
        "amazon_ads_set_dry_run",
    }
)

_CATALOG: dict[str, tuple[str, ToolAnnotations]] = {
    # server (meta)
    "amazon_ads_describe_server": ("Describe the server configuration", LOCAL_READ),
    "amazon_ads_health_check": ("Check the token and list profiles", READ),
    "amazon_ads_audit_lookup": ("Look up an audit log entry", LOCAL_READ),
    "amazon_ads_audit_tail": ("Show recent audit log entries", LOCAL_READ),
    "amazon_ads_set_dry_run": ("Turn dry-run mode on or off", LOCAL_SETTING),
    # profiles
    "amazon_ads_list_profiles": ("List advertising profiles", READ),
    "amazon_ads_get_profile": ("Get a profile", READ),
    "amazon_ads_list_manager_accounts": ("List manager accounts", READ),
    # sp_campaigns
    "amazon_ads_sp_list_campaigns": ("List Sponsored Products campaigns", READ),
    "amazon_ads_sp_create_campaigns": ("Create Sponsored Products campaigns", WRITE),
    "amazon_ads_sp_update_campaigns": ("Update Sponsored Products campaigns", UPSERT),
    "amazon_ads_sp_archive_campaigns": ("Archive Sponsored Products campaigns", DESTRUCTIVE),
    "amazon_ads_sp_list_ad_groups": ("List Sponsored Products ad groups", READ),
    "amazon_ads_sp_create_ad_groups": ("Create Sponsored Products ad groups", WRITE),
    "amazon_ads_sp_update_ad_groups": ("Update Sponsored Products ad groups", UPSERT),
    "amazon_ads_sp_archive_ad_groups": ("Archive Sponsored Products ad groups", DESTRUCTIVE),
    # sp_ads
    "amazon_ads_sp_list_product_ads": ("List Sponsored Products product ads", READ),
    "amazon_ads_sp_create_product_ads": ("Create Sponsored Products product ads", WRITE),
    "amazon_ads_sp_update_product_ads": ("Update Sponsored Products product ads", UPSERT),
    "amazon_ads_sp_archive_product_ads": ("Archive Sponsored Products product ads", DESTRUCTIVE),
    # sp_targeting
    "amazon_ads_sp_list_keywords": ("List Sponsored Products keywords", READ),
    "amazon_ads_sp_create_keywords": ("Create Sponsored Products keywords", WRITE),
    "amazon_ads_sp_update_keywords": ("Update Sponsored Products keywords", UPSERT),
    "amazon_ads_sp_archive_keywords": ("Archive Sponsored Products keywords", DESTRUCTIVE),
    "amazon_ads_sp_list_negative_keywords": ("List Sponsored Products negative keywords", READ),
    "amazon_ads_sp_create_negative_keywords": (
        "Create Sponsored Products negative keywords",
        WRITE,
    ),
    "amazon_ads_sp_archive_negative_keywords": (
        "Archive Sponsored Products negative keywords",
        DESTRUCTIVE,
    ),
    "amazon_ads_sp_list_campaign_negative_keywords": (
        "List Sponsored Products campaign negative keywords",
        READ,
    ),
    "amazon_ads_sp_create_campaign_negative_keywords": (
        "Create Sponsored Products campaign negative keywords",
        WRITE,
    ),
    "amazon_ads_sp_archive_campaign_negative_keywords": (
        "Archive Sponsored Products campaign negative keywords",
        DESTRUCTIVE,
    ),
    "amazon_ads_sp_list_targets": ("List Sponsored Products product targets", READ),
    "amazon_ads_sp_create_targets": ("Create Sponsored Products product targets", WRITE),
    "amazon_ads_sp_update_targets": ("Update Sponsored Products product targets", UPSERT),
    "amazon_ads_sp_archive_targets": ("Archive Sponsored Products product targets", DESTRUCTIVE),
    "amazon_ads_sp_list_negative_targets": (
        "List Sponsored Products negative product targets",
        READ,
    ),
    "amazon_ads_sp_create_negative_targets": (
        "Create Sponsored Products negative product targets",
        WRITE,
    ),
    "amazon_ads_sp_archive_negative_targets": (
        "Archive Sponsored Products negative product targets",
        DESTRUCTIVE,
    ),
    "amazon_ads_sp_list_campaign_negative_targets": (
        "List Sponsored Products campaign negative product targets",
        READ,
    ),
    "amazon_ads_sp_create_campaign_negative_targets": (
        "Create Sponsored Products campaign negative product targets",
        WRITE,
    ),
    "amazon_ads_sp_archive_campaign_negative_targets": (
        "Archive Sponsored Products campaign negative product targets",
        DESTRUCTIVE,
    ),
    # sp_recommendations
    "amazon_ads_sp_budget_recommendations": ("Get Sponsored Products budget recommendations", READ),
    "amazon_ads_sp_bid_recommendations": ("Get Sponsored Products bid recommendations", READ),
    "amazon_ads_sp_keyword_recommendations": (
        "Get Sponsored Products keyword recommendations",
        READ,
    ),
    # bulk
    "amazon_ads_sp_adjust_bids": ("Adjust many Sponsored Products bids", WRITE),
    "amazon_ads_sp_set_states": ("Pause or enable many Sponsored Products entities", UPSERT),
    # sponsored_brands
    "amazon_ads_sb_list_campaigns": ("List Sponsored Brands campaigns", READ),
    "amazon_ads_sb_create_campaigns": ("Create Sponsored Brands campaigns", WRITE),
    "amazon_ads_sb_update_campaigns": ("Update Sponsored Brands campaigns", UPSERT),
    "amazon_ads_sb_archive_campaigns": ("Archive Sponsored Brands campaigns", DESTRUCTIVE),
    "amazon_ads_sb_list_ad_groups": ("List Sponsored Brands ad groups", READ),
    "amazon_ads_sb_create_ad_groups": ("Create Sponsored Brands ad groups", WRITE),
    "amazon_ads_sb_update_ad_groups": ("Update Sponsored Brands ad groups", UPSERT),
    "amazon_ads_sb_archive_ad_groups": ("Archive Sponsored Brands ad groups", DESTRUCTIVE),
    "amazon_ads_sb_list_ads": ("List Sponsored Brands ads", READ),
    "amazon_ads_sb_update_ads": ("Update Sponsored Brands ads", UPSERT),
    "amazon_ads_sb_archive_ads": ("Archive Sponsored Brands ads", DESTRUCTIVE),
    "amazon_ads_sb_list_keywords": ("List Sponsored Brands keywords", READ),
    "amazon_ads_sb_create_keywords": ("Create Sponsored Brands keywords", WRITE),
    "amazon_ads_sb_update_keywords": ("Update Sponsored Brands keywords", UPSERT),
    "amazon_ads_sb_archive_keywords": ("Archive Sponsored Brands keywords", DESTRUCTIVE),
    "amazon_ads_sb_create_ads": ("Create Sponsored Brands ads", WRITE),
    # sponsored_display
    "amazon_ads_sd_list_campaigns": ("List Sponsored Display campaigns", READ),
    "amazon_ads_sd_create_campaigns": ("Create Sponsored Display campaigns", WRITE),
    "amazon_ads_sd_update_campaigns": ("Update Sponsored Display campaigns", UPSERT),
    "amazon_ads_sd_archive_campaigns": ("Archive Sponsored Display campaigns", DESTRUCTIVE),
    "amazon_ads_sd_list_ad_groups": ("List Sponsored Display ad groups", READ),
    "amazon_ads_sd_create_ad_groups": ("Create Sponsored Display ad groups", WRITE),
    "amazon_ads_sd_update_ad_groups": ("Update Sponsored Display ad groups", UPSERT),
    "amazon_ads_sd_archive_ad_groups": ("Archive Sponsored Display ad groups", DESTRUCTIVE),
    "amazon_ads_sd_list_product_ads": ("List Sponsored Display product ads", READ),
    "amazon_ads_sd_create_product_ads": ("Create Sponsored Display product ads", WRITE),
    "amazon_ads_sd_update_product_ads": ("Update Sponsored Display product ads", UPSERT),
    "amazon_ads_sd_archive_product_ads": ("Archive Sponsored Display product ads", DESTRUCTIVE),
    "amazon_ads_sd_list_targets": ("List Sponsored Display targets", READ),
    "amazon_ads_sd_create_targets": ("Create Sponsored Display targets", WRITE),
    "amazon_ads_sd_update_targets": ("Update Sponsored Display targets", UPSERT),
    "amazon_ads_sd_archive_targets": ("Archive Sponsored Display targets", DESTRUCTIVE),
    "amazon_ads_sd_list_negative_targets": ("List Sponsored Display negative targets", READ),
    "amazon_ads_sd_create_negative_targets": ("Create Sponsored Display negative targets", WRITE),
    "amazon_ads_sd_archive_negative_targets": (
        "Archive Sponsored Display negative targets",
        DESTRUCTIVE,
    ),
    # reporting
    "amazon_ads_create_report": ("Request a performance report", REPORT),
    "amazon_ads_get_report": ("Check a report's status", READ),
    "amazon_ads_download_report": ("Download a finished report", READ),
    "amazon_ads_run_report": ("Run a report and return its rows", REPORT),
    # portfolios
    "amazon_ads_list_portfolios": ("List portfolios", READ),
    "amazon_ads_create_portfolios": ("Create portfolios", WRITE),
    "amazon_ads_update_portfolios": ("Update portfolios", UPSERT),
    # budget_rules
    "amazon_ads_sp_list_budget_rules": ("List Sponsored Products budget rules", READ),
    "amazon_ads_sp_get_budget_rule": ("Get a Sponsored Products budget rule", READ),
    "amazon_ads_sp_list_campaign_budget_rules": ("List a campaign's budget rules", READ),
    "amazon_ads_sp_create_budget_rules": ("Create Sponsored Products budget rules", WRITE),
    "amazon_ads_sp_update_budget_rules": ("Update Sponsored Products budget rules", UPSERT),
    "amazon_ads_sp_attach_budget_rules": ("Attach budget rules to a campaign", UPSERT),
    "amazon_ads_sp_detach_budget_rule": ("Detach a budget rule from a campaign", DESTRUCTIVE),
    # ads_api_v1
    "amazon_ads_v1_query": ("Query entities (Ads API v1)", READ),
    "amazon_ads_v1_create": ("Create entities (Ads API v1)", WRITE),
    "amazon_ads_v1_update": ("Update entities (Ads API v1)", UPSERT),
    "amazon_ads_v1_delete": ("Delete entities (Ads API v1)", DESTRUCTIVE),
    # request
    "amazon_ads_read_request": ("Read from any Amazon Ads API endpoint", READ),
    "amazon_ads_request": ("Call any Amazon Ads API endpoint", DESTRUCTIVE_ONCE),
}

TOOL_SPECS: dict[str, ToolSpec] = {
    name: ToolSpec(title, annotations) for name, (title, annotations) in _CATALOG.items()
}
