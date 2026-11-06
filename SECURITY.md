# Security

This server can create, change, pause and archive Amazon Ads campaigns, ad groups, ads,
keywords, targets, bids, budgets, portfolios and budget rules, so it can spend real money.
It also reads performance reports and account data. It acts with the Login with Amazon
permissions granted by the Amazon user who ran `amazon-ads-mcp auth`.

## Protect your credentials

- The client ID and client secret belong in `~/.amazon-ads-mcp/.env` (or your own `.env`
  file or client config). The refresh token is saved to
  `~/.amazon-ads-mcp/secrets/amazon-ads-token.json`. Never commit, share or paste any of
  them into chat.
- The server creates `~/.amazon-ads-mcp` and its folders owner-only (0700), and the token
  file and audit log owner-only (0600). Keep them that way, and `chmod 600` your `.env`.
- Tokens and the client secret are redacted from logs, errors and the audit log.
- `amazon-ads-mcp purge` deletes the stored refresh token and the audit log.
- If a machine is lost or a secret may have leaked: remove the app from the list of apps
  allowed to use Login with Amazon in the Amazon account settings of the user who ran
  `auth` (this revokes the refresh token), and generate a new client secret on the
  security profile in the Amazon Developer Console.
- Start with `AMAZON_ADS_DRY_RUN=true`, use `AMAZON_ADS_READ_ONLY=true` for agents that only
  report, and set `AMAZON_ADS_MAX_BID` / `AMAZON_ADS_MAX_BUDGET` if you want hard caps.

## Never expose the HTTP transport

The `streamable-http` and `sse` transports have no sign-in. Anyone who can reach the port
can use your Amazon Ads access. The server binds to `127.0.0.1` by default and refuses to
start on any other address unless you set `AMAZON_ADS_ALLOW_REMOTE=true` or pass
`--allow-remote`. Only do that behind a proxy that authenticates every request, and never
on a public network. For a single client, use stdio.

## Reporting a vulnerability or misuse of Amazon data

Report security problems privately with a
[GitHub private security advisory](https://github.com/AI-Shopping-Feeds/amazon-ads-mcp/security/advisories/new).
Use the same form to report a privacy incident or suspected misuse of Amazon Ads data by
or through this server, for example data sent somewhere it shouldn't go, kept longer
than it should be, or accessed without the advertiser's permission.

Include what happened, the version or commit, and how to reproduce it. Don't post working
exploits, leaked credentials, refresh tokens or account data in a public issue. We'll
confirm receipt, investigate and tell you what we found and fixed.

## Supported versions

Security fixes go into the latest release and `main`.
