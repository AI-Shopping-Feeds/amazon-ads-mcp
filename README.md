# Amazon Ads MCP Server (read + write)

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE) [![Python 3.11+](https://img.shields.io/badge/Python-3.11%2B-blue.svg)](https://www.python.org/downloads/)

An [MCP](https://modelcontextprotocol.io) server for the
[Amazon Ads API](https://advertising.amazon.com/API/docs/en-us/reference/api-overview).
Use it from Claude, ChatGPT, Cursor, Codex or any MCP client to report on and
manage Sponsored Products, Sponsored Brands and Sponsored Display campaigns,
keywords, targets, bids and budgets, run performance reports, and manage
portfolios and budget rules.

It's maintained by [AI Shopping Feeds](https://github.com/AI-Shopping-Feeds) and offers:

- **coverage:** Sponsored Products v3, Sponsored Brands, Sponsored Display, reporting v3, portfolios, budget rules, recommendations and the unified Ads API v1
- **bulk changes:** adjust bids by a percentage or pause and enable many entities in one call
- **safety:** dry-run, confirm words for archives, big batches and bid or budget rises, read-only mode and an audit log of every write
- **an escape hatch:** any other endpoint on your regional Amazon Ads API host through `amazon_ads_read_request` and `amazon_ads_request`

Amazon also runs an official [Amazon Ads MCP Server](https://advertising.amazon.com/library/news/amazon-ads-mcp-server-open-beta),
hosted by Amazon for Ads partners (open beta since 2 February 2026). This one runs on your
own machine and adds dry-run, an audit log, read-only mode and spend guards; see the
[comparison](docs/terms-and-data.md#how-this-differs-from-amazons-own-mcp-server).

Not affiliated with or endorsed by Amazon.

Part of the AI Shopping Feeds MCP family: [Google Ads](https://github.com/AI-Shopping-Feeds/google-ads-mcp) · [Google Merchant Centre](https://github.com/AI-Shopping-Feeds/google-merchant-centre-mcp) · [Google Analytics](https://github.com/AI-Shopping-Feeds/google-analytics-mcp) · [YouTube Studio](https://github.com/AI-Shopping-Feeds/youtube-studio-mcp) · **Amazon Ads** · [Apple Ads](https://github.com/AI-Shopping-Feeds/apple-ads-mcp) · [Microsoft Ads](https://github.com/AI-Shopping-Feeds/microsoft-ads-mcp) · [TikTok Ads](https://github.com/AI-Shopping-Feeds/tiktok-ads-mcp) · [Pinterest Ads](https://github.com/AI-Shopping-Feeds/pinterest-ads-mcp) · [Snapchat Ads](https://github.com/AI-Shopping-Feeds/snapchat-ads-mcp) · [OpenAI Ads](https://github.com/AI-Shopping-Feeds/openai-ads-mcp) · [AppLovin](https://github.com/AI-Shopping-Feeds/applovin-mcp).

## Let your agent set it up

Paste this into Claude Code, Codex, Cursor or any agent that can read web pages and edit files:

```text
Set up the Amazon Ads MCP server for me by following https://raw.githubusercontent.com/AI-Shopping-Feeds/amazon-ads-mcp/main/skills/amazon-ads-mcp/SKILL.md
```

The agent checks whether it's already connected, installs the runner if you
agree, walks you through the Login with Amazon security profile, API access and
sign-in, adds the server to your client's config without touching your other
servers, and checks it works by calling `amazon_ads_health_check`.

The same file is an [Agent Skill](https://agentskills.io), so your agent can keep it as a guide to using the tools well. For Claude Code, copy the folder into your skills:

```bash
git clone --depth 1 https://github.com/AI-Shopping-Feeds/amazon-ads-mcp.git /tmp/amazon-ads-mcp
cp -r /tmp/amazon-ads-mcp/skills/amazon-ads-mcp ~/.claude/skills/
```

Other agents that support skills load the same `skills/amazon-ads-mcp` folder from their own skills directory.

## What it can do

100 tools, all prefixed `amazon_ads_`. The full list is in [docs/tools.md](docs/tools.md).

### Read

| Area | Tools |
|---|---|
| Profiles | `list_profiles`, `get_profile`, `list_manager_accounts` |
| Sponsored Products | `sp_list_campaigns`, `sp_list_ad_groups`, `sp_list_product_ads`, `sp_list_keywords`, `sp_list_targets`, negative keyword and target lists |
| Recommendations | `sp_budget_recommendations`, `sp_bid_recommendations`, `sp_keyword_recommendations` |
| Sponsored Brands | `sb_list_campaigns`, `sb_list_ad_groups`, `sb_list_ads`, `sb_list_keywords` |
| Sponsored Display | `sd_list_campaigns`, `sd_list_ad_groups`, `sd_list_product_ads`, `sd_list_targets`, `sd_list_negative_targets` |
| Reports | `run_report` (request, wait and return rows), `create_report`, `get_report`, `download_report` |
| Portfolios and budget rules | `list_portfolios`, `sp_list_budget_rules`, `sp_get_budget_rule`, `sp_list_campaign_budget_rules` |
| Ads API v1 and anything else | `v1_query`, `read_request` |

### Write

| Area | Tools |
|---|---|
| Sponsored Products | create, update and archive campaigns, ad groups, product ads, keywords and targets; create and archive ad-group and campaign negatives |
| Bulk | `sp_adjust_bids` (by % or to a value), `sp_set_states` (pause or enable many) |
| Sponsored Brands | create, update and archive campaigns, ad groups and keywords; `sb_create_ads` per format, `sb_update_ads`, `sb_archive_ads` |
| Sponsored Display | create, update and archive campaigns, ad groups, product ads and targets; create and archive negative targets |
| Portfolios | `create_portfolios`, `update_portfolios` |
| Budget rules | `sp_create_budget_rules`, `sp_update_budget_rules`, `sp_attach_budget_rules`, `sp_detach_budget_rule` |
| Ads API v1 | `v1_create`, `v1_update`, `v1_delete` |
| Any endpoint | `request` |

### Safety

- Dry-run (`AMAZON_ADS_DRY_RUN=true` or `amazon_ads_set_dry_run`) records writes in the audit log and returns what would be sent, without sending it. Reads and reports still work.
- Archives need `confirm="ARCHIVE"` and Ads API v1 deletes need `confirm="DELETE"`. Without the word, the tool sends nothing and returns the reasons.
- Spend guards: batches over `AMAZON_ADS_BULK_THRESHOLD` (10), bid or budget rises over `AMAZON_ADS_MAX_INCREASE_PCT` (25%), values over `AMAZON_ADS_MAX_BID` / `AMAZON_ADS_MAX_BUDGET`, budget rules and raw writes need `confirm="APPLY"`, with the before/after values shown first.
- Every write is recorded in an audit log (`~/.amazon-ads-mcp/logs/audit.jsonl`) with a before-snapshot. Entries older than 30 days are pruned, and `amazon-ads-mcp purge` deletes the log and the stored token.
- `AMAZON_ADS_READ_ONLY=true` hides every tool that can change the account; `AMAZON_ADS_TOOL_GROUPS` exposes only the groups you need.
- The HTTP transports have no sign-in, so the server refuses to listen on anything but this machine unless you set `AMAZON_ADS_ALLOW_REMOTE=true`.
- How the server handles Amazon data, and who can use the API: [docs/terms-and-data.md](docs/terms-and-data.md).

## Supported clients

| Client | Works? | How |
|---|---|---|
| Claude Code | ✅ | Local server, `claude mcp add` (below) |
| Claude Desktop | ✅ | Local server, `claude_desktop_config.json` |
| Cursor | ✅ | Local server, `~/.cursor/mcp.json` |
| VS Code (Copilot) | ✅ | Local server, `.vscode/mcp.json` (uses `servers` instead of `mcpServers`) |
| Codex | ✅ | Local server, `~/.codex/config.toml` |
| Gemini CLI | ✅ | Local server, `~/.gemini/settings.json` |
| Windsurf and other local clients | ✅ | Local server, same JSON entry |
| Claude.ai and ChatGPT | ❌ not yet | These need a remote server with sign-in. This server's HTTP transports have no sign-in, so don't expose them publicly. Use a local client. |

## Setup

### 1. Install uv

The server runs with `uvx` from [uv](https://docs.astral.sh/uv/getting-started/installation/)
(`brew install uv` on macOS) and needs Python 3.11 or later. It installs straight
from this repository:

```shell
uvx --from git+https://github.com/AI-Shopping-Feeds/amazon-ads-mcp.git amazon-ads-mcp version
```

Pin a release by adding `@vX.Y.Z` to the URL.

### 2. Get credentials

1. **Login with Amazon:** create a security profile in the Amazon Developer Console,
   note its client ID and client secret, and add `http://localhost:8765/callback` to its
   Allowed Return URLs.
2. **API access:** apply for Amazon Ads API access with the same email (approval can
   take up to one business day), then assign it to the security profile.
3. **Save the credentials** in `~/.amazon-ads-mcp/.env` (owner-only), with your region
   (`NA`, `EU` for the UK and Europe, or `FE`):

   ```text
   AMAZON_ADS_CLIENT_ID=amzn1.application-oa2-client.YOUR_CLIENT_ID
   AMAZON_ADS_CLIENT_SECRET=YOUR_CLIENT_SECRET
   AMAZON_ADS_REGION=EU
   ```

4. **Sign in** with the Amazon user that manages the ads. It saves a refresh token to
   `~/.amazon-ads-mcp/secrets/` (add `--manual` if the browser redirect doesn't work):

   ```shell
   uvx --from git+https://github.com/AI-Shopping-Feeds/amazon-ads-mcp.git amazon-ads-mcp auth
   ```

Step by step, with regions and token expiry: [docs/setup-amazon-ads-api.md](docs/setup-amazon-ads-api.md).

### 3. Add it to your client

Keep your other servers in each file. Credentials and the token are read from
`~/.amazon-ads-mcp`, so the config holds no secrets. The examples start in dry-run.

**Claude Code**

```bash
claude mcp add --scope user amazon-ads \
  --env AMAZON_ADS_DRY_RUN=true \
  -- uvx --from git+https://github.com/AI-Shopping-Feeds/amazon-ads-mcp.git amazon-ads-mcp
```

**Claude Desktop, Cursor, Gemini CLI, Windsurf** (and VS Code under `servers`)

```json
{
  "mcpServers": {
    "amazon-ads": {
      "command": "uvx",
      "args": ["--from", "git+https://github.com/AI-Shopping-Feeds/amazon-ads-mcp.git", "amazon-ads-mcp"],
      "env": {
        "AMAZON_ADS_DRY_RUN": "true"
      }
    }
  }
}
```

Desktop apps often can't find `uvx` on the PATH; if the server doesn't start, use
the full path from `which uvx` as the `command`.

**Codex** (`~/.codex/config.toml`)

```toml
[mcp_servers.amazon-ads]
command = "uvx"
args = ["--from", "git+https://github.com/AI-Shopping-Feeds/amazon-ads-mcp.git", "amazon-ads-mcp"]
env = { AMAZON_ADS_DRY_RUN = "true" }
```

To keep the files elsewhere, add `"--env", "/abs/path/amazon-ads.env"` after
`amazon-ads-mcp` in the arguments, or set `AMAZON_ADS_TOKEN_FILE=/abs/path/amazon-ads-token.json`
and `AMAZON_ADS_AUDIT_LOG=/abs/path/audit.jsonl`.

### 4. Check it works

Restart or reload the client, then ask it "which Amazon Ads profiles can you see?". It
should call `amazon_ads_health_check` and list your profiles. Add the one you use most to
`~/.amazon-ads-mcp/.env` as `AMAZON_ADS_PROFILE_ID`; tools also take a `profile_id`
argument. When you're happy with the dry-run previews, remove `AMAZON_ADS_DRY_RUN`.

## Configuration

Settings come from the environment (including your client config), then the `--env`
file or `./.env`, then `~/.amazon-ads-mcp/.env`.

| Variable | Required | What it does |
|---|---|---|
| `AMAZON_ADS_CLIENT_ID`, `AMAZON_ADS_CLIENT_SECRET` | yes | Login with Amazon security profile credentials |
| `AMAZON_ADS_REGION` | no | `NA`, `EU` (default) or `FE` |
| `AMAZON_ADS_TOKEN_FILE` | no | Refresh-token file written by `auth` (default `~/.amazon-ads-mcp/secrets/amazon-ads-token.json`) |
| `AMAZON_ADS_REFRESH_TOKEN` | no | The refresh token itself, instead of the file |
| `AMAZON_ADS_PROFILE_ID` | no | Default advertiser profile |
| `AMAZON_ADS_DRY_RUN` | no | `true` previews writes without sending them |
| `AMAZON_ADS_READ_ONLY` | no | `true` registers only read-only tools |
| `AMAZON_ADS_TOOL_GROUPS` | no | Comma-separated groups: `profiles`, `sp_campaigns`, `sp_ads`, `sp_targeting`, `sp_recommendations`, `bulk`, `sponsored_brands`, `sponsored_display`, `reporting`, `portfolios`, `budget_rules`, `ads_api_v1`, `request`. Unknown names stop the server at startup |
| `AMAZON_ADS_BULK_THRESHOLD` | no | Items per write before `confirm="APPLY"` is needed (default 10) |
| `AMAZON_ADS_MAX_INCREASE_PCT` | no | Bid or budget rise that needs `confirm="APPLY"` (default 25) |
| `AMAZON_ADS_MAX_BUDGET`, `AMAZON_ADS_MAX_BID` | no | Optional absolute caps |
| `AMAZON_ADS_AUDIT_LOG` | no | Audit log path (default `~/.amazon-ads-mcp/logs/audit.jsonl`) |
| `AMAZON_ADS_AUDIT_RETENTION_DAYS` | no | Days to keep audit entries, pruned at startup (default 30; 0 keeps them) |
| `AMAZON_ADS_PAGE_SIZE`, `AMAZON_ADS_TIMEOUT`, `AMAZON_ADS_LOG_LEVEL` | no | List page size (100), request timeout in seconds (30) and log level |
| `AMAZON_ADS_TRANSPORT`, `AMAZON_ADS_HOST`, `AMAZON_ADS_PORT` | no | `stdio` (default) or `streamable-http` at `http://HOST:PORT/mcp` (default `127.0.0.1:8000`) |
| `AMAZON_ADS_ALLOW_REMOTE` | no | `true` lets an HTTP transport bind to a non-loopback host (same as `--allow-remote`). It has no sign-in: only behind an authenticating proxy |

CLI: `amazon-ads-mcp run` (default), `auth`, `purge`, `describe`, `version`.

## Example prompts

```text
Which Sponsored Products campaigns spent the most last week, and what was their ACOS?
```

```text
Lower bids by 10% on keywords in the "Brand - Exact" ad group with ACOS over 40%. Dry-run first and show me the table.
```

```text
Add "free" and "cheap" as campaign negative phrase keywords to all my Sponsored Products campaigns.
```

```text
Show me suggested budgets for campaigns that ran out of budget this week.
```

## More docs

- [All tools and confirm words](docs/tools.md)
- [Amazon Ads API setup, regions and token expiry](docs/setup-amazon-ads-api.md)
- [MCP client configuration and every environment variable](docs/mcp-client-config.md)
- [Terms and data handling](docs/terms-and-data.md)
- [Agent skill](skills/amazon-ads-mcp/SKILL.md): setup and usage guide for agents
- [Changelog](CHANGELOG.md) and [security policy](SECURITY.md)

## Contributing and licence

Issues and pull requests are welcome on [this repository](https://github.com/AI-Shopping-Feeds/amazon-ads-mcp). See
[CONTRIBUTING.md](CONTRIBUTING.md).

Licensed under the [MIT License](LICENSE).

---

Try out [AI Shopping Feeds](https://aishoppingfeeds.com/), our shopping feed management tool (including Google Shopping feeds).
