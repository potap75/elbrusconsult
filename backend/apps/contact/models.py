from __future__ import annotations

from django.db import models


class ContactMessage(models.Model):
    name = models.CharField(max_length=120)
    email = models.EmailField()
    company = models.CharField(max_length=120, blank=True)
    subject = models.CharField(max_length=180, blank=True)
    message = models.TextField()

    submitted_at = models.DateTimeField(auto_now_add=True)
    ip_address = models.GenericIPAddressField(null=True, blank=True)
    user_agent = models.CharField(max_length=500, blank=True)

    # Marketing attribution snapshot. PII-light: UTMs + paid-channel click
    # IDs + landing page + cross-origin referrer captured by
    # ``core.middleware.AttributionMiddleware`` and merged via
    # ``core.attribution.get_attribution_snapshot()``. Shape:
    #     {"first_touch": {...}, "last_touch": {...}, "current": {...},
    #      "captured_at": "<iso>"}
    attribution = models.JSONField(default=dict, blank=True)

    handled = models.BooleanField(default=False)
    notes = models.TextField(blank=True)

    class Meta:
        ordering = ["-submitted_at"]

    def __str__(self) -> str:
        return f"{self.name} <{self.email}> at {self.submitted_at:%Y-%m-%d %H:%M}"
