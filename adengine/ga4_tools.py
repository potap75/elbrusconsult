"""Google Analytics 4 tools (read-only, service-account auth)."""

from __future__ import annotations

from adengine.clients import ga4_admin_client, ga4_data_client

_MAX_REPORT_ROWS = 1000


def _format_report(response) -> dict:
    dimension_headers = [h.name for h in response.dimension_headers]
    metric_headers = [h.name for h in response.metric_headers]
    rows = [
        {
            **{name: value.value for name, value in
               zip(dimension_headers, row.dimension_values)},
            **{name: value.value for name, value in
               zip(metric_headers, row.metric_values)},
        }
        for row in response.rows
    ]
    return {
        "dimensions": dimension_headers,
        "metrics": metric_headers,
        "row_count": len(rows),
        "rows": rows,
    }


def register(mcp) -> None:
    @mcp.tool()
    def ga4_account_summaries() -> list[dict]:
        """List GA4 accounts and properties visible to the engine's service account."""
        client = ga4_admin_client()
        summaries = []
        for account in client.list_account_summaries():
            summaries.append({
                "account": account.account,
                "display_name": account.display_name,
                "properties": [
                    {"property": p.property, "display_name": p.display_name}
                    for p in account.property_summaries
                ],
            })
        return summaries

    @mcp.tool()
    def ga4_run_report(property_id: str, metrics: list[str],
                       dimensions: list[str] | None = None,
                       start_date: str = "28daysAgo",
                       end_date: str = "today",
                       limit: int = 100) -> dict:
        """Run a GA4 report. property_id is numeric (e.g. "532358716").

        metrics e.g. ["activeUsers", "sessions", "conversions"];
        dimensions e.g. ["date", "sessionDefaultChannelGroup", "pagePath"];
        dates accept YYYY-MM-DD, "today", "yesterday", or "NdaysAgo".
        """
        from google.analytics.data_v1beta.types import (
            DateRange, Dimension, Metric, RunReportRequest,
        )

        client = ga4_data_client()
        request = RunReportRequest(
            property=f"properties/{property_id.removeprefix('properties/')}",
            metrics=[Metric(name=name) for name in metrics],
            dimensions=[Dimension(name=name) for name in (dimensions or [])],
            date_ranges=[DateRange(start_date=start_date, end_date=end_date)],
            limit=min(limit, _MAX_REPORT_ROWS),
        )
        return _format_report(client.run_report(request))

    @mcp.tool()
    def ga4_realtime(property_id: str,
                     metrics: list[str] | None = None,
                     dimensions: list[str] | None = None) -> dict:
        """GA4 realtime snapshot (last 30 minutes). Default metric: activeUsers."""
        from google.analytics.data_v1beta.types import (
            Dimension, Metric, RunRealtimeReportRequest,
        )

        client = ga4_data_client()
        request = RunRealtimeReportRequest(
            property=f"properties/{property_id.removeprefix('properties/')}",
            metrics=[Metric(name=name) for name in (metrics or ["activeUsers"])],
            dimensions=[Dimension(name=name) for name in (dimensions or [])],
        )
        return _format_report(client.run_realtime_report(request))
