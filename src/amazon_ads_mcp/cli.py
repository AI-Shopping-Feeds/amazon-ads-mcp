"""CLI entrypoint exposed as the `amazon-ads-mcp` console script.

Subcommands:

* `amazon-ads-mcp run`       (default) — start the MCP server.
* `amazon-ads-mcp auth`      — one-time Login with Amazon consent; saves the refresh token.
* `amazon-ads-mcp purge`     — delete the audit log and the stored refresh token.
* `amazon-ads-mcp describe`  — print the effective configuration (no secrets).
* `amazon-ads-mcp version`   — print the package version.
"""

from __future__ import annotations

import json
import secrets
import sys
import threading
import time
import webbrowser
from datetime import datetime, timezone
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path
from typing import Any
from urllib.parse import parse_qs, urlencode, urlparse

import click
from dotenv import load_dotenv

from . import __version__
from ._logging import configure_default, get_logger
from .auth import SCOPE, exchange_code, redact, register_secret, save_token_file
from .config import REGIONS, TRANSPORTS, audit_log_path, load_config, token_file_path
from .server import build_server

logger = get_logger("cli")

_LOOPBACK_HOSTS = {"127.0.0.1", "localhost", "::1"}


@click.group(invoke_without_command=True)
@click.option(
    "--env",
    "env_file",
    type=click.Path(dir_okay=False, path_type=Path),
    help="Path to a .env file. Defaults to ./.env.",
)
@click.option(
    "--transport",
    type=click.Choice(TRANSPORTS),
    default=None,
    help="Override AMAZON_ADS_TRANSPORT. 'sse' is deprecated; use 'streamable-http'.",
)
@click.option(
    "--host", default=None, help="Bind host for streamable-http / sse (default 127.0.0.1)."
)
@click.option(
    "--port", type=int, default=None, help="Bind port for streamable-http / sse (default 8000)."
)
@click.pass_context
def cli(
    ctx: click.Context,
    env_file: Path | None,
    transport: str | None,
    host: str | None,
    port: int | None,
) -> None:
    """Amazon Ads MCP server."""
    ctx.ensure_object(dict)
    ctx.obj["env_file"] = env_file
    ctx.obj["transport"] = transport
    ctx.obj["host"] = host
    ctx.obj["port"] = port
    if ctx.invoked_subcommand is None:
        ctx.invoke(run)


@cli.command()
@click.pass_context
def run(ctx: click.Context) -> None:
    """Start the MCP server (default subcommand)."""
    configure_default()
    config = load_config(env_file=ctx.obj.get("env_file"))
    if ctx.obj.get("transport"):
        config.transport = ctx.obj["transport"]
    if ctx.obj.get("host"):
        config.host = ctx.obj["host"]
    if ctx.obj.get("port"):
        config.port = ctx.obj["port"]

    mcp = build_server(config=config)

    if config.transport != "stdio" and config.host not in _LOOPBACK_HOSTS:
        logger.warning(
            "binding to %s: the server has no authentication, so anyone who can reach "
            "this address can use your Amazon Ads credentials",
            config.host,
        )
    if config.transport == "stdio":
        mcp.run("stdio")
    elif config.transport == "streamable-http":
        logger.info("serving streamable HTTP on http://%s:%d/mcp", config.host, config.port)
        mcp.run("streamable-http", host=config.host, port=config.port)
    elif config.transport == "sse":
        logger.warning(
            "the sse transport (HTTP+SSE) is deprecated by the MCP spec; "
            "use --transport streamable-http instead"
        )
        mcp.run("sse", host=config.host, port=config.port)
    else:
        raise click.ClickException(f"Unknown transport: {config.transport}")


def authorization_url(*, region: str, client_id: str, redirect_uri: str, state: str) -> str:
    query = urlencode(
        {
            "client_id": client_id,
            "scope": SCOPE,
            "response_type": "code",
            "redirect_uri": redirect_uri,
            "state": state,
        }
    )
    return f"{REGIONS[region].authorize_url}?{query}"


def parse_redirect(value: str, expected_state: str) -> str:
    """Pull the authorization code out of a pasted redirect URL (or a bare code)."""
    value = value.strip()
    if "code=" not in value:
        if not value:
            raise click.ClickException("No code given.")
        return value
    query = parse_qs(urlparse(value).query or value.split("?", 1)[-1])
    if "error" in query:
        raise click.ClickException(f"Amazon returned an error: {query['error'][0]}")
    state = query.get("state", [None])[0]
    if state is not None and state != expected_state:
        raise click.ClickException("The state in the redirect doesn't match; start again.")
    code = query.get("code", [""])[0]
    if not code:
        raise click.ClickException("No code in the redirect URL.")
    return code


def _wait_for_code(port: int, expected_state: str, timeout: float) -> str:
    result: dict[str, str] = {}

    class Handler(BaseHTTPRequestHandler):
        def do_GET(self) -> None:
            parsed = urlparse(self.path)
            query = parse_qs(parsed.query)
            if parsed.path != "/callback":
                self.send_response(404)
                self.end_headers()
                return
            if query.get("state", [""])[0] != expected_state:
                result["error"] = "state mismatch"
            elif "error" in query:
                result["error"] = query["error"][0]
            elif query.get("code"):
                result["code"] = query["code"][0]
            else:
                result["error"] = "no code in the redirect"
            ok = "code" in result
            self.send_response(200 if ok else 400)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.end_headers()
            message = (
                "Authorised. You can close this window and return to the terminal."
                if ok
                else "Authorisation failed. Return to the terminal for details."
            )
            self.wfile.write(f"<html><body><p>{message}</p></body></html>".encode())

        def log_message(self, *args: Any, **kwargs: Any) -> None:  # never log the code
            pass

    server = HTTPServer(("127.0.0.1", port), Handler)
    server.timeout = 1
    deadline = time.monotonic() + timeout
    try:
        while not result and time.monotonic() < deadline:
            server.handle_request()
    finally:
        server.server_close()
    if "code" in result:
        return result["code"]
    if "error" in result:
        raise click.ClickException(f"Authorisation failed: {result['error']}")
    raise click.ClickException("Timed out waiting for the browser redirect.")


@cli.command()
@click.option(
    "--region",
    type=click.Choice(sorted(REGIONS), case_sensitive=False),
    default=None,
    help="Consent region (default AMAZON_ADS_REGION, else EU). Use the region of the ads account.",
)
@click.option("--port", type=int, default=8765, help="Local callback port (default 8765).")
@click.option(
    "--manual",
    is_flag=True,
    help="Don't start a local server: paste the redirected URL instead.",
)
@click.option(
    "--redirect-uri",
    default=None,
    help="Redirect URI registered on the security profile. Default "
    "http://localhost:PORT/callback, or https://amazon.com with --manual.",
)
@click.option(
    "--output",
    "output_path",
    type=click.Path(dir_okay=False, path_type=Path),
    default=None,
    help="Where to save the refresh token (default AMAZON_ADS_TOKEN_FILE or "
    "secrets/amazon-ads-token.json in this checkout).",
)
@click.option("--no-browser", is_flag=True, help="Print the consent URL instead of opening it.")
@click.option(
    "--show-token",
    is_flag=True,
    help="Also print the refresh token once (e.g. to paste into a client config).",
)
@click.option("--timeout", type=float, default=300, help="Seconds to wait for the redirect.")
@click.pass_context
def auth(
    ctx: click.Context,
    region: str | None,
    port: int,
    manual: bool,
    redirect_uri: str | None,
    output_path: Path | None,
    no_browser: bool,
    show_token: bool,
    timeout: float,
) -> None:
    """One-time Login with Amazon consent: get a refresh token for this server.

    Sign in with the Amazon user that has access to the ads accounts. The
    redirect URI must be listed under "Allowed Return URLs" on your security
    profile (Login with Amazon -> Web Settings).
    """
    configure_default()
    config = load_config(env_file=ctx.obj.get("env_file"), require_refresh_token=False)
    register_secret(config.client_secret)
    region = (region or config.region).upper()
    redirect = redirect_uri or (
        "https://amazon.com" if manual else f"http://localhost:{port}/callback"
    )
    state = secrets.token_urlsafe(24)
    url = authorization_url(
        region=region, client_id=config.client_id, redirect_uri=redirect, state=state
    )
    click.echo(f"Redirect URI (must be in Allowed Return URLs): {redirect}")
    click.echo("Open this link, sign in with the Amazon user that manages the ads, and Allow:")
    click.echo(url)

    if manual:
        if not no_browser:
            webbrowser.open(url)
        pasted = click.prompt(
            "Paste the full address you were redirected to (or just the code)", hide_input=True
        )
        code = parse_redirect(pasted, state)
    else:
        if not no_browser:
            threading.Timer(0.5, webbrowser.open, args=(url,)).start()
        click.echo(f"Waiting for the redirect on {redirect} ...")
        code = _wait_for_code(port, state, timeout)

    tokens = exchange_code(
        code=code,
        redirect_uri=redirect,
        client_id=config.client_id,
        client_secret=config.client_secret,
        token_url=REGIONS[region].token_url,
    )
    refresh = tokens["refresh_token"]
    register_secret(refresh)
    target = output_path or config.token_file or token_file_path()
    save_token_file(
        target,
        {
            "refresh_token": refresh,
            "region": region,
            "client_id_suffix": config.client_id[-6:],
            "created_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        },
    )
    click.echo(f"Saved the refresh token to {target} (owner-only permissions).")
    if target.resolve() != token_file_path().resolve():
        click.echo(f"Set AMAZON_ADS_TOKEN_FILE={target.resolve()} so the server finds it.")
    click.echo(
        "Next: run `amazon-ads-mcp describe`, then add the server to your MCP client. "
        "Keep the token file out of git and never paste it into chat."
    )
    if show_token:
        click.echo(f"Refresh token: {refresh}")


@cli.command()
@click.option("--yes", is_flag=True, help="Don't ask for confirmation.")
@click.option("--keep-token", is_flag=True, help="Delete only the audit log.")
@click.pass_context
def purge(ctx: click.Context, yes: bool, keep_token: bool) -> None:
    """Delete locally stored Amazon Ads data: the audit log and the refresh-token file."""
    env_file = ctx.obj.get("env_file")
    if env_file is not None:
        load_dotenv(dotenv_path=env_file, override=False)
    else:
        load_dotenv(override=False)
    audit = audit_log_path()
    targets = [audit, audit.with_suffix(audit.suffix + ".tmp")]
    if not keep_token:
        targets.append(token_file_path())
    existing = [p for p in targets if p.exists()]
    if not existing:
        click.echo("Nothing to delete.")
        return
    click.echo("Will delete:\n" + "\n".join(f"  {p}" for p in existing))
    if not yes and not click.confirm("Delete these files?", default=False):
        click.echo("Cancelled.")
        return
    for p in existing:
        p.unlink()
    click.echo(f"Deleted {len(existing)} file(s).")
    if not keep_token:
        click.echo(
            "If you also set AMAZON_ADS_REFRESH_TOKEN in a client config, remove it there, "
            "and remove this app's access from the Amazon account if you no longer use it."
        )


@cli.command()
def version() -> None:
    """Print the amazon-ads-mcp version."""
    click.echo(__version__)


@cli.command("describe")
@click.pass_context
def describe(ctx: click.Context) -> None:
    """Print effective config (region, profile, paths, limits) and exit. No secrets."""
    configure_default()
    config = load_config(env_file=ctx.obj.get("env_file"), require_refresh_token=False)
    info = {
        "version": __version__,
        "region": config.region,
        "api_host": config.api_host,
        "client_id": f"...{config.client_id[-6:]}",
        "refresh_token": "set" if config.refresh_token else "missing (run `amazon-ads-mcp auth`)",
        "token_file": str(config.token_file) if config.token_file else None,
        "default_profile_id": config.profile_id,
        "audit_log": str(config.audit_log),
        "audit_retention_days": config.audit_retention_days,
        "dry_run": config.dry_run,
        "read_only": config.read_only,
        "tool_groups": config.tool_groups or "all",
        "bulk_threshold": config.bulk_threshold,
        "max_increase_pct": config.max_increase_pct,
        "max_budget": config.max_budget,
        "max_bid": config.max_bid,
        "transport": config.transport,
        "host": config.host,
        "port": config.port,
    }
    click.echo(json.dumps(info, indent=2, ensure_ascii=False))


def main() -> None:
    try:
        cli(obj={})
    except RuntimeError as e:
        # Surface config errors cleanly instead of a Python traceback.
        click.echo(f"Error: {redact(str(e))}", err=True)
        sys.exit(2)


if __name__ == "__main__":
    main()
