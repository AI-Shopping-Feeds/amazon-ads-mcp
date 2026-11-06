# Contributing

Thanks for helping improve Amazon Ads MCP.

## Development setup

```bash
git clone https://github.com/AI-Shopping-Feeds/amazon-ads-mcp.git
cd amazon-ads-mcp
uv venv && uv pip install -e ".[test,dev]"
```

Without uv:

```bash
python3 -m venv .venv
.venv/bin/pip install -e ".[test,dev]"
```

Python 3.11 or later. To try it against a real account, follow
[docs/setup-amazon-ads-api.md](docs/setup-amazon-ads-api.md) and run
`.venv/bin/amazon-ads-mcp auth`. Use `AMAZON_ADS_DRY_RUN=true` while you develop.

## Checks

```bash
.venv/bin/ruff check src tests
.venv/bin/ruff format --check src tests
.venv/bin/mypy src/amazon_ads_mcp
.venv/bin/pytest
```

`pre-commit install` runs the same lint and type checks on every commit.

Tests run offline: HTTP is mocked with `respx` and they use a temporary home folder.
They never touch a real Amazon Ads account and need no credentials.

## Pull requests

- Keep secrets, tokens, refresh tokens and account data out of commits, tests and
  issues. Test fixtures use obviously fake values.
- New tools go in the matching module under `src/amazon_ads_mcp/tools/`, use the
  `amazon_ads_` prefix, and need an entry in `src/amazon_ads_mcp/tool_catalog.py`
  (title and read/write/destructive annotations) and a row in
  [docs/tools.md](docs/tools.md). The tests fail if either is missing.
- Writes go through the client so they follow dry-run and the audit log. Archives and
  deletes need a confirm word, and anything that can raise bids or budgets uses the
  safety checks in `safety.py`.
- IDs that go into URL paths must be checked with `path_id()`; the server only talks
  to Amazon hosts.
- Don't paste Amazon's API documentation, specifications, SDK code or sample code into
  the repository. Write descriptions in your own words.
- Update the README, docs and `CHANGELOG.md` when tools, settings or setup change.
