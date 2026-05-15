"""Reusable SEO mixin for class-based views.

Subclasses set the class attributes ``seo_title`` / ``seo_description`` /
``seo_robots`` (or override ``get_seo_*`` for dynamic values). The values are
injected into the template context where ``base.html`` consumes them.
"""
from __future__ import annotations

from typing import Any

from django.conf import settings


class SeoMixin:
    seo_title: str | None = None
    seo_description: str | None = None
    seo_robots: str = "index,follow"
    seo_og_type: str = "website"
    seo_og_image: str | None = None
    seo_canonical_path: str | None = None

    def get_seo_title(self) -> str:
        return self.seo_title or settings.SITE_NAME

    def get_seo_description(self) -> str:
        return self.seo_description or settings.SITE_TAGLINE

    def get_seo_robots(self) -> str:
        return self.seo_robots

    def get_seo_og_type(self) -> str:
        return self.seo_og_type

    def get_seo_og_image(self) -> str:
        return self.seo_og_image or settings.SITE_DEFAULT_OG_IMAGE

    def get_seo_canonical_path(self) -> str:
        if self.seo_canonical_path is not None:
            return self.seo_canonical_path
        request = getattr(self, "request", None)
        return request.path if request is not None else "/"

    def get_breadcrumbs(self) -> list[dict[str, str]]:
        """Override to provide breadcrumb data for BreadcrumbList JSON-LD."""
        return []

    def get_context_data(self, **kwargs: Any) -> dict[str, Any]:
        context = super().get_context_data(**kwargs)  # type: ignore[misc]
        canonical_path = self.get_seo_canonical_path()
        context.update(
            {
                "seo_title": self.get_seo_title(),
                "seo_description": self.get_seo_description(),
                "seo_robots": self.get_seo_robots(),
                "seo_og_type": self.get_seo_og_type(),
                "seo_og_image": self.get_seo_og_image(),
                "seo_canonical_path": canonical_path,
                "seo_canonical_url": f"{settings.SITE_URL}{canonical_path}",
                "breadcrumbs": self.get_breadcrumbs(),
            }
        )
        return context
