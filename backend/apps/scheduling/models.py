"""Scheduling models.

Two parallel paths live here:

* ``BookingInquiry`` (legacy): a lead-capture form used when the customer
  doesn't want to pick a specific time. Kept for backward compatibility.
* ``AppointmentType`` + ``AvailabilityRule`` + ``AvailabilityException``
  + ``Booking``: the real booking calendar. Customers pick an appointment
  type, then a slot, and a confirmed ``Booking`` is created.
"""
from __future__ import annotations

import uuid

from django.db import models
from django.urls import reverse
from django.utils.text import slugify


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


class AppointmentType(models.Model):
    """A bookable kind of meeting (e.g. 30-min discovery call).

    Independent of ``Service``: customers can optionally tell us which service
    area they want to discuss on the booking form, but the duration / cadence
    is driven by the appointment type alone.
    """

    name = models.CharField(max_length=120, unique=True)
    slug = models.SlugField(max_length=140, unique=True, blank=True)
    duration_minutes = models.PositiveSmallIntegerField(
        default=30,
        help_text="Length of the meeting in minutes.",
    )
    buffer_after_minutes = models.PositiveSmallIntegerField(
        default=0,
        help_text="Padding after the meeting before another can start.",
    )
    description = models.TextField(
        blank=True,
        help_text="Shown on the appointment-type picker.",
    )
    location_instructions = models.CharField(
        max_length=240,
        blank=True,
        help_text=(
            "Free-form text describing how the meeting happens "
            "(e.g. 'We will send a Google Meet link').'"
        ),
    )
    order = models.PositiveSmallIntegerField(default=100)
    is_active = models.BooleanField(default=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["order", "name"]
        verbose_name = "Appointment type"
        verbose_name_plural = "Appointment types"

    def __str__(self) -> str:
        return f"{self.name} ({self.duration_minutes} min)"

    def save(self, *args, **kwargs) -> None:
        if not self.slug:
            self.slug = slugify(self.name)[:140]
        super().save(*args, **kwargs)


class AvailabilityRule(models.Model):
    """A weekly recurring availability window in the company timezone."""

    class Weekday(models.IntegerChoices):
        MONDAY = 0, "Monday"
        TUESDAY = 1, "Tuesday"
        WEDNESDAY = 2, "Wednesday"
        THURSDAY = 3, "Thursday"
        FRIDAY = 4, "Friday"
        SATURDAY = 5, "Saturday"
        SUNDAY = 6, "Sunday"

    weekday = models.PositiveSmallIntegerField(choices=Weekday.choices)
    start_time = models.TimeField()
    end_time = models.TimeField()
    is_active = models.BooleanField(default=True)

    class Meta:
        ordering = ["weekday", "start_time"]
        verbose_name = "Availability rule"
        verbose_name_plural = "Availability rules"

    def __str__(self) -> str:
        return (
            f"{self.get_weekday_display()} "
            f"{self.start_time:%H:%M}-{self.end_time:%H:%M}"
        )


class AvailabilityException(models.Model):
    """A blackout window that subtracts from the weekly availability.

    Stored in UTC. Holidays, days off, full-team workshops, etc.
    """

    start_at = models.DateTimeField()
    end_at = models.DateTimeField()
    reason = models.CharField(max_length=200, blank=True)

    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["start_at"]
        verbose_name = "Availability exception"
        verbose_name_plural = "Availability exceptions"

    def __str__(self) -> str:
        label = self.reason or "blackout"
        return f"{label}: {self.start_at:%Y-%m-%d %H:%M} -> {self.end_at:%Y-%m-%d %H:%M} UTC"


class Booking(models.Model):
    """A concrete confirmed (or pending/cancelled) booking on the calendar."""

    class Status(models.TextChoices):
        PENDING = "pending", "Pending"
        CONFIRMED = "confirmed", "Confirmed"
        CANCELLED = "cancelled", "Cancelled"

    appointment_type = models.ForeignKey(
        AppointmentType,
        on_delete=models.PROTECT,
        related_name="bookings",
    )
    service = models.ForeignKey(
        "pages.Service",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="bookings",
        help_text="Optional consulting area the customer wants to discuss.",
    )

    name = models.CharField(max_length=120)
    email = models.EmailField()
    company = models.CharField(max_length=120, blank=True)
    phone = models.CharField(max_length=40, blank=True)
    notes = models.TextField(blank=True)

    start_at = models.DateTimeField(help_text="UTC start of the meeting.")
    end_at = models.DateTimeField(help_text="UTC end of the meeting (exclusive).")
    customer_timezone = models.CharField(
        max_length=80,
        blank=True,
        help_text="IANA tz the customer booked in (e.g. America/New_York).",
    )

    status = models.CharField(
        max_length=12,
        choices=Status.choices,
        default=Status.CONFIRMED,
    )
    manage_token = models.UUIDField(
        default=uuid.uuid4,
        unique=True,
        editable=False,
        help_text="Opaque token used by the customer manage/cancel page.",
    )
    rescheduled_from = models.ForeignKey(
        "self",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="rescheduled_to",
        help_text="If this booking replaces another, the original it replaced.",
    )

    cancelled_at = models.DateTimeField(null=True, blank=True)
    cancel_reason = models.CharField(max_length=200, blank=True)

    ip_address = models.GenericIPAddressField(null=True, blank=True)
    user_agent = models.CharField(max_length=500, blank=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-start_at"]
        verbose_name = "Booking"
        verbose_name_plural = "Bookings"
        indexes = [
            models.Index(fields=["status", "start_at"]),
            models.Index(fields=["start_at", "end_at"]),
        ]

    def __str__(self) -> str:
        return f"{self.name} - {self.appointment_type.name} @ {self.start_at:%Y-%m-%d %H:%M} UTC"

    @property
    def is_active(self) -> bool:
        return self.status in {self.Status.PENDING, self.Status.CONFIRMED}

    def get_manage_url(self) -> str:
        return reverse("scheduling-manage", kwargs={"token": self.manage_token})

    def get_cancel_url(self) -> str:
        return reverse("scheduling-manage-cancel", kwargs={"token": self.manage_token})

    def get_reschedule_url(self) -> str:
        return f"{reverse('schedule')}?reschedule={self.manage_token}"
