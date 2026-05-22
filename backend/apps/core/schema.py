"""Helpers to build schema.org JSON-LD payloads."""
from __future__ import annotations

from django.conf import settings


def organization_schema() -> dict:
    """Site-wide Organization payload."""
    payload: dict = {
        "@context": "https://schema.org",
        "@type": "Organization",
        "name": settings.SITE_NAME,
        "url": settings.SITE_URL,
        "logo": f"{settings.SITE_URL}/static/img/logo.png",
        "description": settings.SITE_TAGLINE,
        "email": settings.INFO_EMAIL,
        "sameAs": [],
    }
    if settings.SITE_ADVISORY_PHONE:
        payload["telephone"] = settings.SITE_ADVISORY_PHONE
    return payload


def website_schema() -> dict:
    """WebSite payload, includes a SearchAction for blog search."""
    return {
        "@context": "https://schema.org",
        "@type": "WebSite",
        "name": settings.SITE_NAME,
        "url": settings.SITE_URL,
        "potentialAction": {
            "@type": "SearchAction",
            "target": f"{settings.SITE_URL}/blog/?q={{search_term_string}}",
            "query-input": "required name=search_term_string",
        },
    }


def breadcrumb_schema(items: list[dict[str, str]]) -> dict | None:
    """Build a BreadcrumbList from ``[{'name': ..., 'url': ...}, ...]``.

    URLs may be absolute or relative; relative paths are resolved against
    ``SITE_URL``.
    """
    if not items:
        return None
    list_items = []
    for index, item in enumerate(items, start=1):
        url = item["url"]
        if url.startswith("/"):
            url = f"{settings.SITE_URL}{url}"
        list_items.append(
            {
                "@type": "ListItem",
                "position": index,
                "name": item["name"],
                "item": url,
            }
        )
    return {
        "@context": "https://schema.org",
        "@type": "BreadcrumbList",
        "itemListElement": list_items,
    }
