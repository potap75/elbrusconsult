# Elbrus Ads Engine — MCP Server Documentation

The **Elbrus Ads Engine** is a self-hosted, remote MCP (Model Context
Protocol) server that gives Cursor (or any MCP client) direct, authenticated
access to our Google marketing stack: **Google Ads** (read + guarded writes),
**Google Analytics 4** (read), and **Google Search Console** (read + sitemap
submission). It replaced the third-party Ryze AI connector after Ryze dropped
Cursor support.

- **Endpoint:** `https://mcp.elbruscloud.com/mcp`
- **Health check:** `https://mcp.elbruscloud.com/healthz` (public, returns `ok`)
- **Source:** [`adengine/`](../adengine/) in this repo
- **Runbook (ops-focused):** [`infra/mcp/README.md`](../infra/mcp/README.md)

---

## Architecture

```
Cursor (any machine)
   │  HTTPS + Authorization: Bearer <token>
   ▼
mcp.elbruscloud.com  ── elbrus-app VM (Azure, Ubuntu, same host as elbruscloud.com)
   │
   ├─ Nginx            TLS (Let's Encrypt), rate limit 10 r/s burst 20,
   │                   only /mcp and /healthz proxied; everything else 444
   ▼
   adengine            FastMCP (Python) via gunicorn + UvicornWorker,
   │                   unix socket /run/elbrus/adengine.sock, user `elbrus`
   │                   Bearer-auth middleware in the app itself
   ▼
   Google APIs         Google Ads API (OAuth refresh token)
                       GA4 Data/Admin API (service account)
                       Search Console API (service account)
```

Key design choices:

- **Remote, not local.** The server runs on the VM so any Cursor install
  (laptop, desktop, cloud) gets identical capability with one config entry —
  no local Python/pipx setup per machine.
- **Stateless HTTP + JSON responses** (`stateless_http=True`,
  `json_response=True` in FastMCP) — each request is self-contained; no
  session affinity needed behind Nginx.
- **Auth lives in the app, not Nginx.** `BearerAuthMiddleware` rejects
  missing/wrong tokens with 401 and **fails closed with 503 if the token
  isn't configured** — a fresh deploy can never serve unauthenticated.
- **Host-header allow-list** (FastMCP transport security): defaults include
  `mcp.elbruscloud.com` and localhost variants; override with
  `ENGINE_ALLOWED_HOSTS` (comma-separated) if needed.

---

## Tools exposed

### Google Ads (`gads_*`) — customer IDs: `3783454052` (Elbrus Cloud client account, has the campaigns), `6539012537` (MCC)

| Tool | Type | Notes |
|---|---|---|
| `gads_gaql` | Read | Arbitrary GAQL, max 500 rows |
| `gads_pause_campaign` / `gads_enable_campaign` | Write | Status change only |
| `gads_set_budget` | Write | Daily budget in USD |
| `gads_add_keywords` | Write | exact/phrase/broad match |
| `gads_create_rsa` | Write | **Always created PAUSED** for human review |

**Safety model:** every write defaults to `dry_run=true`, which maps to the
Google Ads API `validate_only` flag — the mutation is fully validated
server-side but nothing changes. The operator must explicitly pass
`dry_run=false` to apply. This is the core guard against accidental spend
changes. Campaign *creation* is deliberately not exposed; it was done once
via a supervised one-off script.

### Google Analytics 4 (`ga4_*`) — property `542900375` ("elbruscloud")

- `ga4_account_summaries` — list accounts/properties
- `ga4_run_report` — metrics/dimensions/date-range reports
- `ga4_realtime` — last-30-minutes snapshot

### Search Console (`gsc_*`) — property `sc-domain:elbruscloud.com`

- `gsc_list_sites` — list properties (engine has **Full** permission)
- `gsc_search_analytics` — query/page/country/device performance
- `gsc_submit_sitemap` — submit/resubmit `sitemap.xml`

---

## Credentials & secrets

All secrets live in Azure Key Vault **`kv-elbruscloud`** (subscription
`romanconsulting`, resource group `rg-elbruscloud`) and are materialized on
the VM at `/opt/elbrus/adengine.env` (mode 600, owned `elbrus:elbrus`).

| Key Vault secret | Env var on VM | Used for |
|---|---|---|
| `adengine-bearer-token` | `ENGINE_BEARER_TOKEN` | Client → engine auth |
| `google-ads-developer-token` | `GADS_DEVELOPER_TOKEN` | Google Ads API |
| `google-ads-oauth-client-id` | `GADS_CLIENT_ID` | Google Ads OAuth (Desktop-app client in GCP project `elbruscloud`) |
| `google-ads-oauth-client-secret` | `GADS_CLIENT_SECRET` | ” |
| `google-ads-oauth-refresh-token` | `GADS_REFRESH_TOKEN` | Minted once via loopback OAuth as the Ads account owner |
| `mcp-google-service-account-json` | file at `GOOGLE_APPLICATION_CREDENTIALS` (`/opt/elbrus/secrets/ga-service-account.json`) | GA4 + GSC |

Identity notes:

- **Google Ads** authenticates as a *user* (OAuth refresh token) because the
  Ads API has no service-account path for standard accounts.
- **GA4 + GSC** authenticate as the service account
  `adengine-analytics@elbruscloud.iam.gserviceaccount.com` (GCP project
  `elbruscloud`), which is granted GA4 **Viewer** and Search Console
  **Full** in the respective product UIs.
- GCP APIs enabled on the project: `googleads.googleapis.com`,
  `analyticsadmin.googleapis.com`, `analyticsdata.googleapis.com`,
  `searchconsole.googleapis.com`.

### Rotating the bearer token

```bash
az keyvault secret set --subscription romanconsulting \
  --vault-name kv-elbruscloud --name adengine-bearer-token \
  --value "$(openssl rand -hex 32)"
# then: rewrite /opt/elbrus/adengine.env on the VM,
# systemctl restart adengine.service, update ~/.cursor/mcp.json everywhere.
```

---

## Deployment

Deployed by the same pipeline as the website: push to `main` → GitHub Actions
(`.github/workflows/deploy.yml`) → `elbrus-bootstrap` on the VM via
`az vm run-command`. Bootstrap steps relevant to the engine
(`infra/deploy/bootstrap.sh`):

1. Creates/updates the dedicated venv `/opt/elbrus/adengine-venv` and installs
   `adengine/requirements.txt`.
2. Installs `infra/systemd/adengine.service`, enables and restarts it.
3. Stages `infra/nginx/adengine.conf` into sites-available; **enables it only
   if the TLS cert exists** (so a fresh VM passes `nginx -t` before certbot
   has run). The `:80` block in `elbrus.conf` answers for
   `mcp.elbruscloud.com` so ACME challenges work either way.

TLS: `sudo certbot certonly --webroot -w /var/www/letsencrypt -d
mcp.elbruscloud.com` (auto-renews via certbot.timer; current cert expires
2026-10-19 and renews itself).

### Client configuration (Cursor)

`~/.cursor/mcp.json`:

```json
"elbrus-ads-engine": {
  "url": "https://mcp.elbruscloud.com/mcp",
  "headers": { "Authorization": "Bearer <adengine-bearer-token from Key Vault>" }
}
```

---

## Hard-won lessons (do not rediscover these)

1. **seccomp vs gunicorn:** the systemd unit uses
   `SystemCallFilter=~@privileged`, which includes `@chown` — but gunicorn
   `chown()`s the unix socket it binds, so the master died with SIGSYS
   (`status=31/SYS`). Fix: an explicit `SystemCallFilter=@chown` re-allow
   line after the deny. (The website's gunicorn doesn't hit this because it
   receives a pre-created socket FD from `gunicorn.socket`.)
2. **Nginx `proxy_set_header` inheritance is all-or-nothing:** adding a
   single `proxy_set_header Connection ""` inside `location /mcp` cancelled
   the server-level `Host` header, so FastMCP's transport security rejected
   every request with **421 Invalid Host header**. The full header set must
   be repeated inside the location block.
3. **`EnvironmentFile=` must be optional** (`EnvironmentFile=-...`): a
   required env file that doesn't exist yet makes the unit fail with the
   opaque `Failed with result 'resources'` before the secrets are
   provisioned. With `-`, the engine starts and fails closed (503) instead.
4. **Azure B-series VMs restrict kernel namespaces** for non-root systemd
   services: `ProtectSystem=`, `PrivateTmp=` etc. cause `status=226/NAMESPACE`.
   The unit hardens without namespace directives.
5. **DNS before certbot:** the `mcp` A record initially pointed at the wrong
   VM (the CloudStart/rag machine that also hosts `app.elbruscloud.com`).
   Always confirm the authoritative answer matches the target VM's IP before
   running certbot — Let's Encrypt failure rate limits are unforgiving.
6. **Google Ads API service must be enabled** on the GCP project that owns
   the OAuth client (`gcloud services enable googleads.googleapis.com`) —
   the OAuth consent/token flow succeeds without it, and the failure only
   appears on the first API call (`SERVICE_DISABLED`).

---

## Operations quick reference

| Task | Command |
|---|---|
| Engine logs | `journalctl -u adengine -f` (on the VM) |
| Restart engine | `sudo systemctl restart adengine.service` |
| Health check | `curl https://mcp.elbruscloud.com/healthz` → `ok` |
| Auth check | `POST /mcp` without token → 401; with token → JSON-RPC response |
| Run tests locally | `pytest adengine/tests` |
| Local dev server | `ENGINE_BEARER_TOKEN=dev uvicorn adengine.server:app --port 8765` |
| Redeploy | push to `main`, or `sudo /usr/local/sbin/elbrus-bootstrap` on the VM |

**Symptom → cause cheat sheet:**

- `401` — missing/wrong bearer token in the client config.
- `503 server_not_configured` — `ENGINE_BEARER_TOKEN` absent on the VM.
- `421 Invalid Host header` — Host allow-list or Nginx header inheritance
  (see lessons 2 above / `ENGINE_ALLOWED_HOSTS`).
- `Google Ads credentials missing on the engine` — `GADS_*` vars absent from
  `/opt/elbrus/adengine.env`; repopulate from Key Vault and restart.
- `429` — Nginx rate limit; back off.

---

## Related services in the same Cursor config

| Server | Endpoint | Purpose |
|---|---|---|
| `elbrus-ads-engine` | `mcp.elbruscloud.com/mcp` | This document |
| `buffer` | `mcp.buffer.com/mcp` | Organic social posting |
| `meta-ads` | `mcp.facebook.com/ads` | Meta Ads (Meta-hosted, OAuth) |

LinkedIn Ads integration is pending Marketing Developer Platform approval.

---

## Current state (as of 2026-07-22)

- Engine live and verified end-to-end for all three Google services.
- Active campaign: **"Elbrus Cloud - Search - Onboarding & Security"**
  (ID `24058043690`, $9.85/day ≈ $300/mo, 3 ad groups, US/English,
  phrase match, $4 CPC ceiling). The auto-created PMax "Campaign #1"
  (`24055535476`) is paused.
- Google Ads API access: developer token active; brand verification and the
  API-access compliance review are in progress (see
  `md/Google-Ads-API-Design-Documentation.md`).
