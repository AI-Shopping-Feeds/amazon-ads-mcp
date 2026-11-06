# Changelog — Amazon Ads MCP (`amazon-ads-mcp`)

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [0.1.0] - 2026-11-06

### Added
- First version: 100 tools across 13 groups plus 5 meta tools, built on the same
  architecture as the Google Merchant Centre MCP server (tool catalog with
  titles and annotations, tool groups, read-only mode, dry-run, JSONL audit log,
  stdio and streamable HTTP transports, progress notifications).
- Login with Amazon auth: `amazon-ads-mcp auth` runs the one-time consent with a
  localhost redirect (or `--manual`) and saves the refresh token to an
  owner-only, gitignored file. Access tokens refresh automatically and are
  cached until shortly before they expire; a 401 triggers one refresh.
- Regional hosts for NA, EU (default) and FE; every request sends the client ID,
  and profile-scoped requests send the profile from `AMAZON_ADS_PROFILE_ID` or
  a per-call `profile_id`.
- Sponsored Products v3: campaigns, ad groups, product ads, keywords, product
  targets, ad-group and campaign negatives; budget, bid and keyword
  recommendations; bulk bid adjustment and pause/enable.
- Sponsored Brands v4 campaigns, ad groups and ads, and v3 keywords.
- Sponsored Display campaigns, ad groups, product ads, targets and negative targets.
- Reporting v3: create, status, download (gzipped JSON parsed in memory) and
  `amazon_ads_run_report`, which waits with progress. Duplicate requests reuse
  the report already in progress.
- Portfolios, Sponsored Products budget rules, Ads API v1 query/create/update/
  delete, and raw read/write request tools for anything else.
- Safety: confirm words for archives (`ARCHIVE`), v1 deletes (`DELETE`), and
  batches, bid/budget rises, caps, budget rules and raw writes (`APPLY`).
  Updates read current values first for a before-snapshot and the rise check.
- Data handling: audit entries are redacted and pruned after
  `AMAZON_ADS_AUDIT_RETENTION_DAYS` (30); report rows and read results are never
  stored; `amazon-ads-mcp purge` deletes the audit log and token file; only
  Amazon hosts are contacted; 429 responses honour `Retry-After`.
