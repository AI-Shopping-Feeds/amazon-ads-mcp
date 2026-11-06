# All tools

**100 tools: 95 across 13 groups + 5 meta tools.**

Groups are the modules in `src/amazon_ads_mcp/tools`; `AMAZON_ADS_TOOL_GROUPS`
selects some of them. `AMAZON_ADS_READ_ONLY=true` keeps only the tools marked
*read* below. The meta tools are always registered.

"Kind" comes from each tool's MCP annotations: *read* changes nothing in the ads
account, *write* creates or updates, *destructive* archives, deletes or detaches
(or, for `amazon_ads_request`, may do anything).

## Confirm words

| Change | Needs |
|---|---|
| Archive (Sponsored Products, Sponsored Brands, Sponsored Display) | `confirm="ARCHIVE"` |
| Delete through Ads API v1 | `confirm="DELETE"` |
| More than `AMAZON_ADS_BULK_THRESHOLD` items (default 10) | `confirm="APPLY"` |
| A bid or budget rising more than `AMAZON_ADS_MAX_INCREASE_PCT` (default 25%), or whose current value couldn't be read | `confirm="APPLY"` |
| A bid or budget above `AMAZON_ADS_MAX_BID` / `AMAZON_ADS_MAX_BUDGET` (if set) | `confirm="APPLY"` |
| Creating, updating or attaching budget rules | `confirm="APPLY"` |
| Ads API v1 creates/updates that set bids or budgets | `confirm="APPLY"` |
| Any write through `amazon_ads_request` | `confirm="APPLY"` |

Without the right word a guarded write returns `refused: true`, the reasons and
the bid/budget changes it would make, and sends nothing. In dry-run mode
nothing is sent anyway, so guards don't block; the preview says which confirm a
real run would need.

## meta (5)

| Tool | What it does | Kind |
|---|---|---|
| `amazon_ads_describe_server` | Describe the server configuration | read |
| `amazon_ads_health_check` | Check the token and list profiles | read |
| `amazon_ads_audit_lookup` | Look up an audit log entry | read |
| `amazon_ads_audit_tail` | Show recent audit log entries | read |
| `amazon_ads_set_dry_run` | Turn dry-run mode on or off | write |

## profiles (3)

Advertiser profiles (one per marketplace) and manager accounts.

| Tool | What it does | Kind |
|---|---|---|
| `amazon_ads_list_profiles` | List advertising profiles | read |
| `amazon_ads_get_profile` | Get a profile | read |
| `amazon_ads_list_manager_accounts` | List manager accounts | read |

## sp_campaigns (8)

Sponsored Products campaigns and ad groups.

| Tool | What it does | Kind |
|---|---|---|
| `amazon_ads_sp_list_campaigns` | List Sponsored Products campaigns | read |
| `amazon_ads_sp_create_campaigns` | Create Sponsored Products campaigns | write |
| `amazon_ads_sp_update_campaigns` | Update Sponsored Products campaigns | write |
| `amazon_ads_sp_archive_campaigns` | Archive Sponsored Products campaigns | **destructive** |
| `amazon_ads_sp_list_ad_groups` | List Sponsored Products ad groups | read |
| `amazon_ads_sp_create_ad_groups` | Create Sponsored Products ad groups | write |
| `amazon_ads_sp_update_ad_groups` | Update Sponsored Products ad groups | write |
| `amazon_ads_sp_archive_ad_groups` | Archive Sponsored Products ad groups | **destructive** |

## sp_ads (4)

Sponsored Products product ads.

| Tool | What it does | Kind |
|---|---|---|
| `amazon_ads_sp_list_product_ads` | List Sponsored Products product ads | read |
| `amazon_ads_sp_create_product_ads` | Create Sponsored Products product ads | write |
| `amazon_ads_sp_update_product_ads` | Update Sponsored Products product ads | write |
| `amazon_ads_sp_archive_product_ads` | Archive Sponsored Products product ads | **destructive** |

## sp_targeting (20)

Sponsored Products keywords, product targets and negatives (ad group and campaign level).

| Tool | What it does | Kind |
|---|---|---|
| `amazon_ads_sp_list_keywords` | List Sponsored Products keywords | read |
| `amazon_ads_sp_create_keywords` | Create Sponsored Products keywords | write |
| `amazon_ads_sp_update_keywords` | Update Sponsored Products keywords | write |
| `amazon_ads_sp_archive_keywords` | Archive Sponsored Products keywords | **destructive** |
| `amazon_ads_sp_list_negative_keywords` | List Sponsored Products negative keywords | read |
| `amazon_ads_sp_create_negative_keywords` | Create Sponsored Products negative keywords | write |
| `amazon_ads_sp_archive_negative_keywords` | Archive Sponsored Products negative keywords | **destructive** |
| `amazon_ads_sp_list_campaign_negative_keywords` | List Sponsored Products campaign negative keywords | read |
| `amazon_ads_sp_create_campaign_negative_keywords` | Create Sponsored Products campaign negative keywords | write |
| `amazon_ads_sp_archive_campaign_negative_keywords` | Archive Sponsored Products campaign negative keywords | **destructive** |
| `amazon_ads_sp_list_targets` | List Sponsored Products product targets | read |
| `amazon_ads_sp_create_targets` | Create Sponsored Products product targets | write |
| `amazon_ads_sp_update_targets` | Update Sponsored Products product targets | write |
| `amazon_ads_sp_archive_targets` | Archive Sponsored Products product targets | **destructive** |
| `amazon_ads_sp_list_negative_targets` | List Sponsored Products negative product targets | read |
| `amazon_ads_sp_create_negative_targets` | Create Sponsored Products negative product targets | write |
| `amazon_ads_sp_archive_negative_targets` | Archive Sponsored Products negative product targets | **destructive** |
| `amazon_ads_sp_list_campaign_negative_targets` | List Sponsored Products campaign negative product targets | read |
| `amazon_ads_sp_create_campaign_negative_targets` | Create Sponsored Products campaign negative product targets | write |
| `amazon_ads_sp_archive_campaign_negative_targets` | Archive Sponsored Products campaign negative product targets | **destructive** |

## sp_recommendations (3)

Suggested budgets, bids and keywords. Read-only.

| Tool | What it does | Kind |
|---|---|---|
| `amazon_ads_sp_budget_recommendations` | Get Sponsored Products budget recommendations | read |
| `amazon_ads_sp_bid_recommendations` | Get Sponsored Products bid recommendations | read |
| `amazon_ads_sp_keyword_recommendations` | Get Sponsored Products keyword recommendations | read |

## bulk (2)

Bid changes by percentage and pause/enable across many Sponsored Products entities, with progress.

| Tool | What it does | Kind |
|---|---|---|
| `amazon_ads_sp_adjust_bids` | Adjust many Sponsored Products bids | write |
| `amazon_ads_sp_set_states` | Pause or enable many Sponsored Products entities | write |

## sponsored_brands (16)

Sponsored Brands campaigns, ad groups and ads (v4) and keywords (v3).

| Tool | What it does | Kind |
|---|---|---|
| `amazon_ads_sb_list_campaigns` | List Sponsored Brands campaigns | read |
| `amazon_ads_sb_create_campaigns` | Create Sponsored Brands campaigns | write |
| `amazon_ads_sb_update_campaigns` | Update Sponsored Brands campaigns | write |
| `amazon_ads_sb_archive_campaigns` | Archive Sponsored Brands campaigns | **destructive** |
| `amazon_ads_sb_list_ad_groups` | List Sponsored Brands ad groups | read |
| `amazon_ads_sb_create_ad_groups` | Create Sponsored Brands ad groups | write |
| `amazon_ads_sb_update_ad_groups` | Update Sponsored Brands ad groups | write |
| `amazon_ads_sb_archive_ad_groups` | Archive Sponsored Brands ad groups | **destructive** |
| `amazon_ads_sb_list_ads` | List Sponsored Brands ads | read |
| `amazon_ads_sb_update_ads` | Update Sponsored Brands ads | write |
| `amazon_ads_sb_archive_ads` | Archive Sponsored Brands ads | **destructive** |
| `amazon_ads_sb_list_keywords` | List Sponsored Brands keywords | read |
| `amazon_ads_sb_create_keywords` | Create Sponsored Brands keywords | write |
| `amazon_ads_sb_update_keywords` | Update Sponsored Brands keywords | write |
| `amazon_ads_sb_archive_keywords` | Archive Sponsored Brands keywords | **destructive** |
| `amazon_ads_sb_create_ads` | Create Sponsored Brands ads | write |

## sponsored_display (19)

Sponsored Display campaigns, ad groups, product ads, targets and negative targets.

| Tool | What it does | Kind |
|---|---|---|
| `amazon_ads_sd_list_campaigns` | List Sponsored Display campaigns | read |
| `amazon_ads_sd_create_campaigns` | Create Sponsored Display campaigns | write |
| `amazon_ads_sd_update_campaigns` | Update Sponsored Display campaigns | write |
| `amazon_ads_sd_archive_campaigns` | Archive Sponsored Display campaigns | **destructive** |
| `amazon_ads_sd_list_ad_groups` | List Sponsored Display ad groups | read |
| `amazon_ads_sd_create_ad_groups` | Create Sponsored Display ad groups | write |
| `amazon_ads_sd_update_ad_groups` | Update Sponsored Display ad groups | write |
| `amazon_ads_sd_archive_ad_groups` | Archive Sponsored Display ad groups | **destructive** |
| `amazon_ads_sd_list_product_ads` | List Sponsored Display product ads | read |
| `amazon_ads_sd_create_product_ads` | Create Sponsored Display product ads | write |
| `amazon_ads_sd_update_product_ads` | Update Sponsored Display product ads | write |
| `amazon_ads_sd_archive_product_ads` | Archive Sponsored Display product ads | **destructive** |
| `amazon_ads_sd_list_targets` | List Sponsored Display targets | read |
| `amazon_ads_sd_create_targets` | Create Sponsored Display targets | write |
| `amazon_ads_sd_update_targets` | Update Sponsored Display targets | write |
| `amazon_ads_sd_archive_targets` | Archive Sponsored Display targets | **destructive** |
| `amazon_ads_sd_list_negative_targets` | List Sponsored Display negative targets | read |
| `amazon_ads_sd_create_negative_targets` | Create Sponsored Display negative targets | write |
| `amazon_ads_sd_archive_negative_targets` | Archive Sponsored Display negative targets | **destructive** |

## reporting (4)

Asynchronous performance reports (reporting v3). Rows stay in memory.

| Tool | What it does | Kind |
|---|---|---|
| `amazon_ads_create_report` | Request a performance report | read |
| `amazon_ads_get_report` | Check a report's status | read |
| `amazon_ads_download_report` | Download a finished report | read |
| `amazon_ads_run_report` | Run a report and return its rows | read |

## portfolios (3)

Portfolios and their budget caps.

| Tool | What it does | Kind |
|---|---|---|
| `amazon_ads_list_portfolios` | List portfolios | read |
| `amazon_ads_create_portfolios` | Create portfolios | write |
| `amazon_ads_update_portfolios` | Update portfolios | write |

## budget_rules (7)

Sponsored Products budget rules.

| Tool | What it does | Kind |
|---|---|---|
| `amazon_ads_sp_list_budget_rules` | List Sponsored Products budget rules | read |
| `amazon_ads_sp_get_budget_rule` | Get a Sponsored Products budget rule | read |
| `amazon_ads_sp_list_campaign_budget_rules` | List a campaign's budget rules | read |
| `amazon_ads_sp_create_budget_rules` | Create Sponsored Products budget rules | write |
| `amazon_ads_sp_update_budget_rules` | Update Sponsored Products budget rules | write |
| `amazon_ads_sp_attach_budget_rules` | Attach budget rules to a campaign | write |
| `amazon_ads_sp_detach_budget_rule` | Detach a budget rule from a campaign | **destructive** |

## ads_api_v1 (4)

The unified Amazon Ads API v1 (campaigns, ad groups, ads, targets, ad associations across ad products).

| Tool | What it does | Kind |
|---|---|---|
| `amazon_ads_v1_query` | Query entities (Ads API v1) | read |
| `amazon_ads_v1_create` | Create entities (Ads API v1) | write |
| `amazon_ads_v1_update` | Update entities (Ads API v1) | write |
| `amazon_ads_v1_delete` | Delete entities (Ads API v1) | **destructive** |

## request (2)

Escape hatch for any endpoint the other tools don't cover.

| Tool | What it does | Kind |
|---|---|---|
| `amazon_ads_read_request` | Read from any Amazon Ads API endpoint | read |
| `amazon_ads_request` | Call any Amazon Ads API endpoint | **destructive** |

## CLI

`amazon-ads-mcp run` (default), `auth`, `purge`, `describe`, `version`.
