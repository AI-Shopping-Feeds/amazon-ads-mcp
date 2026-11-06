# Terms and data handling

Using the Amazon Ads API means accepting Amazon's API License Agreement and
policies. This server is built to fit them, but you are responsible for how you
use it. This project is maintained by AI Shopping Feeds and is not affiliated
with or endorsed by Amazon.

## Eligibility

The Amazon Ads API is for advertisers, agencies and tool makers, and only for
companies that don't run a significant ecommerce business, a DSP or an ad
network. Check Amazon's current terms before you apply.

## How the server handles Amazon data

- **Authorisation.** Only connect advertiser accounts whose owners have
  expressly authorised you to manage them through the API.
- **No Amazon materials here.** This repository contains its own client code and
  tool descriptions. It doesn't include Amazon's API specifications,
  documentation text, SDKs or sample code.
- **Only Amazon endpoints.** The server talks only to your regional Amazon Ads
  API host, the Login with Amazon token endpoint, and Amazon's storage for
  report downloads. No telemetry, no other hosts, and the raw request tools
  can't reach other hosts either.
- **Local files.** Everything the server writes lives in `~/.amazon-ads-mcp`
  unless you choose other paths: the refresh token
  (`secrets/amazon-ads-token.json`) and the audit log (`logs/audit.jsonl`).
  Folders it creates are owner-only (0700) and both files are owner-only (0600).
- **Data retention.** The audit log keeps only write requests, before-snapshots
  and write responses, never read results or report rows, and entries older
  than `AMAZON_ADS_AUDIT_RETENTION_DAYS` (30) are deleted at startup. Reports are
  downloaded and parsed in memory, and files over 200 MB are refused.
  `amazon-ads-mcp purge` deletes the audit log and the stored refresh token.
  Delete Amazon data you no longer need, and on request or when you stop using
  the API.
- **Credentials.** The refresh-token file is written owner-only and kept out of
  git. Tokens and the client secret are redacted from logs, errors and the
  audit log.
- **Throttling.** Throttled requests (HTTP 429) wait for the `Retry-After`
  period before retrying, with backoff.
- **No mixing with other data.** Don't combine Amazon Ads data with data from
  other ad platforms or third-party sources (for example Google Ads) in the same
  analysis or output unless you have Amazon's written approval. The server tells
  the agent this too.
- **AI providers.** Amazon Ads data returned by these tools is sent to the AI
  model your client uses. Use it only under business or API terms where the
  provider doesn't train on your inputs.
- **Network exposure.** The HTTP transports have no sign-in, so the server
  refuses to listen on anything but this machine unless you set
  `AMAZON_ADS_ALLOW_REMOTE=true`. See [SECURITY.md](../SECURITY.md).
- **Trademarks.** "Amazon" and "Amazon Ads" are used here only to say what the
  server works with. No logos, and no claim of partnership or endorsement.

## Security and privacy incidents

To report a security problem in this server, or suspected misuse of Amazon Ads
data by or through it, follow [SECURITY.md](../SECURITY.md). Reports are made
privately through GitHub, not in public issues.

## How this differs from Amazon's own MCP server

Amazon runs an official
[Amazon Ads MCP Server](https://advertising.amazon.com/library/news/amazon-ads-mcp-server-open-beta),
in open beta since 2 February 2026 for Amazon Ads partners with active API
credentials. It is hosted by Amazon and adds multi-step workflow tools (for
example, creating a complete Sponsored Products campaign in one step). If you
qualify and want Amazon-maintained workflows, look at it first.

| | This server | Amazon's MCP server |
|---|---|---|
| Where it runs | On your machine (or your own server) | Hosted by Amazon |
| Who can use it | Anyone with their own approved Amazon Ads API client | Amazon Ads partners with active API credentials (open beta) |
| Audit log | Every write, with a before-snapshot, in a local JSONL file | Not offered |
| Dry-run | Rehearse any write and see exactly what would be sent | Not offered |
| Read-only mode | `AMAZON_ADS_READ_ONLY=true` hides every write tool | Not offered |
| Tool groups | Load only the areas you need (`AMAZON_ADS_TOOL_GROUPS`) | Not offered |
| Spend guards | Confirm words for archives, big batches and bid/budget rises | Not offered |

This comparison reflects Amazon's announcement at the time of writing; check
Amazon's documentation for its current features.
