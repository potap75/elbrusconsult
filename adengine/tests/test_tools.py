"""Tool registration and Google Ads dry-run construction with stubbed creds."""

import json
from unittest import mock

import pytest

EXPECTED_TOOLS = {
    "gads_gaql",
    "gads_pause_campaign",
    "gads_enable_campaign",
    "gads_set_budget",
    "gads_add_keywords",
    "gads_create_rsa",
    "ga4_account_summaries",
    "ga4_run_report",
    "ga4_realtime",
    "gsc_list_sites",
    "gsc_search_analytics",
    "gsc_submit_sitemap",
}


@pytest.mark.anyio
async def test_all_tools_registered():
    from adengine.server import mcp

    tools = {tool.name for tool in await mcp.list_tools()}
    assert EXPECTED_TOOLS <= tools


@pytest.fixture()
def anyio_backend():
    return "asyncio"



def _payload(result):
    """call_tool returns a content list (or (contents, structured))."""
    contents = result[0] if isinstance(result, tuple) else result
    item = contents[0] if isinstance(contents, list) else contents
    return json.loads(item.text)

def _stub_google_ads_client():
    """A real GoogleAdsClient (anonymous creds) whose services never hit
    the network: mutate_* and search are intercepted and recorded."""
    import google.ads.googleads.oauth2 as oauth2
    from google.auth.credentials import AnonymousCredentials

    with mock.patch.object(oauth2, "get_credentials",
                           return_value=AnonymousCredentials()):
        from google.ads.googleads.client import GoogleAdsClient

        real_client = GoogleAdsClient.load_from_dict({
            "developer_token": "x", "client_id": "x", "client_secret": "x",
            "refresh_token": "x", "use_proto_plus": True,
        })

    captured = {}

    class ServiceStub:
        def __init__(self, real_service, name):
            self._real = real_service
            self._name = name

        def __getattr__(self, attr):
            if attr.startswith("mutate_"):
                def _mutate(request=None, **kwargs):
                    captured[attr] = request
                    return mock.Mock(results=[])
                return _mutate
            if attr == "search":
                def _search(customer_id=None, query=None, **kwargs):
                    captured["search"] = {"customer_id": customer_id,
                                          "query": query}
                    return iter(captured.get("search_rows", []))
                return _search
            return getattr(self._real, attr)

    class ClientStub:
        def __getattr__(self, attr):
            return getattr(real_client, attr)

        def get_service(self, name):
            return ServiceStub(real_client.get_service(name), name)

    return ClientStub(), captured


@pytest.mark.anyio
async def test_pause_campaign_dry_run_by_default():
    from adengine import gads_tools
    from adengine.server import mcp

    client, captured = _stub_google_ads_client()
    with mock.patch.object(gads_tools, "google_ads_client",
                           return_value=client):
        result = await mcp.call_tool(
            "gads_pause_campaign",
            {"customer_id": "123-456-7890", "campaign_id": "42"},
        )

    payload = _payload(result)
    assert payload["dry_run"] is True
    request = captured["mutate_campaigns"]
    assert request.validate_only is True
    assert request.customer_id == "1234567890"
    update = request.operations[0].update
    assert update.resource_name == "customers/1234567890/campaigns/42"
    assert update.status.name == "PAUSED"
    assert "status" in list(request.operations[0].update_mask.paths)


@pytest.mark.anyio
async def test_add_keywords_apply_mode():
    from adengine import gads_tools
    from adengine.server import mcp

    client, captured = _stub_google_ads_client()
    with mock.patch.object(gads_tools, "google_ads_client",
                           return_value=client):
        result = await mcp.call_tool(
            "gads_add_keywords",
            {"customer_id": "1234567890", "ad_group_id": "77",
             "keywords": ["cloud security consulting"],
             "match_type": "phrase", "dry_run": False},
        )

    payload = _payload(result)
    assert payload["dry_run"] is False
    request = captured["mutate_ad_group_criteria"]
    assert request.validate_only is False
    criterion = request.operations[0].create
    assert criterion.keyword.text == "cloud security consulting"
    assert criterion.keyword.match_type.name == "PHRASE"


@pytest.mark.anyio
async def test_create_rsa_always_paused_and_validates_counts():
    from adengine import gads_tools
    from adengine.server import mcp

    client, captured = _stub_google_ads_client()
    with mock.patch.object(gads_tools, "google_ads_client",
                           return_value=client):
        too_few = await mcp.call_tool(
            "gads_create_rsa",
            {"customer_id": "1", "ad_group_id": "2",
             "final_url": "https://elbruscloud.com/",
             "headlines": ["a", "b"], "descriptions": ["d1", "d2"]},
        )
        payload = _payload(too_few)
        assert "error" in payload

        ok = await mcp.call_tool(
            "gads_create_rsa",
            {"customer_id": "1", "ad_group_id": "2",
             "final_url": "https://elbruscloud.com/",
             "headlines": ["h1", "h2", "h3"],
             "descriptions": ["d1", "d2"]},
        )

    payload = _payload(ok)
    assert payload["status"] == "PAUSED"
    request = captured["mutate_ad_group_ads"]
    assert request.validate_only is True
    ad_group_ad = request.operations[0].create
    assert ad_group_ad.status.name == "PAUSED"
    assert len(ad_group_ad.ad.responsive_search_ad.headlines) == 3


@pytest.mark.anyio
async def test_missing_credentials_surface_clean_error(monkeypatch):
    from adengine import clients
    from adengine.server import mcp

    from mcp.server.fastmcp.exceptions import ToolError

    for var in ("GADS_DEVELOPER_TOKEN", "GADS_CLIENT_ID",
                "GADS_CLIENT_SECRET", "GADS_REFRESH_TOKEN"):
        monkeypatch.delenv(var, raising=False)
    clients.google_ads_client.cache_clear()

    with pytest.raises(ToolError, match="credentials missing"):
        await mcp.call_tool(
            "gads_gaql",
            {"customer_id": "1", "query": "SELECT campaign.id FROM campaign"},
        )
