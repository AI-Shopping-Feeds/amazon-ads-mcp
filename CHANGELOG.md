# Changelog — Amazon Ads MCP (`amazon-ads-mcp`)

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Added
- MIT licence, security policy (including how to report suspected misuse of
  Amazon data), contributing guide, issue and pull request templates, and
  Dependabot updates for pip and GitHub Actions.
- `docs/setup-amazon-ads-api.md`, `docs/mcp-client-config.md` and
  `docs/terms-and-data.md`. The README now follows the AI Shopping Feeds MCP
  family format and installs with `uvx` from git.
- `AMAZON_ADS_ALLOW_REMOTE` / `--allow-remote`.
- `~/.amazon-ads-mcp/.env` is read after the `--env` file or `./.env`.

### Changed
- The refresh token and audit log default to
  `~/.amazon-ads-mcp/secrets/amazon-ads-token.json` and
  `~/.amazon-ads-mcp/logs/audit.jsonl` instead of folders next to the installed
  package (which, for `uvx`, is a cache). Folders the server creates are 0700
  and the audit log is 0600. Set `AMAZON_ADS_TOKEN_FILE` / `AMAZON_ADS_AUDIT_LOG`
  to keep using old locations.
- `./.env` is looked up in the folder the server starts in, not the package folder.
- Python 3.11 or later (3.10 reached end of life); tested on 3.11 to 3.15.
  Minimum dependency versions raised to current releases.

### Security
- HTTP transports refuse to bind to a non-loopback host unless
  `AMAZON_ADS_ALLOW_REMOTE=true` or `--allow-remote` is set.
- `auth --manual` refuses a pasted redirect URL whose `state` is missing or
  different (a bare code is still accepted).
- Request paths are checked for dot segments (also encoded), backslashes,
  fragments and control characters, and IDs placed in paths must be plain IDs.
- `amazon_ads_read_request` treats POSTs to paths with action segments
  (`apply`, `update`, `delete`, ...) as writes, so read-only mode can't change
  the account.
- Report files over 200 MB (compressed or decompressed) are refused instead of
  being read into memory.
- Per-item failure reasons in bulk and archive results are redacted.

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
