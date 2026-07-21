"""Cached, lazily-built API clients for the ads engine.

All credentials come from the environment (populated on the VM from
/opt/elbrus/adengine.env via systemd EnvironmentFile):

  GADS_DEVELOPER_TOKEN / GADS_CLIENT_ID / GADS_CLIENT_SECRET /
  GADS_REFRESH_TOKEN [/ GADS_LOGIN_CUSTOMER_ID]   -> Google Ads
  GOOGLE_APPLICATION_CREDENTIALS (service-account JSON path)
                                                  -> GA4 + Search Console
"""

from __future__ import annotations

import os
from functools import lru_cache

_GADS_REQUIRED = (
    "GADS_DEVELOPER_TOKEN",
    "GADS_CLIENT_ID",
    "GADS_CLIENT_SECRET",
    "GADS_REFRESH_TOKEN",
)


class CredentialsError(RuntimeError):
    pass


@lru_cache(maxsize=1)
def google_ads_client():
    missing = [name for name in _GADS_REQUIRED if not os.environ.get(name)]
    if missing:
        raise CredentialsError(
            "Google Ads credentials missing on the engine: "
            + ", ".join(missing)
            + ". Populate /opt/elbrus/adengine.env and restart adengine."
        )

    from google.ads.googleads.client import GoogleAdsClient

    config = {
        "developer_token": os.environ["GADS_DEVELOPER_TOKEN"],
        "client_id": os.environ["GADS_CLIENT_ID"],
        "client_secret": os.environ["GADS_CLIENT_SECRET"],
        "refresh_token": os.environ["GADS_REFRESH_TOKEN"],
        "use_proto_plus": True,
    }
    login_customer_id = os.environ.get("GADS_LOGIN_CUSTOMER_ID")
    if login_customer_id:
        config["login_customer_id"] = login_customer_id.replace("-", "")
    return GoogleAdsClient.load_from_dict(config)


def _require_sa_key() -> None:
    path = os.environ.get("GOOGLE_APPLICATION_CREDENTIALS")
    if not path or not os.path.exists(path):
        raise CredentialsError(
            "GOOGLE_APPLICATION_CREDENTIALS is not set or the key file is "
            "missing on the engine. Populate /opt/elbrus/adengine.env and the "
            "service-account key, then restart adengine."
        )


@lru_cache(maxsize=1)
def ga4_data_client():
    _require_sa_key()
    from google.analytics.data_v1beta import BetaAnalyticsDataClient

    return BetaAnalyticsDataClient()


@lru_cache(maxsize=1)
def ga4_admin_client():
    _require_sa_key()
    from google.analytics.admin_v1beta import AnalyticsAdminServiceClient

    return AnalyticsAdminServiceClient()


@lru_cache(maxsize=1)
def gsc_service():
    _require_sa_key()
    from google.oauth2 import service_account
    from googleapiclient.discovery import build

    credentials = service_account.Credentials.from_service_account_file(
        os.environ["GOOGLE_APPLICATION_CREDENTIALS"],
        scopes=["https://www.googleapis.com/auth/webmasters"],
    )
    return build("searchconsole", "v1", credentials=credentials,
                 cache_discovery=False)
