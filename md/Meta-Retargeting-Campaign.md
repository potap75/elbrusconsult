# Meta retargeting campaign

Retargets recent elbruscloud.com visitors on Facebook/Instagram to bring
them back to book a consultation. Companion to the Google Search campaign
(see `MCP-Server-Setup.md` and `Sales.md`).

**Status: CREATED (2026-07-22), everything PAUSED pending review in Ads
Manager.** Created via the Marketing API with the `elbrus-ads` system-user
token (Key Vault secret `meta-system-user-token`, never expires; app
`elbruscloud`, id `27876220105304964`, published/Live). The Meta hosted
MCP (`mcp.facebook.com/ads`) could not be used: its OAuth server rejects
Cursor with "Dynamic registration is not available for this client".
The official Meta Ads CLI (`meta`, installed via
`pipx install --python python3.13 meta-ads`) uses the same token
(`ACCESS_TOKEN` env var).

- **Ad account:** `act_2756765971296445` ("Roman Consulting", currency
  **AED**, timezone Asia/Dubai)
- **Facebook Page:** Elbrus Cloud (`1227890120405945`)
- **Pixel:** `506487697553655` (installed via GTM, consent-gated,
  Key Vault secret `meta-pixel-id`)

## Created object IDs

| Object | ID |
|---|---|
| Campaign `Elbrus Cloud — Retargeting — Site Visitors` | `120249055447820703` |
| Ad set `Site visitors 30d — exclude converters` | `120249055492910703` |
| Audience `Website visitors — 30d` | `120249055491620703` |
| Audience `Converters — 180d` (exclusion) | `120249055491730703` |
| Ad `Retargeting — security_eval` | `120249055539170703` |
| Ad `Retargeting — msp_refugee` | `120249055539410703` |
| Ad `Retargeting — one_day` | `120249055539740703` |
| Creative A (security_eval) | `1358994039006265` |
| Creative B (msp_refugee) | `1336221088666204` |
| Creative C (one_day) | `883392021062955` |

---

## Campaign

| Setting | Value |
|---|---|
| Name | `Elbrus Cloud — Retargeting — Site Visitors` |
| Objective | Leads (website conversions) |
| Buying type | Auction |
| Budget | **AED 26/day campaign budget** ≈ $7/day ≈ $210/mo (account bills in AED) |
| Bid strategy | Highest volume (`LOWEST_COST_WITHOUT_CAP`) |
| Status at creation | PAUSED |

Rationale: retargeting pools for a low-traffic B2B site are small, so one
campaign + one ad set keeps the learning phase consolidated. $7/day is
enough to reach a 30-day visitor pool several times without fatiguing it.

## Audiences (create first)

1. **`Website visitors — 30d`** (custom audience, pixel
   `506487697553655`, rule: all website visitors, retention 30 days).
2. **`Converters — 180d`** (custom audience, pixel events:
   `booking_confirmed` OR `contact_submit`, retention 180 days) — used
   as an **exclusion** so we stop paying to chase people who already
   booked or wrote in.

Note: the pixel is consent-gated behind the cookie banner, so the pool
only contains visitors who accepted marketing cookies. Expect the
audience to build slowly; Meta requires ~100 matched people before an
ad set will deliver.

## Ad set

| Setting | Value |
|---|---|
| Name | `Site visitors 30d — exclude converters` |
| Audience | Include `Website visitors — 30d`, exclude `Converters — 180d` |
| Geo | United States |
| Age | 25–64 |
| Placements | Advantage+ (automatic) |
| Optimization | `OFFSITE_CONVERSIONS` → pixel `Lead` event (the pixel already fires `Lead`); Advantage audience expansion **off**. Switch to Landing page views if delivery stalls before the pixel reaches ~50 leads/month |
| Attribution | 7-day click / 1-day view (account default) |

## Ads (3 variants, one per strongest angle)

All link to `https://elbruscloud.com/schedule/` with UTMs:
`utm_source=facebook&utm_medium=paid_social&utm_campaign=retargeting_site_visitors&utm_content=<variant>`

### Variant A — security evaluation (`utm_content=security_eval`)
- **Primary text:** Your first enterprise deal will stall on a security
  questionnaire. Get an evaluation of your cloud security posture and
  walk into that conversation with an audit trail instead of promises.
- **Headline:** Get a cloud security evaluation
- **Description:** Enterprise-grade foundations, SMB prices.
- **CTA button:** Book Now

### Variant B — MSP refugee (`utm_content=msp_refugee`)
- **Primary text:** Ask your MSP for the documentation to your own
  environment — and watch what happens. With us, your infrastructure is
  code, in your repo, from day one. Every change is a diff you approve.
- **Headline:** Own your cloud. Fire us anytime.
- **Description:** Transparent management, zero lock-in.
- **CTA button:** Learn More

### Variant C — delivered in a day (`utm_content=one_day`)
- **Primary text:** The six-week cloud migration quote is why your
  servers got another year older. Our platform builds a governed Azure
  foundation in a day — you approve every change before it happens.
- **Headline:** Enterprise cloud foundations in a day
- **Description:** No SOW. No lock-in. No junior engineers.
- **CTA button:** Book Now

Creative: start with static image ads reusing the site's OG image /
brand imagery; iterate once we see which angle wins.

## Launch checklist

- [x] System-user token generated and stored in Key Vault
      (`meta-system-user-token`); Custom Audiences ToS accepted;
      app `elbruscloud` published (creatives require a Live app)
- [x] Facebook Page confirmed: Elbrus Cloud (`1227890120405945`)
- [x] Custom audiences created (populating; Meta needs >100 matched
      people before delivery starts)
- [x] Campaign + ad set + 3 ads created PAUSED
- [ ] Review in Ads Manager, then enable (campaign, ad set, and each ad
      must all be un-paused)

## Measurement

- Meta-side: campaign results in Ads Manager (optimize toward the
  lead/contact pixel events).
- Site-side: `AttributionMiddleware` captures `fbclid` +
  `utm_*` into first/last-touch cookies; bookings and contact messages
  persist the snapshot in their `attribution` JSONField, enabling
  offline conversion uploads back to Meta later.
