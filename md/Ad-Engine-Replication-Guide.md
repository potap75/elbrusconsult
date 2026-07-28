# Ad Engine Replication Guide (for Sellwell or any new product)

A step-by-step recipe for standing up the complete ad-management stack we
built for Elbrus Cloud, for a **different product** with **different
secrets**. Written so another agent can execute it mechanically. The Elbrus
instance is the reference implementation; this guide tells you what to copy,
what to rename, and which steps only a human can perform.

What you get at the end:

1. A **self-hosted remote MCP server** ("ads engine") at
   `https://mcp.<product-domain>/mcp` exposing Google Ads (read + guarded
   writes), GA4 (read), and Search Console (read + sitemap submit) to any
   MCP client with a bearer token.
2. A **Meta Marketing API access path** (system-user token) that works even
   though Meta's hosted MCP rejects Cursor, enabling audiences/campaigns/ads
   via the Graph API and the official `meta` CLI.

Reference docs for the original build (read alongside this guide):

- `md/MCP-Server-Setup.md` — architecture + ops of the Elbrus instance
- `infra/mcp/README.md` — ops runbook, secret inventory
- `md/Meta-Retargeting-Campaign.md` — record of the Meta campaign build

---

## 0. Parameter sheet

Every occurrence of these placeholders below must be substituted. Elbrus
values shown for reference.

| Placeholder | Elbrus reference value | Sellwell value (fill in) |
|---|---|---|
| `<product>` | `elbrus` | e.g. `sellwell` |
| `<product-domain>` | `elbruscloud.com` | e.g. `sellwell.com` |
| `<mcp-host>` | `mcp.elbruscloud.com` | e.g. `mcp.sellwell.com` |
| `<vm>` | `elbrus-app` (Azure Ubuntu VM) | the product's VM |
| `<vm-user>` | `elbrus` (system user, owns app + sockets) | e.g. `sellwell` |
| `<app-root>` | `/opt/elbrus` | e.g. `/opt/sellwell` |
| `<kv>` | `kv-elbruscloud` | the product's Key Vault |
| `<subscription>` | `romanconsulting` | Azure subscription |
| `<gcp-project>` | `elbruscloud` | the product's GCP project |
| `<ga4-property-id>` | `542900375` | product GA4 property |
| `<gads-customer-id>` | `3783454052` (client), `6539012537` (MCC) | product Ads account |
| `<meta-business>` | "Elbrus Cloud" | e.g. "Sell What" portfolio |
| `<meta-app-id>` | `27876220105304964` (`elbruscloud`) | `1992500188116687` (`Sellwhat`) already exists |
| `<meta-ad-account>` | `act_2756765971296445` | product ad account |
| `<meta-page-id>` | `1227890120405945` | product Facebook Page |
| `<meta-pixel-id>` | `506487697553655` | product pixel |

Secret **names** inside Key Vault can stay identical across products if each
product has its own vault (recommended). If products share one vault, prefix
the names (e.g. `sellwell-adengine-bearer-token`).

---

## 1. Prerequisites (mostly human-owned)

Accounts and access that must exist before the technical work:

- [ ] Azure: a VM (Ubuntu 22.04+, nginx + systemd, same pattern as the
      product website) and a Key Vault the operator can write to.
- [ ] DNS control for `<product-domain>`.
- [ ] Google Ads account for the product, ideally under the existing MCC
      (`6539012537`). **A developer token is per-MCC, not per-account** —
      if Sellwell's Ads account lives under the same MCC and the same OAuth
      user manages it, you can REUSE the existing developer token and even
      the same OAuth client + refresh token. That collapses section 4 to
      "reuse secrets". A separate MCC needs its own token application
      (Google Ads UI → Admin → API Center → Basic access, 1–3 business days).
- [ ] GA4 property + Search Console property for `<product-domain>`.
- [ ] Meta Business portfolio with the product's ad account, Page, and
      pixel. (For Sellwell: portfolio "Sell What" and app "Sellwhat"
      already exist.)
- [ ] Python 3.11+ on the VM; Python 3.12/3.13 locally for the `meta` CLI
      (the PyPI `meta-ads` package has no 3.14 wheels — use
      `pipx install --python python3.13 meta-ads`).

---

## 2. Copy the engine code

Copy these from this repo (`potap75/elbrusconsult`) into the product's repo:

| Source | Purpose | Edits needed |
|---|---|---|
| `adengine/` (all of it, incl. `tests/`) | FastMCP server: `server.py`, `clients.py`, `gads_tools.py`, `ga4_tools.py`, `gsc_tools.py`, `requirements.txt` | See list below |
| `infra/systemd/adengine.service` | systemd unit | paths + user |
| `infra/nginx/adengine.conf` | nginx site | hostname + upstream |
| `infra/deploy/bootstrap.sh` lines ~88–132 | venv build, unit install, conditional nginx enable | paths + hostname |
| `scripts/gads/` (optional) | local CLI fallback for Google Ads writes | KV names |

Required edits (the code is small and deliberately boring — grep for
`elbrus` and fix every hit):

1. `adengine/server.py`
   - FastMCP server name: `"elbrus-ads-engine"` → `"<product>-ads-engine"`.
   - `instructions=` string: product name.
   - Default `ENGINE_ALLOWED_HOSTS`: replace `mcp.elbruscloud.com` with
     `<mcp-host>` (keep the `localhost`/`127.0.0.1`/`testserver` entries —
     tests and local dev need them).
2. `adengine.service`
   - `User=`/`Group=` → `<vm-user>`; `RuntimeDirectory=` → `<vm-user>`.
   - `WorkingDirectory=<app-root>/app`, venv path
     `<app-root>/adengine-venv`, socket `unix:/run/<vm-user>/adengine.sock`,
     `EnvironmentFile=-<app-root>/adengine.env` (keep the `-`!).
   - Keep ALL the hardening quirks verbatim — they encode real failures:
     `SystemCallFilter=@chown` re-allow (gunicorn chowns its socket, SIGSYS
     otherwise) and NO namespace directives (`ProtectSystem`, `PrivateTmp`
     → `status=226/NAMESPACE` on Azure B-series).
3. `adengine.conf` (nginx)
   - `server_name`, cert paths → `<mcp-host>`; upstream socket path.
   - The `limit_req zone=` must reference a zone defined in the product's
     main nginx config (Elbrus defines `elbrus_default` 10 r/s in
     `elbrus.conf`); create an equivalent.
   - Do NOT "simplify" the repeated `proxy_set_header` lines inside
     `location /mcp` — defining any header there cancels inheritance of the
     server-level set, and a missing `Host` makes FastMCP reject everything
     with 421.
   - The product's `:80` server block must answer for `<mcp-host>` and
     serve the ACME webroot (`/.well-known/acme-challenge/` →
     `/var/www/letsencrypt`) so certbot can issue before the 443 block is
     enabled.
4. `bootstrap.sh` section — adjust paths, and keep the conditional enable:
   stage `adengine.conf` into sites-available on every deploy, symlink into
   sites-enabled **only if** `/etc/letsencrypt/live/<mcp-host>/fullchain.pem`
   exists (otherwise a fresh VM fails `nginx -t`).
5. Run the tests: `pip install -r adengine/requirements.txt pytest &&
   pytest adengine/tests`. They cover the auth middleware (401/503
   fail-closed), tool registration, and dry-run mutation construction, and
   they pass without any live credentials.

---

## 3. Azure secrets

Generate and store (names assume a dedicated `<kv>`):

```bash
# engine bearer token (client -> engine auth)
az keyvault secret set --subscription <subscription> --vault-name <kv> \
  --name adengine-bearer-token --value "$(openssl rand -hex 32)"
```

Full inventory the engine needs (populate over sections 4–5):

| Key Vault secret | Env var on VM | Source |
|---|---|---|
| `adengine-bearer-token` | `ENGINE_BEARER_TOKEN` | generated above |
| `google-ads-developer-token` | `GADS_DEVELOPER_TOKEN` | MCC API Center (or reuse) |
| `google-ads-oauth-client-id` | `GADS_CLIENT_ID` | GCP OAuth client (Desktop app) |
| `google-ads-oauth-client-secret` | `GADS_CLIENT_SECRET` | ” |
| `google-ads-oauth-refresh-token` | `GADS_REFRESH_TOKEN` | minted once, section 4 |
| `mcp-google-service-account-json` | file at `GOOGLE_APPLICATION_CREDENTIALS` | GCP SA key, section 5 |
| `meta-system-user-token` | (not used by engine; used by agents/CLI) | Meta BM, section 8 |

---

## 4. Google Ads credentials

Skip to "reuse" if Sellwell's Ads account is under the same MCC and managed
by the same Google user — then copy the three `google-ads-oauth-*` secrets
and the developer token into `<kv>` and you are done with this section.

Fresh setup:

1. GCP project `<gcp-project>`: `gcloud services enable
   googleads.googleapis.com` — do this FIRST; the OAuth flow succeeds
   without it and the failure (`SERVICE_DISABLED`) only appears on the
   first API call.
2. OAuth consent screen: External. **The app homepage URL must be a page
   that actually describes the application** — Google rejected the generic
   marketing homepage during brand verification. Elbrus solved this with a
   dedicated `/ads-engine/` page (see `backend/templates/pages/ads_engine.html`
   and `md/Google-Ads-API-Design-Documentation.md`); replicate that page on
   `<product-domain>` (describe the app, list the `auth/adwords` scope,
   link the privacy policy, mention Limited Use compliance).
3. Create an OAuth client, type **Desktop app**. Store id + secret in `<kv>`.
4. Mint the refresh token (human must complete the browser sign-in as the
   Google user that has access to the Ads account):

   ```bash
   pip install google-ads
   python -m google.ads.googleads.oauth2 \
     --client_id ... --client_secret ... \
     --scopes https://www.googleapis.com/auth/adwords
   # store the printed refresh token WITHOUT writing it to disk:
   az keyvault secret set --vault-name <kv> \
     --name google-ads-oauth-refresh-token --value '<token>'
   ```

5. Developer token: Google Ads UI as the MCC → Admin → API Center → apply
   for Basic access. Until approval it works in test mode only.

## 5. GA4 + Search Console service account

1. In `<gcp-project>`: `gcloud services enable
   analyticsadmin.googleapis.com analyticsdata.googleapis.com
   searchconsole.googleapis.com`
2. Create SA `adengine-analytics@<gcp-project>.iam.gserviceaccount.com`,
   create a JSON key, upload to `<kv>` as `mcp-google-service-account-json`.
3. Human grants (product UIs, not IAM):
   - GA4 property `<ga4-property-id>` → Property access management → add
     the SA email as **Viewer**.
   - Search Console `sc-domain:<product-domain>` → Users and permissions →
     add the SA email as **Full** (Full is required for sitemap submission).

## 6. VM deployment

1. **DNS first**: A record `<mcp-host>` → the VM's public IP. Verify the
   authoritative answer before certbot (`dig +short <mcp-host>`) — the
   Elbrus record initially pointed at the wrong VM, and Let's Encrypt
   failure rate-limits are unforgiving.
2. Deploy the code (product's bootstrap/CI). The engine unit starts and
   **fails closed with 503** until secrets exist — that's expected.
3. TLS: `sudo certbot certonly --webroot -w /var/www/letsencrypt -d
   <mcp-host>`, then re-run bootstrap (it will now enable the nginx site).
4. Materialize secrets on the VM (from a machine with `az login`):

   ```bash
   ssh <vm> 'sudo -u <vm-user> tee <app-root>/adengine.env >/dev/null \
             && sudo chmod 600 <app-root>/adengine.env' <<EOF
   ENGINE_BEARER_TOKEN=$(az keyvault secret show --vault-name <kv> --name adengine-bearer-token --query value -o tsv)
   GADS_DEVELOPER_TOKEN=$(az keyvault secret show --vault-name <kv> --name google-ads-developer-token --query value -o tsv)
   GADS_CLIENT_ID=$(az keyvault secret show --vault-name <kv> --name google-ads-oauth-client-id --query value -o tsv)
   GADS_CLIENT_SECRET=$(az keyvault secret show --vault-name <kv> --name google-ads-oauth-client-secret --query value -o tsv)
   GADS_REFRESH_TOKEN=$(az keyvault secret show --vault-name <kv> --name google-ads-oauth-refresh-token --query value -o tsv)
   GOOGLE_APPLICATION_CREDENTIALS=<app-root>/secrets/ga-service-account.json
   EOF
   ```

   Add `GADS_LOGIN_CUSTOMER_ID=<mcc-id>` if access goes through an MCC.
   Then download the SA key to `<app-root>/secrets/ga-service-account.json`
   (mode 600, `<vm-user>:<vm-user>`) and
   `sudo systemctl restart adengine.service`.
5. Smoke tests:

   ```bash
   curl https://<mcp-host>/healthz                    # -> ok
   curl -s -X POST https://<mcp-host>/mcp             # -> 401 (no token)
   # with token: JSON-RPC initialize handshake succeeds
   curl -s -X POST https://<mcp-host>/mcp \
     -H "Authorization: Bearer $TOKEN" \
     -H 'Content-Type: application/json' \
     -H 'Accept: application/json, text/event-stream' \
     --data '{"jsonrpc":"2.0","id":1,"method":"initialize","params":{"protocolVersion":"2025-06-18","capabilities":{},"clientInfo":{"name":"probe","version":"0"}}}'
   ```

## 7. Cursor client config

Merge into `~/.cursor/mcp.json` on each machine:

```json
"<product>-ads-engine": {
  "url": "https://<mcp-host>/mcp",
  "headers": { "Authorization": "Bearer <adengine-bearer-token from <kv>>" }
}
```

---

## 8. Meta access (system-user token — the path that actually works)

Meta's hosted MCP (`mcp.facebook.com/ads`) **rejects Cursor**: its OAuth
server allows only pre-approved clients (Claude, ChatGPT) and returns
`invalid_client_metadata: "Dynamic registration is not available for this
client"`. Do not burn time on it; use a system-user token with the Graph
API / official `meta` CLI instead. Re-check the MCP occasionally — if Meta
adds Cursor, it's a one-line config.

Human steps in business.facebook.com (Business settings, portfolio
`<meta-business>`) — order matters, each gate produced a real error:

1. **App**: create (or reuse — for Sellwell the app `Sellwhat`,
   id `1992500188116687`, already exists) a Business-type app with the
   **"Create & manage ads with Marketing API"** use case.
   Set the Privacy Policy URL (Settings → Basic), then **publish the app**
   (left sidebar "Publish"; the new dashboard has no App Mode toggle).
   An unpublished/dev-mode app fails ad-creative creation with error
   subcode `1885183`.
2. **System user**: Users → System users → Add. Name with at most ONE
   hyphen (`sellwell-ads` is fine; `sell-well-ads` is rejected). Role Admin.
3. **Assign assets to the system user** (not just to the app!):
   - Ad account `<meta-ad-account>` with **Manage campaigns** — without
     this, writes fail `(#200, subcode 2490585) No write permission`.
   - The Facebook Page with **Content + Ads** partial access.
4. **Attach the system user to the app**: Accounts → Apps → the app →
   Assign people → system user, Full control. Token generation shows
   "No permissions available" until this is done.
5. **Generate token**: System users → Generate token → select the app →
   expiry **Never** → scopes: `ads_management`, `ads_read`,
   `business_management`, `pages_show_list`, `pages_read_engagement`
   (`pages_manage_ads` comes along via the Page assignment).
6. **Accept Custom Audiences ToS** (once per ad account, human click):
   `https://www.facebook.com/customaudiences/app/tos/?act=<meta-ad-account-number>`
   — until then audience creation fails `(#2663)`.

Store the token:

```bash
az keyvault secret set --vault-name <kv> \
  --name meta-system-user-token --value '<TOKEN>'
```

Verify (expected: system-user identity, the ad account visible, pixel
listed):

```bash
TOKEN=$(az keyvault secret show --vault-name <kv> --name meta-system-user-token --query value -o tsv)
curl -s "https://graph.facebook.com/v23.0/me" -H "Authorization: Bearer $TOKEN"
curl -s "https://graph.facebook.com/v23.0/me/adaccounts?fields=id,name,account_status,currency" -H "Authorization: Bearer $TOKEN"
curl -s "https://graph.facebook.com/v23.0/debug_token?input_token=$TOKEN" -H "Authorization: Bearer $TOKEN"
```

API gotchas hit during the Elbrus build (all reproducible):

- **Currency/timezone**: budgets are minor units of the AD ACCOUNT's
  currency (Elbrus account bills in AED: `daily_budget=2600` = AED 26 ≈
  $7/day). Check `currency` before setting budgets.
- Custom audience creation: do NOT pass `subtype` on v23+ (`subtype is not
  supported`); the pixel rule implies WEBSITE.
- Ad set creation requires
  `targeting_automation.advantage_audience: 0|1` explicitly (error
  subcode `1870227`); use `0` for strict retargeting.
- Campaign creation requires `special_ad_categories=[]` explicitly.
- Everything should be created `status=PAUSED`; a human enables in Ads
  Manager after review (and must un-pause campaign, ad set, AND ads).
- Meta needs ~100 matched people in a custom audience before delivery;
  consent-gated pixels fill slowly.
- The official CLI: `pipx install --python python3.13 meta-ads`, then
  `ACCESS_TOKEN=<token> AD_ACCOUNT_ID=<meta-ad-account> meta ads campaign
  list`. It covers campaigns/ad sets/ads/creatives/insights but NOT custom
  audiences — create those via the Graph API directly.

---

## 9. Final verification checklist

- [ ] `pytest adengine/tests` green in the product repo
- [ ] `https://<mcp-host>/healthz` → `ok`
- [ ] `POST /mcp` without token → 401; with token → initialize succeeds
- [ ] Cursor lists the `gads_*` / `ga4_*` / `gsc_*` tools
- [ ] `gads_gaql` returns campaigns; a `gads_set_budget` **dry-run**
      validates; GA4 report and GSC query return data
- [ ] Meta: `me/adaccounts` shows the account; a test custom-audience
      create succeeds (then delete it)
- [ ] All secrets in `<kv>`; nothing in the repo, shell history, or `/tmp`
- [ ] Rotation documented: bearer token = regenerate KV secret → rewrite
      `adengine.env` → restart service → update `mcp.json` everywhere
