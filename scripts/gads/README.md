# Google Ads write CLI

The official `google-ads-mcp` server (wired in [`infra/mcp/`](../../infra/mcp/README.md))
is read-only by design. This CLI covers the write operations, each as an
explicit, auditable subcommand. New ads are always created **PAUSED**, and every
mutation supports `--dry-run` (API `validate_only`) for preview.

## Setup (local machine)

```bash
python3 -m venv .venv && source .venv/bin/activate   # or use pipx/uv
pip install -r requirements.txt
```

Credentials come from env vars, with Azure Key Vault fallback (`az login` +
`GADS_KV_VAULT=<vault name>`):

| Env var | Key Vault secret |
| --- | --- |
| `GADS_DEVELOPER_TOKEN` | `google-ads-developer-token` |
| `GADS_CLIENT_ID` | `google-ads-oauth-client-id` |
| `GADS_CLIENT_SECRET` | `google-ads-oauth-client-secret` |
| `GADS_REFRESH_TOKEN` | `google-ads-oauth-refresh-token` |
| `GADS_LOGIN_CUSTOMER_ID` (optional) | — (manager account ID, if used) |

One-time OAuth bootstrap: create an OAuth **Desktop app** client in the same
GCP project (APIs & Services -> Credentials), then generate a refresh token
with Google's helper:

```bash
pip install google-ads
python -m google.ads.googleads.oauth2 \
  --client_id <ID> --client_secret <SECRET> \
  --scopes https://www.googleapis.com/auth/adwords
# sign in as the Google account that has access to the elbruscloud Ads account
```

Store all four values in Key Vault (see the secrets inventory in
[`infra/mcp/README.md`](../../infra/mcp/README.md)).

## Commands

```bash
python gads.py gaql --customer 123-456-7890 \
  "SELECT campaign.id, campaign.name, campaign.status FROM campaign"

python gads.py pause      --customer 123-456-7890 --campaign 111 --dry-run
python gads.py enable     --customer 123-456-7890 --campaign 111
python gads.py set-budget --customer 123-456-7890 --campaign 111 --daily-usd 25

python gads.py add-keywords --customer 123-456-7890 --ad-group 222 \
  --match phrase "cloud security consulting" "azure landing zone"

python gads.py create-rsa --customer 123-456-7890 --ad-group 222 \
  --final-url https://elbruscloud.com/ \
  --headline "Enterprise Cloud Foundations" \
  --headline "Fixed-Fee Onboarding" \
  --headline "Zero Lock-In" \
  --description "Production-ready Azure landing zone in a day." \
  --description "Transparent pricing. Cancel anytime."
```

Recommended flow for the Cursor agent: run with `--dry-run` first, show the
output, then re-run without the flag after confirmation.
