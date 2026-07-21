# Direct ad-platform MCP setup (Cursor)

This replaces the retired Ryze MCP with direct, per-platform connections:

| Platform | How | Access |
| --- | --- | --- |
| Meta Ads | Official hosted MCP `https://mcp.facebook.com/ads` | Read + write (creates default to PAUSED) |
| GA4 | Official `analytics-mcp` (pipx) | Read-only |
| Search Console | Community `mcp-server-gsc` (npx), same service account | Read + sitemap submit |
| Google Ads | Official `google-ads-mcp` (read-only) + `scripts/gads/` write CLI in this repo | Read via MCP, write via CLI |
| LinkedIn Ads | Marketing API scripts after Marketing Developer Platform approval | Pending approval |

The target client config lives in [`mcp.json.example`](mcp.json.example). Merge it
into `~/.cursor/mcp.json` on the local machine (PowerShell/macOS paths differ —
the example uses the macOS path). **Keep the existing `buffer` entry as is**;
only the `ryze-ads` entry is removed.

---

## 1. Meta Ads (same day, ~10 min)

1. Add the `meta-ads` entry from the example config. No token needed — Cursor
   runs Meta's OAuth flow in the browser on first connect.
2. Sign in with the account that administers Business Manager
   **2756765971296445** and grant ads scopes.
3. Smoke test in Cursor: call `ads_get_ad_accounts` and confirm the elbruscloud
   ad account is listed.

Notes:
- The server is in open beta; tool names may change between versions.
- Campaign creation defaults to **PAUSED** — review in Ads Manager before enabling.

## 2. Google Cloud service account (GA4 + GSC, ~30 min)

```bash
PROJECT_ID=elbrus-marketing            # or reuse an existing project
SA_NAME=elbrus-mcp
gcloud projects create "$PROJECT_ID" 2>/dev/null || true
gcloud config set project "$PROJECT_ID"
gcloud services enable analyticsadmin.googleapis.com \
                       analyticsdata.googleapis.com \
                       searchconsole.googleapis.com
gcloud iam service-accounts create "$SA_NAME" --display-name "Elbrus MCP (Cursor)"
gcloud iam service-accounts keys create ~/.config/elbrus/ga-service-account.json \
  --iam-account "$SA_NAME@$PROJECT_ID.iam.gserviceaccount.com"
```

Then grant the service account email
(`elbrus-mcp@<PROJECT_ID>.iam.gserviceaccount.com`) access in each product UI:

- **GA4**: Admin -> Property (`elbruscloud`, measurement ID `G-JD3TKNY687`) ->
  Property access management -> add the SA email as **Viewer**.
- **Search Console**: `https://search.google.com/search-console` ->
  `elbruscloud.com` property -> Settings -> Users and permissions -> add the SA
  email as **Full** user.

Back up the key to Key Vault (never commit it):

```bash
az keyvault secret set --vault-name <SECUGENT_KV_NAME> \
  --name mcp-google-service-account-json \
  --file ~/.config/elbrus/ga-service-account.json
```

Add the `analytics-mcp` and `gsc-mcp` entries from the example config
(requires `pipx` and Node/`npx` locally). Smoke test: `get_account_summaries`
should list the elbruscloud property; `list_sites` should list
`sc-domain:elbruscloud.com`.

## 3. Google Ads (days — waits on token approval)

1. In the **elbruscloud Google Ads account**: Tools & settings -> Setup ->
   **API Center** -> apply for a developer token (Basic access). Approval is
   typically 1-3 business days.
2. Store it:

   ```bash
   az keyvault secret set --vault-name <SECUGENT_KV_NAME> \
     --name google-ads-developer-token --value <TOKEN>
   ```

3. Add the `google-ads-mcp` entry from the example config (read-only:
   `list_accessible_customers`, GAQL `search`, resource metadata).
4. For **writes** (pause/enable, budgets, keywords, RSAs) use the CLI in
   [`scripts/gads/`](../../scripts/gads/README.md) — the official MCP is
   read-only by design.

Note on auth: the official server supports OAuth user credentials or a service
account. A service account requires a Google Workspace domain-delegation setup;
the simpler path is OAuth desktop credentials (`gcloud auth application-default login`)
with the Google account that has access to the Ads account.

## 4. LinkedIn Ads (weeks — start the application now)

1. Apply at `https://developer.linkedin.com/` -> create an app tied to the
   Elbrus Cloud company page -> request **Marketing Developer Platform** access
   (`r_ads`, `rw_ads`, `r_ads_reporting` scopes). Approval takes ~1-4 weeks.
2. Until approved, manage campaigns in Campaign Manager UI. The Insight Tag
   (partner ID 9255234) is independent of this and keeps working.
3. On approval: store the OAuth client ID/secret + refresh token in Key Vault
   (`linkedin-ads-client-id`, `linkedin-ads-client-secret`,
   `linkedin-ads-refresh-token`) and wire either a community LinkedIn MCP or
   thin scripts alongside `scripts/gads/`.

## Secrets inventory (Azure Key Vault)

| Secret name | Purpose |
| --- | --- |
| `mcp-google-service-account-json` | GA4 + GSC service-account key (backup) |
| `google-ads-developer-token` | Google Ads API dev token |
| `google-ads-oauth-refresh-token` | Google Ads write CLI OAuth refresh token |
| `linkedin-ads-client-id` / `-client-secret` / `-refresh-token` | LinkedIn Marketing API (after MDP approval) |
