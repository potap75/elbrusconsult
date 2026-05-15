"""Sitemap for static (non-model) views."""
from __future__ import annotations

from django.contrib.sitemaps import Sitemap
from django.urls import reverse


class StaticViewSitemap(Sitemap):
    """Sitemap of stable, model-less URLs.

    Detail pages backed by models (services, blog posts) live in their own
    sitemaps under their respective apps.
    """

    changefreq = "weekly"
    priority = 0.8
    protocol = "https"

    def items(self) -> list[str]:
        return [
            "home",
            "about",
            "services-list",
            "blog-list",
            "contact",
            "newsletter-subscribe",
            "schedule",
        ]

    def location(self, item: str) -> str:
        return reverse(item)
