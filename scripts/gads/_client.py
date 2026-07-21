"""Builds an authenticated GoogleAdsClient for the write CLI.

Credential resolution order for each value:
  1. Environment variable (GADS_*).
  2. Azure Key Vault via the `az` CLI, when GADS_KV_VAULT is set.

Required values:
  developer_token   GADS_DEVELOPER_TOKEN   / KV secret google-ads-developer-token
  client_id         GADS_CLIENT_ID         / KV secret google-ads-oauth-client-id
  client_secret     GADS_CLIENT_SECRET     / KV secret google-ads-oauth-client-secret
  refresh_token     GADS_REFRESH_TOKEN     / KV secret google-ads-oauth-refresh-token
Optional:
  login_customer_id GADS_LOGIN_CUSTOMER_ID (only for manager-account access)
"""

from __future__ import annotations

import os
import subprocess
import sys

_KV_SECRET_NAMES = {
    "developer_token": "google-ads-developer-token",
    "client_id": "google-ads-oauth-client-id",
    "client_secret": "google-ads-oauth-client-secret",
    "refresh_token": "google-ads-oauth-refresh-token",
}


def _from_key_vault(secret_name: str) -> str | None:
    vault = os.environ.get("GADS_KV_VAULT")
    if not vault:
        return None
    try:
        out = subprocess.run(
            [
                "az", "keyvault", "secret", "show",
                "--vault-name", vault,
                "--name", secret_name,
                "--query", "value",
                "-o", "tsv",
            ],
            capture_output=True,
            text=True,
            timeout=30,
        )
    except (OSError, subprocess.TimeoutExpired):
        return None
    if out.returncode != 0:
        return None
    value = out.stdout.strip()
    return value or None


def _resolve(key: str) -> str:
    env_var = f"GADS_{key.upper()}"
    value = os.environ.get(env_var) or _from_key_vault(_KV_SECRET_NAMES[key])
    if not value:
        sys.exit(
            f"Missing Google Ads credential '{key}'. Set {env_var} or set "
            f"GADS_KV_VAULT and store Key Vault secret "
            f"'{_KV_SECRET_NAMES[key]}' (requires `az login`)."
        )
    return value


def build_client():
    from google.ads.googleads.client import GoogleAdsClient

    config = {
        "developer_token": _resolve("developer_token"),
        "client_id": _resolve("client_id"),
        "client_secret": _resolve("client_secret"),
        "refresh_token": _resolve("refresh_token"),
        "use_proto_plus": True,
    }
    login_customer_id = os.environ.get("GADS_LOGIN_CUSTOMER_ID")
    if login_customer_id:
        config["login_customer_id"] = login_customer_id.replace("-", "")
    return GoogleAdsClient.load_from_dict(config)
