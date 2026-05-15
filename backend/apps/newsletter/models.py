"""Newsletter subscriber model + double opt-in token helpers."""
from __future__ import annotations

import secrets

from django.db import models


def generate_token() -> str:
    return secrets.token_urlsafe(32)


class Subscriber(models.Model):
    email = models.EmailField(unique=True)
    token = models.CharField(max_length=64, unique=True, default=generate_token)
    confirmed_at = models.DateTimeField(null=True, blank=True)
    unsubscribed_at = models.DateTimeField(null=True, blank=True)
    source = models.CharField(
        max_length=80,
        blank=True,
        help_text="Where the signup came from (e.g. footer, /newsletter/).",
    )
    ip_address = models.GenericIPAddressField(null=True, blank=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self) -> str:
        return self.email

    @property
    def is_confirmed(self) -> bool:
        return self.confirmed_at is not None and self.unsubscribed_at is None

    @property
    def status(self) -> str:
        if self.unsubscribed_at:
            return "unsubscribed"
        if self.confirmed_at:
            return "confirmed"
        return "pending"
