"""Google Ads tools: GAQL reads plus guarded writes.

Every mutation defaults to dry_run=True, which maps to the Google Ads API's
validate_only flag: the request is fully validated server-side but nothing is
changed. Callers must pass dry_run=False explicitly to apply. New RSAs are
always created PAUSED.
"""

from __future__ import annotations

from adengine.clients import google_ads_client

_MAX_GAQL_ROWS = 500


def _cid(value: str) -> str:
    return value.replace("-", "").strip()


def _result_names(response) -> list[str]:
    return [result.resource_name for result in response.results]


def _campaign_status(customer_id: str, campaign_id: str, status_name: str,
                     dry_run: bool) -> dict:
    from google.api_core import protobuf_helpers

    client = google_ads_client()
    customer_id = _cid(customer_id)
    service = client.get_service("CampaignService")
    operation = client.get_type("CampaignOperation")
    campaign = operation.update
    campaign.resource_name = service.campaign_path(customer_id, campaign_id)
    campaign.status = client.enums.CampaignStatusEnum[status_name]
    client.copy_from(
        operation.update_mask,
        protobuf_helpers.field_mask(None, campaign._pb),
    )

    request = client.get_type("MutateCampaignsRequest")
    request.customer_id = customer_id
    request.operations.append(operation)
    request.validate_only = dry_run
    response = service.mutate_campaigns(request=request)
    return {
        "dry_run": dry_run,
        "campaign_id": campaign_id,
        "new_status": status_name,
        "applied": [] if dry_run else _result_names(response),
    }


def register(mcp) -> None:
    @mcp.tool()
    def gads_gaql(customer_id: str, query: str) -> dict:
        """Run a read-only Google Ads GAQL query. Returns up to 500 rows.

        Example query: SELECT campaign.id, campaign.name, campaign.status,
        metrics.cost_micros FROM campaign WHERE segments.date DURING LAST_7_DAYS
        """
        client = google_ads_client()
        service = client.get_service("GoogleAdsService")
        rows = []
        truncated = False
        for row in service.search(customer_id=_cid(customer_id), query=query):
            if len(rows) >= _MAX_GAQL_ROWS:
                truncated = True
                break
            rows.append(str(row))
        return {"row_count": len(rows), "truncated": truncated, "rows": rows}

    @mcp.tool()
    def gads_pause_campaign(customer_id: str, campaign_id: str,
                            dry_run: bool = True) -> dict:
        """Pause a Google Ads campaign. dry_run=True only validates."""
        return _campaign_status(customer_id, campaign_id, "PAUSED", dry_run)

    @mcp.tool()
    def gads_enable_campaign(customer_id: str, campaign_id: str,
                             dry_run: bool = True) -> dict:
        """Enable a Google Ads campaign. dry_run=True only validates."""
        return _campaign_status(customer_id, campaign_id, "ENABLED", dry_run)

    @mcp.tool()
    def gads_set_budget(customer_id: str, campaign_id: str, daily_usd: float,
                        dry_run: bool = True) -> dict:
        """Change a campaign's shared daily budget (USD). dry_run=True only validates."""
        from google.api_core import protobuf_helpers

        client = google_ads_client()
        customer_id = _cid(customer_id)
        ga_service = client.get_service("GoogleAdsService")
        query = (
            "SELECT campaign.id, campaign.campaign_budget, "
            "campaign_budget.amount_micros FROM campaign "
            f"WHERE campaign.id = {int(campaign_id)}"
        )
        rows = list(ga_service.search(customer_id=customer_id, query=query))
        if not rows:
            return {"error": f"Campaign {campaign_id} not found in customer {customer_id}"}
        budget_resource = rows[0].campaign.campaign_budget
        old_usd = rows[0].campaign_budget.amount_micros / 1_000_000

        budget_service = client.get_service("CampaignBudgetService")
        operation = client.get_type("CampaignBudgetOperation")
        budget = operation.update
        budget.resource_name = budget_resource
        budget.amount_micros = int(round(daily_usd * 1_000_000))
        client.copy_from(
            operation.update_mask,
            protobuf_helpers.field_mask(None, budget._pb),
        )

        request = client.get_type("MutateCampaignBudgetsRequest")
        request.customer_id = customer_id
        request.operations.append(operation)
        request.validate_only = dry_run
        response = budget_service.mutate_campaign_budgets(request=request)
        return {
            "dry_run": dry_run,
            "budget_resource": budget_resource,
            "old_daily_usd": round(old_usd, 2),
            "new_daily_usd": round(daily_usd, 2),
            "applied": [] if dry_run else _result_names(response),
        }

    @mcp.tool()
    def gads_add_keywords(customer_id: str, ad_group_id: str,
                          keywords: list[str], match_type: str = "phrase",
                          dry_run: bool = True) -> dict:
        """Add keywords to an ad group. match_type: exact|phrase|broad. dry_run=True only validates."""
        client = google_ads_client()
        customer_id = _cid(customer_id)
        service = client.get_service("AdGroupCriterionService")
        ad_group_service = client.get_service("AdGroupService")
        ad_group_resource = ad_group_service.ad_group_path(customer_id, ad_group_id)

        match_enum = client.enums.KeywordMatchTypeEnum[match_type.upper()]
        operations = []
        for text in keywords:
            operation = client.get_type("AdGroupCriterionOperation")
            criterion = operation.create
            criterion.ad_group = ad_group_resource
            criterion.status = client.enums.AdGroupCriterionStatusEnum.ENABLED
            criterion.keyword.text = text
            criterion.keyword.match_type = match_enum
            operations.append(operation)

        request = client.get_type("MutateAdGroupCriteriaRequest")
        request.customer_id = customer_id
        request.operations.extend(operations)
        request.validate_only = dry_run
        response = service.mutate_ad_group_criteria(request=request)
        return {
            "dry_run": dry_run,
            "ad_group_id": ad_group_id,
            "keywords": keywords,
            "match_type": match_type,
            "applied": [] if dry_run else _result_names(response),
        }

    @mcp.tool()
    def gads_create_rsa(customer_id: str, ad_group_id: str, final_url: str,
                        headlines: list[str], descriptions: list[str],
                        path1: str = "", path2: str = "",
                        dry_run: bool = True) -> dict:
        """Create a responsive search ad (always PAUSED). Requires 3-15
        headlines (<=30 chars) and 2-4 descriptions (<=90 chars).
        dry_run=True only validates."""
        if not 3 <= len(headlines) <= 15:
            return {"error": "An RSA requires 3-15 headlines."}
        if not 2 <= len(descriptions) <= 4:
            return {"error": "An RSA requires 2-4 descriptions."}

        client = google_ads_client()
        customer_id = _cid(customer_id)
        service = client.get_service("AdGroupAdService")
        ad_group_service = client.get_service("AdGroupService")

        operation = client.get_type("AdGroupAdOperation")
        ad_group_ad = operation.create
        ad_group_ad.ad_group = ad_group_service.ad_group_path(
            customer_id, ad_group_id
        )
        # New ads always start PAUSED for human review.
        ad_group_ad.status = client.enums.AdGroupAdStatusEnum.PAUSED

        ad = ad_group_ad.ad
        ad.final_urls.append(final_url)
        for text in headlines:
            asset = client.get_type("AdTextAsset")
            asset.text = text
            ad.responsive_search_ad.headlines.append(asset)
        for text in descriptions:
            asset = client.get_type("AdTextAsset")
            asset.text = text
            ad.responsive_search_ad.descriptions.append(asset)
        if path1:
            ad.responsive_search_ad.path1 = path1
        if path2:
            ad.responsive_search_ad.path2 = path2

        request = client.get_type("MutateAdGroupAdsRequest")
        request.customer_id = customer_id
        request.operations.append(operation)
        request.validate_only = dry_run
        response = service.mutate_ad_group_ads(request=request)
        return {
            "dry_run": dry_run,
            "ad_group_id": ad_group_id,
            "status": "PAUSED",
            "note": "Created PAUSED - review in Ads Manager, then enable.",
            "applied": [] if dry_run else _result_names(response),
        }
