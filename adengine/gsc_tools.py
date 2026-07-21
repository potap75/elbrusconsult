"""Google Search Console tools (service-account auth)."""

from __future__ import annotations

from adengine.clients import gsc_service

_MAX_GSC_ROWS = 1000


def register(mcp) -> None:
    @mcp.tool()
    def gsc_list_sites() -> list[dict]:
        """List Search Console properties visible to the engine's service account."""
        response = gsc_service().sites().list().execute()
        return response.get("siteEntry", [])

    @mcp.tool()
    def gsc_search_analytics(site_url: str, start_date: str, end_date: str,
                             dimensions: list[str] | None = None,
                             row_limit: int = 100) -> dict:
        """Query Search Console performance data.

        site_url e.g. "sc-domain:elbruscloud.com"; dates are YYYY-MM-DD;
        dimensions from: query, page, country, device, date, searchAppearance.
        """
        body = {
            "startDate": start_date,
            "endDate": end_date,
            "dimensions": dimensions or ["query"],
            "rowLimit": min(row_limit, _MAX_GSC_ROWS),
        }
        response = (
            gsc_service().searchanalytics()
            .query(siteUrl=site_url, body=body)
            .execute()
        )
        rows = [
            {
                **dict(zip(body["dimensions"], row.get("keys", []))),
                "clicks": row.get("clicks"),
                "impressions": row.get("impressions"),
                "ctr": row.get("ctr"),
                "position": row.get("position"),
            }
            for row in response.get("rows", [])
        ]
        return {"row_count": len(rows), "rows": rows}

    @mcp.tool()
    def gsc_submit_sitemap(site_url: str, sitemap_url: str) -> dict:
        """Submit (or resubmit) a sitemap for a Search Console property.

        e.g. site_url "sc-domain:elbruscloud.com",
        sitemap_url "https://elbruscloud.com/sitemap.xml".
        """
        gsc_service().sitemaps().submit(
            siteUrl=site_url, feedpath=sitemap_url
        ).execute()
        return {"submitted": sitemap_url, "site": site_url}
