# Amazon Ads MCP Server (read + write)

A self-hosted [MCP](https://modelcontextprotocol.io) server for the
[Amazon Ads API](https://advertising.amazon.com/API/docs/en-us/reference/api-overview).
Use it from Claude Code, Claude Desktop or any MCP client to look at and manage
Sponsored Products, Sponsored Brands and Sponsored Display campaigns, run
performance reports, and manage portfolios and budget rules, with a dry-run
mode, confirmation guards and an audit log for every change.

This is an independent project by [AI Shopping Feeds](https://github.com/AI-Shopping-Feeds).
It is not made, endorsed or supported by Amazon.

> **Private repository, not yet licensed.** No licence has been chosen, so no
> one outside AI Shopping Feeds may use, copy or distribute this code yet. It
> isn't published to PyPI or any MCP registry.

Part of the AI Shopping Feeds MCP family: [Google Ads](https://github.com/AI-Shopping-Feeds/google-ads-mcp) · [Google Merchant Centre](https://github.com/AI-Shopping-Feeds/google-merchant-centre-mcp) · [Google Analytics](https://github.com/AI-Shopping-Feeds/google-analytics-mcp) · [YouTube Studio](https://github.com/AI-Shopping-Feeds/youtube-studio-mcp) · **Amazon Ads**.

## How this differs from Amazon's own MCP server

Amazon runs an official
[Amazon Ads MCP Server](https://advertising.amazon.com/library/news/amazon-ads-mcp-server-open-beta),
in open beta since 2 February 2026 for Amazon Ads partners with active API
credentials. It is hosted by Amazon and adds multi-step workflow tools (for
example, creating a complete Sponsored Products campaign in one step). If you
qualify and want Amazon-maintained workflows, look at it first.

This server is different in a few ways:

| | This server | Amazon's MCP server |
|---|---|---|
| Where it runs | On your machine (or your own private server) | Hosted by Amazon |
| Who can use it | Anyone with their own approved Amazon Ads API client | Amazon Ads partners with active API credentials (open beta) |
| Audit log | Every write, with a before-snapshot, in a local JSONL file | Not offered |
| Dry-run | Rehearse any write and see exactly what would be sent | Not offered |
| Read-only mode | `AMAZON_ADS_READ_ONLY=true` hides every write tool | Not offered |
| Tool groups | Load only the areas you need (`AMAZON_ADS_TOOL_GROUPS`) | Not offered |
| Spend guards | Confirm words for archives, big batches and bid/budget rises | Not offered |

## What it can do

100 tools, all prefixed `amazon_ads_`. The full list is in [docs/tools.md](docs/tools.md).

| Area | Covered | Tools |
|---|---|---|
| Profiles and manager accounts | list, get | `list_profiles`, `get_profile`, `list_manager_accounts` |
| Sponsored Products (v3) | campaigns, ad groups, product ads, keywords, product targets, ad-group and campaign negatives: list, create, update, archive | `sp_list_campaigns`, `sp_update_keywords`, `sp_archive_targets`, ... |
| Sponsored Products recommendations | budgets, bids, keywords | `sp_budget_recommendations`, `sp_bid_recommendations`, `sp_keyword_recommendations` |
| Bulk changes | bids by % or to a value; pause/enable many | `sp_adjust_bids`, `sp_set_states` |
| Sponsored Brands | campaigns, ad groups, ads (v4); keywords (v3) | `sb_list_campaigns`, `sb_create_ads`, `sb_update_keywords`, ... |
| Sponsored Display | campaigns, ad groups, product ads, targets, negative targets | `sd_list_campaigns`, `sd_update_targets`, ... |
| Reporting (v3) | request, check, download; or one call that waits with progress | `create_report`, `get_report`, `download_report`, `run_report` |
| Portfolios | list, create, update | `list_portfolios`, `create_portfolios`, `update_portfolios` |
| Budget rules (Sponsored Products) | list, get, create, update, attach, detach | `sp_create_budget_rules`, `sp_attach_budget_rules`, ... |
| Amazon Ads API v1 | campaigns, ad groups, ads, targets, ad associations across ad products | `v1_query`, `v1_create`, `v1_update`, `v1_delete` |
| Anything else | any endpoint on your regional host | `read_request` (reads only), `request` (writes, needs confirm) |
| Server | settings, token check, audit, dry-run | `describe_server`, `health_check`, `audit_tail`, `audit_lookup`, `set_dry_run` |

**Amazon Ads API v1.** Amazon now recommends its unified v1 API for new
integrations, and its campaign-management endpoints (campaigns, ad groups, ads,
targets and ad associations) are generally available. This server keeps the
per-product tools as its main surface, because their fields are well
established and the safety guards can compare bids and budgets against current
values, and adds four generic `v1_*` tools for the unified model. Reporting,
recommendations and rules are still being moved into v1, so this server uses
the established endpoints for those.

**Left to the escape hatch** (`amazon_ads_read_request` / `amazon_ads_request`):
Amazon DSP, Sponsored Television, Amazon Marketing Cloud, Stores and creative
asset uploads, Sponsored Brands and Display creatives and moderation, brand
safety lists, optimization rules, forecasts, insights, product and category
targeting helpers, test accounts, and Ads API v1 reporting.

## Safety

Writes change live ads and spend real money, so:

- **Dry-run** (`AMAZON_ADS_DRY_RUN=true`, or `amazon_ads_set_dry_run`) records
  writes in the audit log and returns what would be sent, without sending it.
  Reads, recommendations and reports still work. Start here.
- **Confirm words.** Archives need `confirm="ARCHIVE"`; Ads API v1 deletes need
  `confirm="DELETE"`. Batches larger than `AMAZON_ADS_BULK_THRESHOLD` (10), bid
  or budget rises above `AMAZON_ADS_MAX_INCREASE_PCT` (25%), values above
  `AMAZON_ADS_MAX_BID` / `AMAZON_ADS_MAX_BUDGET`, budget rules and raw writes
  need `confirm="APPLY"`. Without it the tool sends nothing and replies with
  the reasons and the before/after values, so the agent can show you first.
- **Audit log.** Every write is appended to a JSONL file with the request, the
  response and, where cheap, a before-snapshot of the entities it changed.
  `amazon_ads_audit_tail` and `amazon_ads_audit_lookup` read it.
- **Read-only mode** (`AMAZON_ADS_READ_ONLY=true`) registers only tools that
  can't change anything.
- **Tool groups** (`AMAZON_ADS_TOOL_GROUPS`) load only the areas you need.
- Every tool carries MCP annotations (read-only, destructive, idempotent), so
  clients can ask before running writes.

## Setup

You need: an Amazon account that can manage the ads, about 30 minutes, and
then up to one business day while Amazon reviews your API application.

### 1. Create a Login with Amazon security profile

1. Sign in at [developer.amazon.com](https://developer.amazon.com) (create a
   developer account if you don't have one). For a business, use an email
   address several people in the company can reach: it becomes tied to your
   API access and can't be changed later.
2. Open **Developer Console → Login with Amazon → Create a New Security Profile**.
3. Enter a name, a description and your company's privacy policy URL, then **Save**.
4. In the list of security profiles, click **Show Client ID and Client Secret**
   and keep both somewhere safe, like a password manager. Never paste them into
   chat or commit them.
5. On the same profile, open the gear icon → **Web Settings → Edit**, and add
   this to **Allowed Return URLs**, then **Save**:

   ```text
   http://localhost:8765/callback
   ```

   (If Amazon won't accept a `localhost` address, add `https://amazon.com`
   instead and use `--manual` in step 5.)

### 2. Apply for Amazon Ads API access

1. Go to the Amazon Ads API page and choose **Request API access → Direct
   Advertiser** (agencies and tool makers apply as a Partner through the Amazon
   Ads Partner Network instead).
2. Sign in with **the same email** you used for the developer account.
3. Fill in the form and **Submit for review**. Amazon emails a decision, usually
   within one business day.

### 3. Assign API access to your security profile

When the approval email arrives, **sign out of every other Amazon account in
your browser first** (including personal shopping accounts), then open the link
in the email, choose the security profile from step 1 and **Submit**. The
confirmation page should list the `advertising::campaign_management` scope.

### 4. Install the server

You need [uv](https://docs.astral.sh/uv/getting-started/installation/)
(`brew install uv` on macOS) and git access to this private repository.

```shell
git clone https://github.com/AI-Shopping-Feeds/amazon-ads-mcp.git
cd amazon-ads-mcp
uv venv --python 3.12
uv pip install -e .
cp .env.example .env
```

Open `.env` and fill in `AMAZON_ADS_CLIENT_ID`, `AMAZON_ADS_CLIENT_SECRET` and
`AMAZON_ADS_REGION` (`EU` for the UK and Europe, `NA` for the Americas, `FE`
for Japan, Australia and Singapore). `.env` is gitignored.

### 5. Connect your Amazon account (one time)

```shell
.venv/bin/amazon-ads-mcp auth
```

Your browser opens Amazon's consent page. Sign in with the Amazon user that
manages the ads accounts and click **Allow**. The server saves a refresh token
to `secrets/amazon-ads-token.json` (owner-only permissions, gitignored) and
never prints it. If the local redirect doesn't work, run
`.venv/bin/amazon-ads-mcp auth --manual` and paste the address Amazon sends you
to.

Refresh tokens issued from 30 July 2026 expire 365 days after consent: run
`auth` again when that happens.

Check the settings were picked up (it shows `"refresh_token": "set"` and no
secrets):

```shell
.venv/bin/amazon-ads-mcp describe
```

### 6. Add it to your client

Use the absolute path to your checkout. Secrets stay in `.env`; the client
config only points at it.

**Claude Code**

```bash
claude mcp add --scope user amazon-ads \
  -- /abs/path/amazon-ads-mcp/.venv/bin/amazon-ads-mcp --env /abs/path/amazon-ads-mcp/.env run
```

**Claude Desktop** (`~/Library/Application Support/Claude/claude_desktop_config.json`
on macOS, `%APPDATA%\Claude\claude_desktop_config.json` on Windows). Add the
entry under `mcpServers`, keep your other servers, then quit and reopen Claude:

```json
{
  "mcpServers": {
    "amazon-ads": {
      "command": "/abs/path/amazon-ads-mcp/.venv/bin/amazon-ads-mcp",
      "args": ["--env", "/abs/path/amazon-ads-mcp/.env", "run"]
    }
  }
}
```

### 7. Check it works

Restart or reload the client, then ask: "Which Amazon Ads profiles can you
see?" It should call `amazon_ads_health_check` and list your profiles. Set
`AMAZON_ADS_PROFILE_ID` in `.env` to the one you use most; tools also take a
`profile_id` argument.

## Configuration

| Variable | Required | What it does |
|---|---|---|
| `AMAZON_ADS_CLIENT_ID`, `AMAZON_ADS_CLIENT_SECRET` | yes | Login with Amazon security profile credentials |
| `AMAZON_ADS_REGION` | no | `NA`, `EU` (default) or `FE` |
| `AMAZON_ADS_TOKEN_FILE` | no | Refresh-token file written by `auth` (default `secrets/amazon-ads-token.json` in the checkout) |
| `AMAZON_ADS_REFRESH_TOKEN` | no | The refresh token itself, instead of the file |
| `AMAZON_ADS_PROFILE_ID` | no | Default advertiser profile |
| `AMAZON_ADS_DRY_RUN` | no | `true` previews writes without sending them |
| `AMAZON_ADS_READ_ONLY` | no | `true` registers only read-only tools |
| `AMAZON_ADS_TOOL_GROUPS` | no | Comma-separated groups: `profiles`, `sp_campaigns`, `sp_ads`, `sp_targeting`, `sp_recommendations`, `bulk`, `sponsored_brands`, `sponsored_display`, `reporting`, `portfolios`, `budget_rules`, `ads_api_v1`, `request`. Unknown names stop the server at startup |
| `AMAZON_ADS_BULK_THRESHOLD` | no | Items per write before `confirm="APPLY"` is needed (default 10) |
| `AMAZON_ADS_MAX_INCREASE_PCT` | no | Bid/budget rise that needs `confirm="APPLY"` (default 25) |
| `AMAZON_ADS_MAX_BUDGET`, `AMAZON_ADS_MAX_BID` | no | Optional absolute caps |
| `AMAZON_ADS_AUDIT_LOG` | no | Audit log path (default `logs/audit.jsonl` in the checkout) |
| `AMAZON_ADS_AUDIT_RETENTION_DAYS` | no | Days to keep audit entries, pruned at startup (default 30; 0 keeps them) |
| `AMAZON_ADS_PAGE_SIZE`, `AMAZON_ADS_TIMEOUT` | no | List page size (100) and request timeout in seconds (30) |
| `AMAZON_ADS_TRANSPORT`, `AMAZON_ADS_HOST`, `AMAZON_ADS_PORT` | no | `stdio` (default) or `streamable-http` at `http://HOST:PORT/mcp`. HTTP has no sign-in: keep it on localhost |
| `AMAZON_ADS_LOG_LEVEL` | no | `DEBUG`, `INFO`, `WARNING` or `ERROR` (logs go to stderr) |

CLI: `amazon-ads-mcp run` (default), `auth`, `purge`, `describe`, `version`.

## Terms and data handling

Using the Amazon Ads API means accepting Amazon's API License Agreement and
policies. This server is built to fit them, but you are responsible for how you
use it.

- **Eligibility.** The API is for advertisers, agencies and tool makers, and
  only for companies that don't run a significant ecommerce business, a DSP or
  an ad network. Check Amazon's current terms before you apply.
- **Authorisation.** Only connect advertiser accounts whose owners have
  expressly authorised you to manage them through the API.
- **No Amazon materials here.** This repository contains its own client code and
  tool descriptions. It doesn't include Amazon's API specifications,
  documentation text, SDKs or sample code.
- **Only Amazon endpoints.** The server talks only to your regional Amazon Ads
  API host, the Login with Amazon token endpoint, and Amazon's storage for
  report downloads. No telemetry, no other hosts, and the raw request tools
  can't reach other hosts either.
- **Data retention.** The audit log keeps only write requests, before-snapshots
  and write responses, never read results or report rows, and entries older
  than `AMAZON_ADS_AUDIT_RETENTION_DAYS` (30) are deleted at startup. Reports are
  downloaded and parsed in memory. `amazon-ads-mcp purge` deletes the audit log
  and the stored refresh token. Delete Amazon data you no longer need, and on
  request or when you stop using the API.
- **Credentials.** The refresh-token file is written owner-only (0600) and
  gitignored. Tokens and the client secret are redacted from logs, errors and
  the audit log.
- **Throttling.** Throttled requests (HTTP 429) wait for the `Retry-After`
  period before retrying, with backoff.
- **No mixing with other data.** Don't combine Amazon Ads data with data from
  other ad platforms or third-party sources (for example Google Ads) in the same
  analysis or output unless you have Amazon's written approval. The server tells
  the agent this too.
- **AI providers.** Amazon Ads data returned by these tools is sent to the AI
  model your client uses. Use it only under business or API terms where the
  provider doesn't train on your inputs.
- **Trademarks.** "Amazon" and "Amazon Ads" are used here only to say what the
  server works with. No logos, and no claim of partnership or endorsement.

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

## Development

```shell
uv venv --python 3.12 && uv pip install -e ".[test,dev]"
ruff check src tests && ruff format --check src tests
mypy src/amazon_ads_mcp
pytest
```

Tests run offline with mocked HTTP; no Amazon credentials are needed.

## More docs

- [All tools and confirm words](docs/tools.md)
- [Agent skill](skills/amazon-ads-mcp/SKILL.md): setup and usage guide for agents
- [Changelog](CHANGELOG.md)

## Licence

None yet. This is a private repository and all rights are reserved by AI
Shopping Feeds until a licence is chosen.

---

Try out [AI Shopping Feeds](https://aishoppingfeeds.com/), our shopping feed management tool.
