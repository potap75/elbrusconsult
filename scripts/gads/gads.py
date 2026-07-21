#!/usr/bin/env python3
"""Thin, auditable write CLI for Google Ads.

The official google-ads-mcp server is read-only; this CLI covers the write
operations we need, each as an explicit subcommand with --dry-run support
(validate_only) so changes can be previewed before they are applied.

Usage examples (customer ID with or without dashes):

  python gads.py gaql        --customer 1234567890 "SELECT campaign.id, campaign.name, campaign.status FROM campaign"
  python gads.py pause       --customer 1234567890 --campaign 111
  python gads.py enable      --customer 1234567890 --campaign 111
  python gads.py set-budget  --customer 1234567890 --campaign 111 --daily-usd 25
  python gads.py add-keywords --customer 1234567890 --ad-group 222 \
      --match phrase "cloud security consulting" "azure landing zone"
  python gads.py create-rsa  --customer 1234567890 --ad-group 222 \
      --final-url https://elbruscloud.com/ \
      --headline "Enterprise Cloud Foundations" --headline "Fixed-Fee Onboarding" --headline "Zero Lock-In" \
      --description "Production-ready Azure landing zone in a day." \
      --description "Transparent pricing. Cancel anytime."

All mutations print the affected resource names. New RSAs are created PAUSED.
"""

from __future__ import annotations

import argparse
import sys

from _client import build_client


def _cid(value: str) -> str:
    return value.replace("-", "").strip()


def _print_results(response) -> None:
    for result in response.results:
        print(result.resource_name)


# ---------------------------------------------------------------- gaql (read)

def cmd_gaql(client, args) -> None:
    service = client.get_service("GoogleAdsService")
    rows = service.search(customer_id=_cid(args.customer), query=args.query)
    count = 0
    for row in rows:
        print(row)
        count += 1
    print(f"-- {count} row(s)", file=sys.stderr)


# ------------------------------------------------------- campaign status ops

def _set_campaign_status(client, args, status_name: str) -> None:
    customer_id = _cid(args.customer)
    service = client.get_service("CampaignService")
    operation = client.get_type("CampaignOperation")
    campaign = operation.update
    campaign.resource_name = service.campaign_path(customer_id, args.campaign)
    campaign.status = client.enums.CampaignStatusEnum[status_name]

    from google.api_core import protobuf_helpers

    client.copy_from(
        operation.update_mask,
        protobuf_helpers.field_mask(None, campaign._pb),
    )

    request = client.get_type("MutateCampaignsRequest")
    request.customer_id = customer_id
    request.operations.append(operation)
    request.validate_only = args.dry_run
    response = service.mutate_campaigns(request=request)
    if args.dry_run:
        print(f"[dry-run] campaign {args.campaign} -> {status_name}: valid")
    else:
        _print_results(response)


def cmd_pause(client, args) -> None:
    _set_campaign_status(client, args, "PAUSED")


def cmd_enable(client, args) -> None:
    _set_campaign_status(client, args, "ENABLED")


# ------------------------------------------------------------------- budgets

def cmd_set_budget(client, args) -> None:
    customer_id = _cid(args.customer)
    ga_service = client.get_service("GoogleAdsService")
    query = (
        "SELECT campaign.id, campaign.campaign_budget, "
        "campaign_budget.amount_micros FROM campaign "
        f"WHERE campaign.id = {int(args.campaign)}"
    )
    rows = list(ga_service.search(customer_id=customer_id, query=query))
    if not rows:
        sys.exit(f"Campaign {args.campaign} not found in customer {customer_id}.")
    budget_resource = rows[0].campaign.campaign_budget
    old_usd = rows[0].campaign_budget.amount_micros / 1_000_000

    budget_service = client.get_service("CampaignBudgetService")
    operation = client.get_type("CampaignBudgetOperation")
    budget = operation.update
    budget.resource_name = budget_resource
    budget.amount_micros = int(round(args.daily_usd * 1_000_000))

    from google.api_core import protobuf_helpers

    client.copy_from(
        operation.update_mask,
        protobuf_helpers.field_mask(None, budget._pb),
    )

    request = client.get_type("MutateCampaignBudgetsRequest")
    request.customer_id = customer_id
    request.operations.append(operation)
    request.validate_only = args.dry_run
    response = budget_service.mutate_campaign_budgets(request=request)
    prefix = "[dry-run] " if args.dry_run else ""
    print(
        f"{prefix}budget {budget_resource}: "
        f"${old_usd:.2f}/day -> ${args.daily_usd:.2f}/day"
    )
    if not args.dry_run:
        _print_results(response)


# ------------------------------------------------------------------ keywords

def cmd_add_keywords(client, args) -> None:
    customer_id = _cid(args.customer)
    service = client.get_service("AdGroupCriterionService")
    ad_group_service = client.get_service("AdGroupService")
    ad_group_resource = ad_group_service.ad_group_path(customer_id, args.ad_group)

    match_type = client.enums.KeywordMatchTypeEnum[args.match.upper()]
    operations = []
    for text in args.keywords:
        operation = client.get_type("AdGroupCriterionOperation")
        criterion = operation.create
        criterion.ad_group = ad_group_resource
        criterion.status = client.enums.AdGroupCriterionStatusEnum.ENABLED
        criterion.keyword.text = text
        criterion.keyword.match_type = match_type
        operations.append(operation)

    request = client.get_type("MutateAdGroupCriteriaRequest")
    request.customer_id = customer_id
    request.operations.extend(operations)
    request.validate_only = args.dry_run
    response = service.mutate_ad_group_criteria(request=request)
    if args.dry_run:
        print(f"[dry-run] {len(operations)} keyword(s) valid for ad group {args.ad_group}")
    else:
        _print_results(response)


# ----------------------------------------------------------------------- RSA

def cmd_create_rsa(client, args) -> None:
    if len(args.headline) < 3:
        sys.exit("An RSA requires at least 3 --headline values (max 15).")
    if len(args.description) < 2:
        sys.exit("An RSA requires at least 2 --description values (max 4).")

    customer_id = _cid(args.customer)
    service = client.get_service("AdGroupAdService")
    ad_group_service = client.get_service("AdGroupService")

    operation = client.get_type("AdGroupAdOperation")
    ad_group_ad = operation.create
    ad_group_ad.ad_group = ad_group_service.ad_group_path(customer_id, args.ad_group)
    # New ads always start PAUSED for human review.
    ad_group_ad.status = client.enums.AdGroupAdStatusEnum.PAUSED

    ad = ad_group_ad.ad
    ad.final_urls.append(args.final_url)
    for text in args.headline:
        asset = client.get_type("AdTextAsset")
        asset.text = text
        ad.responsive_search_ad.headlines.append(asset)
    for text in args.description:
        asset = client.get_type("AdTextAsset")
        asset.text = text
        ad.responsive_search_ad.descriptions.append(asset)
    if args.path1:
        ad.responsive_search_ad.path1 = args.path1
    if args.path2:
        ad.responsive_search_ad.path2 = args.path2

    request = client.get_type("MutateAdGroupAdsRequest")
    request.customer_id = customer_id
    request.operations.append(operation)
    request.validate_only = args.dry_run
    response = service.mutate_ad_group_ads(request=request)
    if args.dry_run:
        print(f"[dry-run] RSA valid for ad group {args.ad_group} (would be created PAUSED)")
    else:
        _print_results(response)
        print("Created PAUSED — review in Ads Manager, then enable.")


# ---------------------------------------------------------------------- main

def main() -> None:
    parser = argparse.ArgumentParser(
        prog="gads.py", description=__doc__,
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    sub = parser.add_subparsers(dest="command", required=True)

    def common(p, ad_group=False, campaign=False):
        p.add_argument("--customer", required=True, help="Customer ID (dashes ok)")
        p.add_argument("--dry-run", action="store_true",
                       help="Validate only; make no changes")
        if campaign:
            p.add_argument("--campaign", required=True, help="Campaign ID")
        if ad_group:
            p.add_argument("--ad-group", required=True, help="Ad group ID")

    p = sub.add_parser("gaql", help="Run a read-only GAQL query")
    p.add_argument("--customer", required=True)
    p.add_argument("query")
    p.set_defaults(func=cmd_gaql)

    p = sub.add_parser("pause", help="Pause a campaign")
    common(p, campaign=True)
    p.set_defaults(func=cmd_pause)

    p = sub.add_parser("enable", help="Enable a campaign")
    common(p, campaign=True)
    p.set_defaults(func=cmd_enable)

    p = sub.add_parser("set-budget", help="Change a campaign's daily budget")
    common(p, campaign=True)
    p.add_argument("--daily-usd", type=float, required=True)
    p.set_defaults(func=cmd_set_budget)

    p = sub.add_parser("add-keywords", help="Add keywords to an ad group")
    common(p, ad_group=True)
    p.add_argument("--match", choices=["exact", "phrase", "broad"], default="phrase")
    p.add_argument("keywords", nargs="+")
    p.set_defaults(func=cmd_add_keywords)

    p = sub.add_parser("create-rsa", help="Create a responsive search ad (PAUSED)")
    common(p, ad_group=True)
    p.add_argument("--final-url", required=True)
    p.add_argument("--headline", action="append", required=True,
                   help="Repeat 3-15 times, <=30 chars each")
    p.add_argument("--description", action="append", required=True,
                   help="Repeat 2-4 times, <=90 chars each")
    p.add_argument("--path1", default="")
    p.add_argument("--path2", default="")
    p.set_defaults(func=cmd_create_rsa)

    args = parser.parse_args()
    client = build_client()

    from google.ads.googleads.errors import GoogleAdsException

    try:
        args.func(client, args)
    except GoogleAdsException as exc:
        for error in exc.failure.errors:
            print(f"Google Ads error: {error.message}", file=sys.stderr)
        sys.exit(2)


if __name__ == "__main__":
    main()
