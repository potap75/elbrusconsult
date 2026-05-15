"""Scheduling models.

For the moment this is a lead-capture model only - it stores prospective
bookings so we can follow up manually. When real availability/booking logic
ships, additional models (e.g. ``StaffAvailability``, ``Booking``) will join
this one without changing the placeholder page or its API contract.
"""
from __future__ import annotations

from django.conf import settings
from django.db import models


class BookingInquiry(models.Model):
    name = models.CharField(max_length=120)
    email = models.EmailField()
    company = models.CharField(max_length=120, blank=True)
    phone = models.CharField(max_length=40, blank=True)

    service = models.ForeignKey(
        "pages.Service",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="booking_inquiries",
    )
    preferred_date = models.DateField(null=True, blank=True)
    timezone_label = models.CharField(
        max_length=80,
        blank=True,
        help_text="Free-form timezone label from the client (e.g. America/New_York).",
    )
    notes = models.TextField(blank=True)

    handled = models.BooleanField(default=False)
    ip_address = models.GenericIPAddressField(null=True, blank=True)
    user_agent = models.CharField(max_length=500, blank=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-created_at"]
        verbose_name = "Booking inquiry"
        verbose_name_plural = "Booking inquiries"

    def __str__(self) -> str:
        svc = self.service.name if self.service_id else "general"
        return f"{self.name} <{self.email}> - {svc}"
