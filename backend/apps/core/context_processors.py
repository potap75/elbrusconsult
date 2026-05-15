"""Inject site-wide values (name, URLs, default SEO) into every template."""
from __future__ import annotations

from django.conf import settings
from django.http import HttpRequest

from .schema import organization_schema, website_schema


def site_context(request: HttpRequest) -> dict:
    canonical_path = request.path
    canonical_url = f"{settings.SITE_URL}{canonical_path}"

    return {
        "SITE_NAME": settings.SITE_NAME,
        "SITE_TAGLINE": settings.SITE_TAGLINE,
        "SITE_DOMAIN": settings.SITE_DOMAIN,
        "SITE_URL": settings.SITE_URL,
        "SITE_DEFAULT_OG_IMAGE": settings.SITE_DEFAULT_OG_IMAGE,
        "SITE_TWITTER_HANDLE": settings.SITE_TWITTER_HANDLE,
        "INFO_EMAIL": settings.INFO_EMAIL,
        "default_canonical_url": canonical_url,
        "organization_schema": organization_schema(),
        "website_schema": website_schema(),
    }
