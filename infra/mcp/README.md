# Ad-platform connections for Cursor

Location-agnostic setup: everything is a remote HTTPS MCP server, so any
Cursor install works with just [`mcp.json.example`](mcp.json.example) merged
into `~/.cursor/mcp.json`.

| Server | Endpoint | Covers | Access |
| --- | --- | --- | --- |
| `buffer` | `mcp.buffer.com/mcp` (unchanged) | Organic social posting | Read + write |
| `meta-ads` | `mcp.facebook.com/ads` (Meta-hosted, OAuth) | Meta Ads | Read + write (creates default PAUSED) |
| `elbrus-ads-engine` | `mcp.elbruscloud.com/mcp` (our Azure VM) | Google Ads (read + guarded writes), GA4, Search Console | Bearer token |

LinkedIn Ads is pending Marketing Developer Platform approval (apply at
`https://developer.linkedin.com/`, scopes `r_ads`, `rw_ads`,
`r_ads_reporting`; ~1-4 weeks). Until then use Campaign Manager.

---

## The ads engine (`adengine/`)

FastMCP server deployed on the **elbrus-app VM** by
[`infra/deploy/bootstrap.sh`](../deploy/bootstrap.sh):

- systemd unit [`infra/systemd/adengine.service`](../systemd/adengine.service)
  (gunicorn + UvicornWorker, unix socket `/run/elbrus/adengine.sock`, user
  `elbrus`, venv `/opt/elbrus/adengine-venv`).
- nginx site [`infra/nginx/adengine.conf`](../nginx/adengine.conf) at
  `mcp.elbruscloud.com` (staged on every deploy; enabled once the TLS cert
  exists).
- Bearer-token auth enforced in the app (`ENGINE_BEARER_TOKEN`); unauthorized
  requests get 401, unconfigured engine fails closed with 503. `/healthz` is
  public.

Tools (all Google Ads mutations default to `dry_run=true` = API
`validate_only`; pass `dry_run=false` to apply; new RSAs are always PAUSED):

- `gads_gaql`, `gads_pause_campaign`, `gads_enable_campaign`,
  `gads_set_budget`, `gads_add_keywords`, `gads_create_rsa`
- `ga4_account_summaries`, `ga4_run_report`, `ga4_realtime`
- `gsc_list_sites`, `gsc_search_analytics`, `gsc_submit_sitemap`

### One-time VM setup

1. **DNS**: add an A record `mcp.elbruscloud.com` -> the elbrus-app VM public IP.
2. **Deploy**: push to `main` (CI runs `elbrus-bootstrap`) or run
   `sudo /usr/local/sbin/elbrus-bootstrap` on the VM.
3. **TLS**: `sudo certbot --nginx -d mcp.elbruscloud.com`, then re-run the
   bootstrap (or `sudo ln -sf /etc/nginx/sites-available/adengine.conf
   /etc/nginx/sites-enabled/ && sudo nginx -t && sudo systemctl reload nginx`).
4. **Secrets file** `/opt/elbrus/adengine.env` (mode 600, `elbrus:elbrus`):

   ```bash
   # on a machine with `az login` against the `romanconsulting` subscription
   ssh <vm> 'sudo -u elbrus tee /opt/elbrus/adengine.env >/dev/null && sudo chmod 600 /opt/elbrus/adengine.env' <<EOF
   ENGINE_BEARER_TOKEN=$(az keyvault secret show --vault-name kv-elbruscloud --name adengine-bearer-token --query value -o tsv)
   GADS_DEVELOPER_TOKEN=$(az keyvault secret show --vault-name kv-elbruscloud --name google-ads-developer-token --query value -o tsv)
   GADS_CLIENT_ID=$(az keyvault secret show --vault-name kv-elbruscloud --name google-ads-oauth-client-id --query value -o tsv)
   GADS_CLIENT_SECRET=$(az keyvault secret show --vault-name kv-elbruscloud --name google-ads-oauth-client-secret --query value -o tsv)
   GADS_REFRESH_TOKEN=$(az keyvault secret show --vault-name kv-elbruscloud --name google-ads-oauth-refresh-token --query value -o tsv)
   GOOGLE_APPLICATION_CREDENTIALS=/opt/elbrus/secrets/ga-service-account.json
   EOF
   ```

   The bearer token has already been generated (`openssl rand -hex 32`) and is
   stored in Key Vault `kv-elbruscloud` (subscription `romanconsulting`,
   resource group `rg-elbruscloud`) as secret `adengine-bearer-token`. To
   rotate it, regenerate and overwrite that secret, then redo step 4 and 6.

5. **Service-account key** to `/opt/elbrus/secrets/ga-service-account.json`
   (mode 600, `elbrus:elbrus`), downloaded from Key Vault secret
   `mcp-google-service-account-json`.
6. `sudo systemctl restart adengine.service`, then verify:
   `curl https://mcp.elbruscloud.com/healthz` -> `ok`.

### Google credential prerequisites

- **GCP service account** (GA4 + GSC): create a project, enable
  `analyticsadmin.googleapis.com`, `analyticsdata.googleapis.com`,
  `searchconsole.googleapis.com`; create the SA + key; upload the key JSON to
  Key Vault (`mcp-google-service-account-json`). Grant the SA email:
  - GA4: Property access management on the elbruscloud property
    (`G-JD3TKNY687`) as **Viewer**.
  - Search Console: Users and permissions on `elbruscloud.com` as **Full**.
- **Google Ads developer token**: Google Ads UI -> API Center -> apply for
  Basic access (1-3 business days). Store as `google-ads-developer-token`.
- **Google Ads OAuth**: create a Desktop-app OAuth client in the GCP project;
  mint a refresh token (`python -m google.ads.googleads.oauth2 --client_id ...
  --client_secret ... --scopes https://www.googleapis.com/auth/adwords`)
  signing in as the Google account with access to the Ads account. Store all
  three values in Key Vault.

### Ops

- Logs: `journalctl -u adengine -f`
- Restart after env changes: `sudo systemctl restart adengine.service`
- Rotate the bearer token: update Key Vault + `/opt/elbrus/adengine.env`,
  restart the service, update `~/.cursor/mcp.json` on your machines.
- If Cursor reports 421 errors, the Host allow-list needs updating:
  set `ENGINE_ALLOWED_HOSTS` in `adengine.env` (comma-separated; defaults
  include `mcp.elbruscloud.com`).

## Key Vault secrets inventory

Vault: `kv-elbruscloud` (subscription `romanconsulting`, resource group
`rg-elbruscloud`).

| Secret name | Purpose |
| --- | --- |
| `adengine-bearer-token` | Cursor -> engine auth token (generated and stored; not yet deployed to the VM) |
| `mcp-google-service-account-json` | GA4 + GSC service-account key |
| `google-ads-developer-token` | Google Ads API dev token |
| `google-ads-oauth-client-id` / `-client-secret` / `-refresh-token` | Google Ads OAuth |
| `linkedin-ads-client-id` / `-client-secret` / `-refresh-token` | LinkedIn Marketing API (after MDP approval) |

## Local development

```bash
pip install -r adengine/requirements.txt
ENGINE_BEARER_TOKEN=dev uvicorn adengine.server:app --port 8765
curl http://127.0.0.1:8765/healthz
pytest adengine/tests
```

The `scripts/gads/` CLI remains available as a local/manual alternative for
Google Ads writes; the engine's `gads_*` tools are ports of the same logic.
