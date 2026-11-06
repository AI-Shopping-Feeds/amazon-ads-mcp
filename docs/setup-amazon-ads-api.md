# Amazon Ads API setup

Amazon Ads MCP uses your own Login with Amazon security profile and your own
approved Amazon Ads API access, so the ads accounts stay under your control.

You need: an Amazon account that can manage the ads, about 30 minutes, and then
up to one business day while Amazon reviews your API application.

Before you start, check that you're eligible and read how the server handles
Amazon data: [terms-and-data.md](terms-and-data.md).

## 1. Create a Login with Amazon security profile

1. Sign in at [developer.amazon.com](https://developer.amazon.com) (create a
   developer account if you don't have one). For a business, use an email
   address several people in the company can reach: it becomes tied to your
   API access and can't be changed later.
2. Open **Developer Console → Login with Amazon → Create a New Security Profile**.
3. Enter a name, a description and your company's privacy policy URL, then **Save**.
4. In the list of security profiles, click **Show Client ID and Client Secret**
   and keep both somewhere safe, like a password manager. Never paste them into
   chat or commit them.
5. On the same profile, open the gear icon → **Web Settings → Edit**, add this
   to **Allowed Return URLs**, then **Save**:

   ```text
   http://localhost:8765/callback
   ```

   If Amazon won't accept a `localhost` address, add `https://amazon.com`
   instead and use `--manual` in step 5.

## 2. Apply for Amazon Ads API access

1. Go to the Amazon Ads API page and choose **Request API access → Direct
   Advertiser**. Agencies and tool makers apply as a Partner through the Amazon
   Ads Partner Network instead.
2. Sign in with **the same email** you used for the developer account.
3. Fill in the form and **Submit for review**. Amazon emails a decision, usually
   within one business day.

## 3. Assign API access to your security profile

When the approval email arrives, **sign out of every other Amazon account in
your browser first** (including personal shopping accounts), then open the link
in the email, choose the security profile from step 1 and **Submit**. The
confirmation page should list the `advertising::campaign_management` scope.

## 4. Save the credentials

The server keeps its files in a folder in your home directory,
`~/.amazon-ads-mcp` (`%USERPROFILE%\.amazon-ads-mcp` on Windows). Create it
(on macOS and Linux, owner-only):

```shell
mkdir -p ~/.amazon-ads-mcp && chmod 700 ~/.amazon-ads-mcp
```

Then create `~/.amazon-ads-mcp/.env` with a text editor (not with `echo`, which
leaves the secret in your shell history):

```text
AMAZON_ADS_CLIENT_ID=amzn1.application-oa2-client.YOUR_CLIENT_ID
AMAZON_ADS_CLIENT_SECRET=YOUR_CLIENT_SECRET
AMAZON_ADS_REGION=EU
AMAZON_ADS_DRY_RUN=true
```

and make it owner-only:

```shell
chmod 600 ~/.amazon-ads-mcp/.env
```

`AMAZON_ADS_DRY_RUN=true` previews writes without sending them. Remove it (or
ask your agent to turn dry-run off) once you're happy with what you see.

[.env.example](../.env.example) lists every setting. The server also reads
`./.env` in the folder it starts in, or the file you pass with `--env`; those
win over `~/.amazon-ads-mcp/.env`, and variables set in the environment (for
example in your MCP client's config) win over all of them.

### Regions

Pick the region of the ads accounts. One refresh token works for one region.

| `AMAZON_ADS_REGION` | Marketplaces |
|---|---|
| `NA` | US, Canada, Mexico, Brazil |
| `EU` (default) | UK, France, Italy, Spain, Germany, Netherlands, UAE, Poland, Turkey, Egypt, Saudi Arabia, Sweden, Belgium, India, South Africa |
| `FE` | Japan, Australia, Singapore |

The UK is in `EU`. If you manage accounts in more than one region, run a second
copy of the server with its own `AMAZON_ADS_REGION` and `AMAZON_ADS_TOKEN_FILE`.

## 5. Connect your Amazon account (one time)

```shell
uvx --from git+https://github.com/AI-Shopping-Feeds/amazon-ads-mcp.git amazon-ads-mcp auth
```

Your browser opens Amazon's consent page. Sign in with the Amazon user that
manages the ads accounts and click **Allow**. The server saves a refresh token
to `~/.amazon-ads-mcp/secrets/amazon-ads-token.json` (owner-only) and never
prints it.

If the local redirect doesn't work (for example on a remote machine, or if you
registered `https://amazon.com` in step 1), run it with `--manual`:

```shell
uvx --from git+https://github.com/AI-Shopping-Feeds/amazon-ads-mcp.git amazon-ads-mcp auth --manual
```

Then paste the full address Amazon sends you to. It must be the address from
this sign-in: the server checks its `state` value and refuses one that is
missing or different.

Other `auth` options: `--region` (default `AMAZON_ADS_REGION`), `--port` for the
local callback (default 8765), `--redirect-uri` if you registered a different
return URL, `--output` to save the token somewhere else (then set
`AMAZON_ADS_TOKEN_FILE` to that path), and `--no-browser` to print the consent
link instead of opening it.

### Refresh-token expiry

Refresh tokens issued from 30 July 2026 expire 365 days after consent. When the
server reports that the token refresh was refused (`invalid_grant`), run `auth`
again.

## 6. Check the settings

```shell
uvx --from git+https://github.com/AI-Shopping-Feeds/amazon-ads-mcp.git amazon-ads-mcp describe
```

It prints the region, paths and safety settings, with `"refresh_token": "set"`
and no secrets.

## 7. Choose a profile

Each Amazon Ads profile is one advertiser in one marketplace. After adding the
server to your client (see the [README](../README.md#3-add-it-to-your-client)),
ask your agent which profiles it can see. It calls `amazon_ads_health_check` (or
`amazon_ads_list_profiles`). Add the one you use most to
`~/.amazon-ads-mcp/.env`:

```text
AMAZON_ADS_PROFILE_ID=1234567890
```

Every tool also takes a `profile_id` argument, so you can work across profiles
in the same region.

## Removing access

- `amazon-ads-mcp purge` deletes the audit log and the stored refresh token.
- To revoke the refresh token, remove the app from the list of apps you've
  allowed to use Login with Amazon, in the Amazon account settings of the user
  who ran `auth`.
- If the client secret may have leaked, generate a new one on the security
  profile in the Amazon Developer Console and update `~/.amazon-ads-mcp/.env`.
