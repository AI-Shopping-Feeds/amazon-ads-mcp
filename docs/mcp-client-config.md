# MCP client configuration

The server runs locally over stdio. The examples use `uvx` from [uv](https://docs.astral.sh/uv/);
`pipx run --spec git+https://github.com/AI-Shopping-Feeds/amazon-ads-mcp.git amazon-ads-mcp` works too.

The client ID, client secret and region live in `~/.amazon-ads-mcp/.env` and the
refresh token in `~/.amazon-ads-mcp/secrets/` (see
[setup-amazon-ads-api.md](setup-amazon-ads-api.md)), so client configs don't need
any secrets. Variables set in a client config win over the `.env` files.

## Claude Code

```bash
claude mcp add --scope user amazon-ads \
  --env AMAZON_ADS_DRY_RUN=true \
  -- uvx --from git+https://github.com/AI-Shopping-Feeds/amazon-ads-mcp.git amazon-ads-mcp
```

## Claude Desktop, Cursor and other JSON configs

```json
"amazon-ads": {
  "command": "/full/path/to/uvx",
  "args": ["--from", "git+https://github.com/AI-Shopping-Feeds/amazon-ads-mcp.git", "amazon-ads-mcp"],
  "env": {
    "AMAZON_ADS_DRY_RUN": "true"
  }
}
```

Claude Desktop: `~/Library/Application Support/Claude/claude_desktop_config.json` (macOS) or
`%APPDATA%\Claude\claude_desktop_config.json` (Windows). Cursor: `~/.cursor/mcp.json`.
VS Code uses `servers` instead of `mcpServers` in `.vscode/mcp.json`.

## Codex

```toml
[mcp_servers.amazon-ads]
command = "uvx"
args = ["--from", "git+https://github.com/AI-Shopping-Feeds/amazon-ads-mcp.git", "amazon-ads-mcp"]
env = { AMAZON_ADS_DRY_RUN = "true" }
```

## Keeping files somewhere else

To use another `.env` file, add `--env /abs/path/amazon-ads.env` after `amazon-ads-mcp`
in the arguments. To keep the token or the audit log elsewhere, set
`AMAZON_ADS_TOKEN_FILE=/abs/path/amazon-ads-token.json` or
`AMAZON_ADS_AUDIT_LOG=/abs/path/audit.jsonl`.

For ads accounts in two regions, add the server twice under different names, each with
its own `AMAZON_ADS_REGION` and `AMAZON_ADS_TOKEN_FILE`, and run `auth --region ... --output ...`
once for each.

## Running over HTTP (streamable-http)

stdio is the simplest setup for a single local client. To serve the tools over HTTP, use the
`streamable-http` transport, which is the current MCP standard:

```bash
uvx --from git+https://github.com/AI-Shopping-Feeds/amazon-ads-mcp.git amazon-ads-mcp \
  --transport streamable-http --port 8000
# Claude Code:
claude mcp add --transport http amazon-ads http://127.0.0.1:8000/mcp
```

The server binds to `127.0.0.1` by default and has no authentication of its own. It refuses
to start on any other address (for example `0.0.0.0`) unless you set
`AMAZON_ADS_ALLOW_REMOTE=true` or pass `--allow-remote`. Only do that behind an
authenticating proxy: anyone who can reach the server can change your ads and spend your
budget.

The `sse` transport (HTTP+SSE) still works for older clients but is deprecated by the MCP
specification; the server logs a warning when it is used. Prefer `streamable-http`.

## Limiting the tool list

Large tool lists cost context and make tool choice harder. Expose only what you need:

- `AMAZON_ADS_TOOL_GROUPS=profiles,sp_campaigns,sp_targeting,reporting` registers only those
  tool groups. Groups: `profiles`, `sp_campaigns`, `sp_ads`, `sp_targeting`,
  `sp_recommendations`, `bulk`, `sponsored_brands`, `sponsored_display`, `reporting`,
  `portfolios`, `budget_rules`, `ads_api_v1`, `request`. An unknown group stops the server at
  startup with the list of valid groups.
- `AMAZON_ADS_READ_ONLY=true` registers only read-only tools, for reporting or audit agents
  that must not change the account.

The server tools (`describe_server`, `health_check`, `audit_tail`, `audit_lookup`,
`set_dry_run`) are always registered.

## Environment variables

| Variable | Default | Purpose |
|---|---|---|
| `AMAZON_ADS_CLIENT_ID` | required | Login with Amazon security profile client ID |
| `AMAZON_ADS_CLIENT_SECRET` | required | Login with Amazon security profile client secret |
| `AMAZON_ADS_REGION` | `EU` | `NA`, `EU` or `FE` |
| `AMAZON_ADS_TOKEN_FILE` | `~/.amazon-ads-mcp/secrets/amazon-ads-token.json` | Refresh-token file written by `auth` |
| `AMAZON_ADS_REFRESH_TOKEN` | unset | The refresh token itself, instead of the file |
| `AMAZON_ADS_PROFILE_ID` | unset | Default advertiser profile |
| `AMAZON_ADS_DRY_RUN` | `false` | Preview writes without sending them |
| `AMAZON_ADS_READ_ONLY` | `false` | Register only read-only tools |
| `AMAZON_ADS_TOOL_GROUPS` | unset (all) | Comma-separated tool groups to register |
| `AMAZON_ADS_BULK_THRESHOLD` | `10` | Items per write before `confirm="APPLY"` is needed |
| `AMAZON_ADS_MAX_INCREASE_PCT` | `25` | Bid or budget rise that needs `confirm="APPLY"` |
| `AMAZON_ADS_MAX_BUDGET`, `AMAZON_ADS_MAX_BID` | unset | Optional absolute caps |
| `AMAZON_ADS_AUDIT_LOG` | `~/.amazon-ads-mcp/logs/audit.jsonl` | Where writes are recorded |
| `AMAZON_ADS_AUDIT_RETENTION_DAYS` | `30` | Days to keep audit entries (0 keeps them) |
| `AMAZON_ADS_PAGE_SIZE` | `100` | Results per page for list calls |
| `AMAZON_ADS_TIMEOUT` | `30` | HTTP timeout in seconds |
| `AMAZON_ADS_LOG_LEVEL` | `INFO` | Log level (logs go to stderr) |
| `AMAZON_ADS_TRANSPORT` | `stdio` | `stdio`, `streamable-http` (recommended for HTTP) or `sse` (deprecated) |
| `AMAZON_ADS_HOST` | `127.0.0.1` | Bind host for HTTP transports |
| `AMAZON_ADS_PORT` | `8000` | Bind port for HTTP transports |
| `AMAZON_ADS_ALLOW_REMOTE` | `false` | Allow HTTP transports to bind to a non-loopback host |

Settings are read from the environment first, then the `--env` file (or `./.env` in the
folder the server starts in), then `~/.amazon-ads-mcp/.env`.
