# CloudStart — product & pricing structure

Companion to `Sales.md`. One source of truth for (a) the customer-facing
pricing schedule that goes into the service agreement and (b) the exact
Stripe objects that implement it. Keep the two halves in sync: the
contract promises only what Stripe can bill, and Stripe bills only what
the contract defines.

**Billing model (decided earlier):** the customer owns their Azure
subscription and pays Microsoft directly. We never resell cloud. Our fee
is a separate Stripe charge: a one-time onboarding fee, a flat monthly
base fee per plan, and a metered usage fee computed from the customer's
managed cloud spend (which CloudStart already records daily in
`CostSnapshot`).

> Design note: the earlier "max(15% of spend, monthly floor)" idea is
> implemented as **base fee + tiered % of spend** instead. Stripe has no
> native max() on metered items; base-plus-percentage is one line on an
> invoice, guarantees the floor automatically, and is easier to explain
> in a sales call. The percentages below are set slightly lower than the
> pure-15% headline so the all-in cost at typical spend levels lands in
> the same place.

---

## 1. The product catalog (three things, nothing else)

| # | Product | Type | Price |
|---|---------|------|-------|
| 1 | **CloudStart Onboarding** | One-time, per landing zone | $1,500 (waivable as a promo lever) |
| 2 | **CloudStart Management — Practitioner** | Monthly subscription | $99/mo base + spend fee |
| 3 | **CloudStart Management — Leader** | Monthly subscription | $299/mo base + spend fee |

Enterprise is deliberately **not** a Stripe product: custom terms,
invoiced manually, negotiated percentage. Don't build plumbing for a
customer you don't have yet.

### What each plan includes

| | Practitioner | Leader |
|---|---|---|
| Managed landing zones (engagements) | 1 | up to 5 |
| Agent-designed Terraform landing zone | yes | yes |
| Plan-approval workflow (nothing applies without sign-off) | yes | yes |
| Cost + resource-health dashboard | yes | yes |
| Re-plans / architecture changes | 1 per month | unlimited |
| Support | email, 2 business days | email, next business day |
| Quarterly architecture review | — | yes |

### The spend fee (both plans, identical schedule)

Applied to **Managed Cloud Spend** each calendar month, graduated —
each bracket's rate applies only to the slice of spend inside it:

| Monthly managed spend bracket | Rate |
|---|---|
| $0 – $5,000 | **12%** |
| $5,000.01 – $25,000 | **8%** |
| above $25,000 | **5%** |

Worked examples (spend fee + Practitioner base):

| Managed spend | Spend fee | + $99 base | All-in | Effective % |
|---|---|---|---|---|
| $500 | $60 | $159 | $159 | 31.8% (floor doing its job) |
| $2,000 | $240 | $339 | $339 | 17.0% |
| $5,000 | $600 | $699 | $699 | 14.0% |
| $15,000 | $1,400 | $1,499 | $1,499 | 10.0% |
| $40,000 | $2,950 | $3,049 | $3,049 | 7.6% |

The effective rate glides from "minimum viable engagement" pricing at
tiny spend down to competitive-with-MSP rates as the account grows —
no cliff, no renegotiation trigger.

---

## 2. Contract pricing schedule (paste into the service agreement)

Use this as the **Fees** exhibit/schedule. Definitions are the part a
lawyer, an accountant, and a churn-minded customer will each attack —
these close the three known holes.

### Schedule A — Fees

**A.1 Onboarding Fee.** A one-time fee of **US $1,500 per Landing
Zone**, due on execution of this Agreement, covering business intake,
architecture recommendation, landing-zone design, generation of
infrastructure-as-code, and deployment to the Customer's Azure
subscription upon Customer approval.

**A.2 Base Management Fee.** A recurring monthly fee, billed in
advance, per the plan selected on the Order Form: Practitioner
**US $99/month** (one Landing Zone) or Leader **US $299/month** (up to
five Landing Zones).

**A.3 Managed Spend Fee.** A recurring monthly fee, billed in arrears,
calculated on Managed Cloud Spend for the preceding calendar month at
the following graduated rates: 12% of Managed Cloud Spend up to
US $5,000; plus 8% of the portion from US $5,000.01 to US $25,000; plus
5% of the portion above US $25,000.

**A.4 "Managed Cloud Spend"** means the total consumption charges,
before taxes and before any credits independently negotiated by the
Customer with Microsoft, accrued in all Azure subscriptions connected to
the Service under this Agreement, as reported by the Microsoft Cost
Management API. It includes all resources in those subscriptions
regardless of who deployed them. It excludes Azure Marketplace
third-party software charges and one-time reservation or savings-plan
purchase amounts (the consumption they discount is included at its
discounted rate).

*Why "all resources regardless of who deployed them": this is the
anti-attribution-fight clause — the metering boundary is the
subscription, not authorship of individual resources.*

**A.5 Measurement and disputes.** Managed Cloud Spend is measured from
the Customer's own Cost Management data and is visible to the Customer
in the Service dashboard at all times. Fee disputes must be raised
within 30 days of invoice; the Cost Management API record controls.

**A.6 Disconnection.** If the Customer revokes the Service's access to
a connected subscription mid-month, the Managed Spend Fee for that
subscription is calculated on spend accrued through the revocation
date. Base Management Fees are not prorated.

**A.7 Termination.** Either party may terminate with 30 days' notice.
On termination the Customer retains the deployed infrastructure, the
infrastructure-as-code repository, and all documentation. No exit fees.
*(This is the "zero lock-in" sales promise made contractual — keep it.)*

**A.8 Changes.** Fee schedule changes require 60 days' written notice
and apply from the next renewal.

---

## 3. Stripe implementation

### Object map

```
Product: CloudStart Onboarding
└── Price: $1,500 one-time                          → price used in mode='payment' checkout

Product: CloudStart Management — Practitioner
├── Price: $99/month flat (licensed)                → subscription item 1
└── Price: Managed Spend Fee (metered, graduated)   → subscription item 2
        unit = 1 US dollar of Managed Cloud Spend
        tier 1: first 5,000 units  @ $0.12/unit
        tier 2: next 20,000 units  @ $0.08/unit
        tier 3: remainder          @ $0.05/unit

Product: CloudStart Management — Leader
├── Price: $299/month flat (licensed)
└── Price: Managed Spend Fee (same metered price reused)
```

Key decisions baked into that map:

- **One metered price shared by both plans.** The spend schedule is
  identical, so define it once and attach it to both subscriptions.
- **Usage unit = 1 dollar of managed spend.** At month-end, a Celery
  task sums the month's `CostSnapshot` rows per customer, rounds to
  whole dollars, and reports that number as the usage quantity. Stripe's
  graduated tiers then price it — no percentage math in our code.
- **`aggregate_usage = last_during_period`** (not `sum`): report one
  authoritative month-total figure; a re-run of the reporting task
  simply overwrites rather than double-bills.
- **Billing timing follows the contract:** base fee in advance (default
  licensed behavior), metered fee in arrears (default metered behavior).
  One subscription, one invoice, two lines.

### Creation commands (Stripe CLI, run in live mode when ready)

```bash
# 1. Onboarding
stripe products create --name "CloudStart Onboarding" \
  --description "One-time agentic landing-zone build, per landing zone"
stripe prices create --product <ONBOARDING_PRODUCT_ID> \
  --unit-amount 150000 --currency usd

# 2. Practitioner base
stripe products create --name "CloudStart Management — Practitioner" \
  --description "1 managed landing zone, dashboard, email support"
stripe prices create --product <PRACTITIONER_PRODUCT_ID> \
  --unit-amount 9900 --currency usd -d "recurring[interval]=month"

# 3. Leader base
stripe products create --name "CloudStart Management — Leader" \
  --description "Up to 5 managed landing zones, priority replans, quarterly review"
stripe prices create --product <LEADER_PRODUCT_ID> \
  --unit-amount 29900 --currency usd -d "recurring[interval]=month"

# 4. Managed Spend Fee (shared metered price — attach to its own product)
stripe products create --name "CloudStart Managed Spend Fee" \
  --description "Graduated fee on managed Azure spend (unit = 1 USD of spend)"
stripe prices create --product <SPENDFEE_PRODUCT_ID> --currency usd \
  -d "recurring[interval]=month" \
  -d "recurring[usage_type]=metered" \
  -d "recurring[aggregate_usage]=last_during_period" \
  -d "billing_scheme=tiered" \
  -d "tiers_mode=graduated" \
  -d "tiers[0][up_to]=5000"  -d "tiers[0][unit_amount_decimal]=12" \
  -d "tiers[1][up_to]=25000" -d "tiers[1][unit_amount_decimal]=8" \
  -d "tiers[2][up_to]=inf"   -d "tiers[2][unit_amount_decimal]=5"
```

(`unit_amount_decimal` is in cents: 12¢ per $1 of spend = 12%.)

### Webhook

Create one endpoint pointing at
`https://app.elbruscloud.com/api/cloudstart/subscription/webhook/`
listening for `customer.subscription.created/updated/deleted`,
`invoice.payment_succeeded`, `invoice.payment_failed`, then:

```bash
az keyvault secret set --vault-name rag-keyvault-55883113 \
  --name cloudstart-stripe-webhook-secret --value whsec_...
```

### Code touchpoints after the objects exist

| Where | Change |
|---|---|
| `django-backend/apps/cloudstart/services/stripe_service.py` | Replace placeholder `PRICE_TO_TIER` keys with the two real base-price ids; replace `ONBOARDING_PRICE_IDS` with the real onboarding price id |
| `webapp/cloudstart-frontend/src/pages/BillingPage.tsx` | Replace placeholder `priceId` values in `TIERS` |
| Checkout session creation | Subscribe with BOTH items: the plan's base price + the shared metered price |
| New monthly Celery beat task | Sum prior month's `CostSnapshot` totals per customer → `stripe.SubscriptionItem.create_usage_record(quantity=<whole dollars>, action='set')` on the metered item |

The `action='set'` + `last_during_period` pairing is what makes the
usage report idempotent.

---

## 4. Launch pricing levers (decide per deal, not in the contract)

- **Waive the onboarding fee** for the first N customers or a
  case-study commitment — it's the strongest lever against the "MSPs
  charge $10k+ to start" anchor without touching recurring economics.
- **Annual prepay of the base fee at 2 months free** ($990 / $2,990) —
  cheap retention; leave the spend fee monthly regardless.
- Never discount the spend-fee percentages per-deal — that's the part
  that must stay uniform or the metering/product structure fragments.
