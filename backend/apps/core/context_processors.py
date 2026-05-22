"""Inject site-wide values (name, URLs, default SEO, analytics IDs) into every template."""
from __future__ import annotations

from django.conf import settings
from django.http import HttpRequest

from .schema import organization_schema, website_schema
from .utils import phone_tel_uri


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
        "SITE_ADVISORY_PHONE": settings.SITE_ADVISORY_PHONE,
        "SITE_ADVISORY_PHONE_TEL": phone_tel_uri(settings.SITE_ADVISORY_PHONE),
        "default_canonical_url": canonical_url,
        "organization_schema": organization_schema(),
        "website_schema": website_schema(),
    }


def analytics_context(request: HttpRequest) -> dict:
    """Expose analytics + paid-channel IDs to templates.

    Every value is a plain string. The analytics partial only renders a tag
    when its value is truthy, so an unset env var means zero third-party
    requests. Lives in its own context processor (rather than ``site_context``)
    so it's trivial to disable in tests via override_settings or by removing
    the processor entirely.
    """
    return {
        "GTM_CONTAINER_ID": settings.GTM_CONTAINER_ID,
        "GA4_MEASUREMENT_ID": settings.GA4_MEASUREMENT_ID,
        "GOOGLE_ADS_CONVERSION_ID": settings.GOOGLE_ADS_CONVERSION_ID,
        "LINKEDIN_PARTNER_ID": settings.LINKEDIN_PARTNER_ID,
        "META_PIXEL_ID": settings.META_PIXEL_ID,
        "BING_UET_TAG_ID": settings.BING_UET_TAG_ID,
        "TIKTOK_PIXEL_ID": settings.TIKTOK_PIXEL_ID,
        "GOOGLE_SITE_VERIFICATION": settings.GOOGLE_SITE_VERIFICATION,
        "BING_SITE_VERIFICATION": settings.BING_SITE_VERIFICATION,
        "CONSENT_DEFAULT_GRANTED": settings.CONSENT_DEFAULT_GRANTED,
        "CONSENT_DEFAULT_DENY_REGIONS": settings.CONSENT_DEFAULT_DENY_REGIONS,
        # CSP nonce attached by SecurityHeadersMiddleware. Templates read it
        # via the {% csp_nonce %} tag, but we also expose the raw value so
        # custom partials can render `nonce="{{ csp_nonce }}"` directly.
        "csp_nonce": getattr(request, "csp_nonce", ""),
    }
