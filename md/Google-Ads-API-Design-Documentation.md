# Google Ads API — Tool Design Documentation

**Applicant:** Elbrus Cloud  
**Website:** https://elbruscloud.com  
**Tool name:** Elbrus Ads Engine  
**Endpoint:** https://mcp.elbruscloud.com/mcp (HTTPS, bearer-token authenticated)  
**Date:** July 2026

> **Note (Google requirement):** This tool is externally reachable on the public
> internet. Access is restricted to authenticated internal operators only (see
> *Tool Access/Use*). Interface mockups and architecture diagrams are included
> below in lieu of a traditional web dashboard.

---

## Company Name

**Elbrus Cloud** — a cloud architecture and cybersecurity consulting firm.

---

## Business Model

Elbrus Cloud operates a marketing and lead-generation website at
**elbruscloud.com**. We run paid search campaigns on Google Ads to drive
qualified traffic to our own site (consulting services, security evaluations,
and scheduling). We do **not** manage Google Ads on behalf of third-party
clients or resell advertising services. All API activity targets our own Google
Ads customer account(s) advertising only properties we own and operate.

---

## Tool Access/Use

| Aspect | Detail |
| --- | --- |
| **Who uses it** | Internal employees only — the founder and designated marketing operator(s) at Elbrus Cloud. |
| **How they access it** | Through **Cursor IDE**, which connects to our remote MCP (Model Context Protocol) server over HTTPS. The operator issues natural-language requests; Cursor invokes typed tools on the server. There is no public signup or multi-tenant access. |
| **Authentication** | Every request (except `/healthz`) must carry a pre-shared **Bearer token** stored in Azure Key Vault. Requests without a valid token receive HTTP 401. If the token is not configured, the server fails closed with HTTP 503. |
| **Network controls** | TLS termination at Nginx; rate limiting (10 req/s, burst 20); Host-header allow-list; systemd sandbox on the VM. |
| **Primary use cases** | (1) Pull campaign/ad-group/keyword performance via GAQL for weekly optimization reviews. (2) Pause or enable campaigns during budget or seasonal adjustments. (3) Adjust daily budgets. (4) Add keywords discovered from Search Console query reports. (5) Create responsive search ads (RSAs) as drafts for human review. |
| **Safety defaults** | All write operations default to **`dry_run=true`**, which maps to the Google Ads API `validate_only` flag — the mutation is validated server-side but not applied. The operator must explicitly pass `dry_run=false` after reviewing the proposed change. New RSAs are **always created in PAUSED status** and must be enabled manually in the Google Ads UI after review. |
| **Frequency** | On demand during internal optimization sessions (typically a few times per week). No unattended bulk automation or inventory sync. |

---

## Tool Design

### High-level architecture

```
┌─────────────────────────────────────────────────────────────────┐
│  Internal operator (Elbrus Cloud employee)                       │
│  Cursor IDE  —  natural-language ad-management requests          │
└────────────────────────────┬────────────────────────────────────┘
                             │ HTTPS + Bearer token
                             ▼
┌─────────────────────────────────────────────────────────────────┐
│  mcp.elbruscloud.com  (Azure VM, Ubuntu)                         │
│  ┌──────────────┐   ┌─────────────────────────────────────────┐ │
│  │ Nginx        │──▶│ Elbrus Ads Engine (FastMCP / Python)    │ │
│  │ TLS, rate    │   │  • Bearer auth middleware               │ │
│  │ limit        │   │  • gads_* / ga4_* / gsc_* tool handlers │ │
│  └──────────────┘   └──────────────┬──────────────────────────┘ │
└────────────────────────────────────┼────────────────────────────┘
                                     │
              ┌──────────────────────┼──────────────────────┐
              ▼                      ▼                      ▼
   Google Ads API            GA4 Data API          Search Console API
   (OAuth refresh token)     (service account)     (service account)
              │                      │                      │
              └──────────────────────┴──────────────────────┘
                                     │
                                     ▼
                    Elbrus Cloud Google Ads account
                    (campaigns for elbruscloud.com only)
```

### Data flow

1. **Read path:** The operator asks Cursor to analyze performance (e.g., “show
   campaign spend for the last 7 days”). Cursor calls `gads_gaql` with a GAQL
   query. The engine executes `GoogleAdsService.Search`, returns up to 500 rows
   as JSON, and Cursor presents the results in the chat pane. No data is
   persisted in a separate database; results live only in the session.

2. **Write path (guarded):** The operator requests a change (e.g., “pause
   campaign 12345”). Cursor calls the appropriate `gads_*` tool with
   `dry_run=true` first. The engine sends a `validate_only` mutate request. If
   validation succeeds, the operator reviews the JSON response and explicitly
   approves; Cursor re-invokes with `dry_run=false` to apply.

3. **Cross-channel context (non-Ads):** The same engine exposes GA4 and Search
   Console read tools so the operator can correlate paid performance with
   organic queries and site analytics before making Ads changes. These do not
   mutate Google Ads entities.

### Infrastructure

- **Compute:** Single Azure Linux VM (`elbrus-app`), same host as elbruscloud.com.
- **Process model:** Gunicorn + UvicornWorker, Unix socket behind Nginx.
- **Secrets:** Azure Key Vault → `/opt/elbrus/adengine.env` (developer token,
  OAuth client ID/secret/refresh token, bearer token). Service-account JSON for
  GA4/GSC at `/opt/elbrus/secrets/ga-service-account.json`.
- **Deployment:** Idempotent bootstrap script on every CI deploy; systemd unit
  `adengine.service`.

### What this tool is *not*

- Not a SaaS product or agency platform.
- Not accessible to external users or advertisers.
- Does not store Ads data in a persistent warehouse or serve a customer-facing
  reporting portal.
- Does not run scheduled bulk jobs that auto-modify campaigns without human
  approval (except health checks on `/healthz`).

---

## API Services Called

All calls target **our own** Google Ads customer ID(s). Typical call volume is
low (tens of requests per week).

### Read operations

| API service / resource | Purpose |
| --- | --- |
| **`GoogleAdsService.Search`** | Run GAQL queries for campaign, ad group, keyword, and metric reports (impressions, clicks, cost, conversions). Used by the `gads_gaql` tool and internally before budget updates to resolve `campaign_budget` resource names. |
| **`Customer`** (via GAQL) | Account-level performance and metadata in reporting queries. |
| **`Campaign`**, **`CampaignBudget`**, **`AdGroup`**, **`AdGroupCriterion`**, **`AdGroupAd`** (via GAQL) | Entity lookup and performance slices in read queries. |

### Write operations (all support `validate_only` / dry-run)

| API service | Mutate request | Purpose |
| --- | --- | --- |
| **`CampaignService`** | `MutateCampaigns` | Pause or enable a campaign (`gads_pause_campaign`, `gads_enable_campaign`). Updates `campaign.status` only. |
| **`CampaignBudgetService`** | `MutateCampaignBudgets` | Change daily budget amount in micros (`gads_set_budget`). Preceded by a GAQL lookup of the linked budget resource. |
| **`AdGroupCriterionService`** | `MutateAdGroupCriteria` | Add keyword criteria to an ad group (`gads_add_keywords`). Creates ENABLED phrase/exact/broad match keywords. |
| **`AdGroupAdService`** | `MutateAdGroupAds` | Create responsive search ads (`gads_create_rsa`). Ads are created with **`AdGroupAdStatus.PAUSED`**; headlines, descriptions, final URL, and optional display paths. |

### Resources touched (write)

- `Campaign` — status field only  
- `CampaignBudget` — `amount_micros`  
- `AdGroupCriterion` — keyword create  
- `AdGroupAd` / `Ad` — RSA create (paused)

We do **not** call billing services, user-management services, or conversion-
upload services through this tool today.

---

## Tool Mockups

This tool does not expose a standalone web dashboard. The operator interface is
**Cursor IDE** connected to the MCP server. Below is a representative session
mockup and the tool catalog the operator sees.

### Mockup: Cursor session — campaign performance review

```
┌─ Cursor ────────────────────────────────────────────────────────────────┐
│  Chat                                                                    │
│  ─────────────────────────────────────────────────────────────────────  │
│  You: Show Google Ads campaign performance for elbruscloud for the      │
│       last 7 days — impressions, clicks, cost, conversions.             │
│                                                                          │
│  Agent: [calls gads_gaql]                                                │
│                                                                          │
│  ┌─ Tool result: gads_gaql ──────────────────────────────────────────┐  │
│  │ row_count: 3                                                       │  │
│  │ rows:                                                              │  │
│  │   campaign { id: 12345678901 name: "Brand - Elbrus Cloud" }      │  │
│  │   metrics { impressions: 8420 clicks: 312 cost_micros: 485000000 │  │
│  │             conversions: 8.0 }                                     │  │
│  │   ...                                                              │  │
│  └────────────────────────────────────────────────────────────────────┘  │
│                                                                          │
│  Agent: Last 7 days — Brand campaign: 8,420 impr, 312 clicks,           │
│         $485 spend, 8 conversions. Non-brand is paused.                  │
│                                                                          │
│  You: Dry-run pause campaign 12345678901.                                │
│                                                                          │
│  Agent: [calls gads_pause_campaign dry_run=true]                         │
│  ✓ Validation passed. Re-run with dry_run=false to apply.               │
└──────────────────────────────────────────────────────────────────────────┘
```

### Mockup: Available MCP tools (Google Ads subset)

| Tool | Type | Description |
| --- | --- | --- |
| `gads_gaql` | Read | Arbitrary GAQL query, max 500 rows |
| `gads_pause_campaign` | Write (guarded) | Set campaign status → PAUSED |
| `gads_enable_campaign` | Write (guarded) | Set campaign status → ENABLED |
| `gads_set_budget` | Write (guarded) | Update linked daily budget (USD) |
| `gads_add_keywords` | Write (guarded) | Add keywords to an ad group |
| `gads_create_rsa` | Write (guarded) | Create RSA in **PAUSED** state |

### Mockup: Dry-run → apply workflow

```
Operator request
       │
       ▼
  dry_run=true  ──▶  Google Ads API validate_only mutate
       │                      │
       │                      ▼
       │               Validation result returned to Cursor
       │                      │
       ▼                      ▼
  Operator reviews JSON in chat
       │
       ▼ (explicit approval)
  dry_run=false ──▶  Google Ads API live mutate
       │
       ▼
  Change visible in Google Ads UI (RSAs remain PAUSED until manual enable)
```

### Endpoint verification

Public health check (no auth): `GET https://mcp.elbruscloud.com/healthz` → `ok`

Authenticated MCP endpoint: `POST https://mcp.elbruscloud.com/mcp` with
`Authorization: Bearer <token>` (token issued to internal operators only).

---

## Contact

**Company:** Elbrus Cloud  
**Website:** https://elbruscloud.com  
**Technical contact:** roman.potapov@elbrusgroup.net
