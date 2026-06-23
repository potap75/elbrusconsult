"""Shared fixtures for the scheduling app tests."""
from __future__ import annotations

from datetime import date, datetime, time, timedelta, timezone
from zoneinfo import ZoneInfo

import pytest

from scheduling.models import (
    AppointmentType,
    AvailabilityException,
    AvailabilityRule,
    Booking,
)


@pytest.fixture
def discovery_call(db) -> AppointmentType:
    return AppointmentType.objects.create(
        name="Discovery call",
        slug="discovery-call",
        duration_minutes=30,
        buffer_after_minutes=0,
        description="Free 30-min intro call.",
        location_instructions="Google Meet link emailed after booking.",
        order=10,
        is_active=True,
    )


@pytest.fixture
def deep_dive(db) -> AppointmentType:
    return AppointmentType.objects.create(
        name="Deep dive",
        slug="deep-dive",
        duration_minutes=60,
        buffer_after_minutes=15,
        description="60-min working session.",
        location_instructions="Google Meet link emailed after booking.",
        order=20,
        is_active=True,
    )


@pytest.fixture
def weekday_business_hours(db) -> list[AvailabilityRule]:
    """Mon-Fri 09:00-17:00 in America/New_York."""
    rules = []
    for weekday in range(5):
        rules.append(
            AvailabilityRule.objects.create(
                weekday=weekday,
                start_time=time(9, 0),
                end_time=time(17, 0),
                is_active=True,
            )
        )
    return rules


@pytest.fixture
def reference_now() -> datetime:
    """A fixed UTC 'now' (a Monday at 09:00 ET == 14:00 UTC during DST)."""
    return datetime(2026, 6, 1, 13, 0, tzinfo=timezone.utc)


@pytest.fixture
def far_future_now() -> datetime:
    """A far-future 'now' that won't conflict with the test slot ranges."""
    return datetime(2026, 5, 1, 12, 0, tzinfo=timezone.utc)


def make_booking(
    appointment_type: AppointmentType,
    start_at: datetime,
    *,
    name: str = "Test User",
    email: str = "test@example.com",
    status: str = Booking.Status.CONFIRMED,
) -> Booking:
    end_at = start_at + timedelta(minutes=appointment_type.duration_minutes)
    return Booking.objects.create(
        appointment_type=appointment_type,
        name=name,
        email=email,
        start_at=start_at,
        end_at=end_at,
        status=status,
    )


def et_at(d: date, h: int, m: int = 0) -> datetime:
    """Construct a UTC datetime from a local America/New_York wall time."""
    local = datetime.combine(d, time(h, m), tzinfo=ZoneInfo("America/New_York"))
    return local.astimezone(timezone.utc)


def future_monday(*, offset_weeks: int = 1) -> date:
    """Return a Monday far enough in the future for booking API tests."""
    from django.utils import timezone as dj_tz

    today = dj_tz.localdate()
    days_ahead = (7 - today.weekday()) % 7
    if days_ahead == 0:
        days_ahead = 7
    return today + timedelta(days=days_ahead + 7 * (offset_weeks - 1))
