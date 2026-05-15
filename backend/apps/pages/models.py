"""Models for the static-content pages (Home/About) and the Services catalog."""
from __future__ import annotations

from django.db import models
from django.urls import reverse
from django.utils.text import slugify


class Service(models.Model):
    """A consulting service / area of expertise.

    Mirrors the 8 areas + flagship services from the brand reference doc
    (see md/rc_site_info).
    """

    name = models.CharField(max_length=80, unique=True)
    slug = models.SlugField(max_length=100, unique=True, blank=True)
    tagline = models.CharField(
        max_length=180,
        help_text="One-line value prop shown on service cards.",
    )
    summary = models.TextField(
        help_text="2-3 sentences for the services overview page.",
    )
    body_markdown = models.TextField(
        blank=True,
        help_text="Full markdown content for the service detail page.",
    )
    icon = models.CharField(
        max_length=50,
        blank=True,
        help_text="Heroicon name or symbol (e.g. 'shield-check').",
    )
    order = models.PositiveSmallIntegerField(default=100)
    is_featured = models.BooleanField(
        default=False,
        help_text="Show this service on the Home page.",
    )
    is_published = models.BooleanField(default=True)

    meta_description = models.CharField(max_length=180, blank=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["order", "name"]

    def __str__(self) -> str:
        return self.name

    def save(self, *args, **kwargs) -> None:
        if not self.slug:
            self.slug = slugify(self.name)[:100]
        super().save(*args, **kwargs)

    def get_absolute_url(self) -> str:
        return reverse("service-detail", kwargs={"slug": self.slug})

    @property
    def seo_description(self) -> str:
        return self.meta_description or self.tagline
