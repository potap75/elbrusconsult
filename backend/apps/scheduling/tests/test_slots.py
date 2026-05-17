"""Tests for the slot generation service."""
from __future__ import annotations

from datetime import date, datetime, timedelta, timezone
from zoneinfo import ZoneInfo

import pytest
from django.test import override_settings

from scheduling.models import AvailabilityException
from scheduling.services.slots import generate_slots, slot_is_available

from .conftest import et_at, make_booking


@pytest.mark.django_db
@override_settings(
    SCHEDULING_TIMEZONE="America/New_York",
    SCHEDULING_MIN_LEAD_MINUTES=0,
    SCHEDULING_MAX_LEAD_DAYS=365,
    SCHEDULING_SLOT_GRANULARITY_MINUTES=30,
)
def test_basic_window_slices_into_30min_slots(
    discovery_call, weekday_business_hours, far_future_now
):
    monday = date(2026, 6, 1)
    slots = generate_slots(discovery_call, monday, monday, now=far_future_now)
    assert len(slots) == 16
    assert slots[0] == et_at(monday, 9, 0)
    assert slots[-1] == et_at(monday, 16, 30)


@pytest.mark.django_db
@override_settings(
    SCHEDULING_TIMEZONE="America/New_York",
    SCHEDULING_MIN_LEAD_MINUTES=0,
    SCHEDULING_MAX_LEAD_DAYS=365,
    SCHEDULING_SLOT_GRANULARITY_MINUTES=15,
)
def test_60min_appointment_fits_fully_in_window(
    deep_dive, weekday_business_hours, far_future_now
):
    monday = date(2026, 6, 1)
    slots = generate_slots(deep_dive, monday, monday, now=far_future_now)
    assert slots[0] == et_at(monday, 9, 0)
    last_start = slots[-1]
    assert last_start + timedelta(minutes=60) <= et_at(monday, 17, 0)


@pytest.mark.django_db
@override_settings(
    SCHEDULING_TIMEZONE="America/New_York",
    SCHEDULING_MIN_LEAD_MINUTES=0,
    SCHEDULING_MAX_LEAD_DAYS=365,
    SCHEDULING_SLOT_GRANULARITY_MINUTES=30,
)
def test_weekend_days_have_no_slots(
    discovery_call, weekday_business_hours, far_future_now
):
    saturday = date(2026, 6, 6)
    slots = generate_slots(discovery_call, saturday, saturday, now=far_future_now)
    assert slots == []


@pytest.mark.django_db
@override_settings(
    SCHEDULING_TIMEZONE="America/New_York",
    SCHEDULING_MIN_LEAD_MINUTES=0,
    SCHEDULING_MAX_LEAD_DAYS=365,
    SCHEDULING_SLOT_GRANULARITY_MINUTES=30,
)
def test_existing_booking_blocks_overlapping_slots(
    discovery_call, weekday_business_hours, far_future_now
):
    monday = date(2026, 6, 1)
    make_booking(discovery_call, et_at(monday, 10, 0))
    slots = generate_slots(discovery_call, monday, monday, now=far_future_now)
    # The 10:00-10:30 booking blocks any 30-min start that overlaps it.
    assert et_at(monday, 10, 0) not in slots
    # 9:30 ends exactly at 10:00 (exclusive end) - still available.
    assert et_at(monday, 9, 30) in slots
    # 10:30 starts exactly when the booking ends - available.
    assert et_at(monday, 10, 30) in slots


@pytest.mark.django_db
@override_settings(
    SCHEDULING_TIMEZONE="America/New_York",
    SCHEDULING_MIN_LEAD_MINUTES=0,
    SCHEDULING_MAX_LEAD_DAYS=365,
    SCHEDULING_SLOT_GRANULARITY_MINUTES=30,
)
def test_buffer_after_extends_block_window(
    deep_dive, weekday_business_hours, far_future_now
):
    """deep_dive has buffer_after_minutes=15; a booking ending at 10:00 should
    block at least until 10:15."""
    monday = date(2026, 6, 1)
    make_booking(deep_dive, et_at(monday, 9, 0))  # 9:00-10:00 with +15min buffer
    slots = generate_slots(deep_dive, monday, monday, now=far_future_now)
    assert et_at(monday, 9, 0) not in slots
    assert et_at(monday, 10, 0) not in slots
    assert et_at(monday, 10, 30) in slots


@pytest.mark.django_db
@override_settings(
    SCHEDULING_TIMEZONE="America/New_York",
    SCHEDULING_MIN_LEAD_MINUTES=0,
    SCHEDULING_MAX_LEAD_DAYS=365,
    SCHEDULING_SLOT_GRANULARITY_MINUTES=30,
)
def test_availability_exception_removes_window(
    discovery_call, weekday_business_hours, far_future_now
):
    monday = date(2026, 6, 1)
    AvailabilityException.objects.create(
        start_at=et_at(monday, 12, 0),
        end_at=et_at(monday, 14, 0),
        reason="Team lunch",
    )
    slots = generate_slots(discovery_call, monday, monday, now=far_future_now)
    assert et_at(monday, 12, 0) not in slots
    assert et_at(monday, 13, 0) not in slots
    assert et_at(monday, 13, 30) not in slots
    assert et_at(monday, 11, 30) in slots
    assert et_at(monday, 14, 0) in slots


@pytest.mark.django_db
@override_settings(
    SCHEDULING_TIMEZONE="America/New_York",
    SCHEDULING_MIN_LEAD_MINUTES=120,
    SCHEDULING_MAX_LEAD_DAYS=365,
    SCHEDULING_SLOT_GRANULARITY_MINUTES=30,
)
def test_min_lead_time_filters_near_slots(
    discovery_call, weekday_business_hours
):
    monday = date(2026, 6, 1)
    now = et_at(monday, 9, 0)  # exactly when business hours open
    slots = generate_slots(discovery_call, monday, monday, now=now)
    assert et_at(monday, 9, 0) not in slots
    assert et_at(monday, 10, 30) not in slots
    assert et_at(monday, 11, 0) in slots


@pytest.mark.django_db
@override_settings(
    SCHEDULING_TIMEZONE="America/New_York",
    SCHEDULING_MIN_LEAD_MINUTES=0,
    SCHEDULING_MAX_LEAD_DAYS=2,
    SCHEDULING_SLOT_GRANULARITY_MINUTES=30,
)
def test_max_lead_days_filters_far_slots(
    discovery_call, weekday_business_hours
):
    monday = date(2026, 6, 1)
    now = et_at(monday, 8, 0)
    far_monday = monday + timedelta(days=7)
    slots = generate_slots(discovery_call, monday, far_monday, now=now)
    assert any(s.date() == monday for s in slots)
    assert all(s <= now + timedelta(days=2) for s in slots)


@pytest.mark.django_db
@override_settings(
    SCHEDULING_TIMEZONE="America/New_York",
    SCHEDULING_MIN_LEAD_MINUTES=0,
    SCHEDULING_MAX_LEAD_DAYS=365,
    SCHEDULING_SLOT_GRANULARITY_MINUTES=30,
)
def test_inactive_appointment_type_has_no_slots(
    discovery_call, weekday_business_hours, far_future_now
):
    discovery_call.is_active = False
    discovery_call.save()
    monday = date(2026, 6, 1)
    assert generate_slots(discovery_call, monday, monday, now=far_future_now) == []


@pytest.mark.django_db
@override_settings(
    SCHEDULING_TIMEZONE="America/New_York",
    SCHEDULING_MIN_LEAD_MINUTES=0,
    SCHEDULING_MAX_LEAD_DAYS=365,
    SCHEDULING_SLOT_GRANULARITY_MINUTES=30,
)
def test_ignore_booking_ids_treats_slot_as_free(
    discovery_call, weekday_business_hours, far_future_now
):
    """For reschedule flows, the original booking's slot should be available."""
    monday = date(2026, 6, 1)
    booking = make_booking(discovery_call, et_at(monday, 10, 0))
    slots_default = generate_slots(discovery_call, monday, monday, now=far_future_now)
    slots_ignored = generate_slots(
        discovery_call,
        monday,
        monday,
        now=far_future_now,
        ignore_booking_ids=[booking.id],
    )
    assert et_at(monday, 10, 0) not in slots_default
    assert et_at(monday, 10, 0) in slots_ignored


@pytest.mark.django_db
@override_settings(
    SCHEDULING_TIMEZONE="America/New_York",
    SCHEDULING_MIN_LEAD_MINUTES=0,
    SCHEDULING_MAX_LEAD_DAYS=365,
    SCHEDULING_SLOT_GRANULARITY_MINUTES=30,
)
def test_dst_transition_spring_forward(discovery_call, weekday_business_hours):
    """On the second Sunday of March, ET shifts from EST(UTC-5) to EDT(UTC-4).
    Pick the Monday after to confirm we still report 9 AM ET as the first slot."""
    spring_forward_monday = date(2026, 3, 9)
    now = datetime(2026, 3, 1, 12, 0, tzinfo=timezone.utc)
    slots = generate_slots(
        discovery_call, spring_forward_monday, spring_forward_monday, now=now
    )
    expected_first = datetime(2026, 3, 9, 9, 0, tzinfo=ZoneInfo("America/New_York"))
    assert slots[0] == expected_first.astimezone(timezone.utc)


@pytest.mark.django_db
@override_settings(
    SCHEDULING_TIMEZONE="America/New_York",
    SCHEDULING_MIN_LEAD_MINUTES=0,
    SCHEDULING_MAX_LEAD_DAYS=365,
    SCHEDULING_SLOT_GRANULARITY_MINUTES=30,
)
def test_slot_is_available(discovery_call, weekday_business_hours, far_future_now):
    monday = date(2026, 6, 1)
    assert slot_is_available(discovery_call, et_at(monday, 10, 0), now=far_future_now)
    # Off-grid times aren't valid:
    assert not slot_is_available(discovery_call, et_at(monday, 10, 15), now=far_future_now)
    # Weekend isn't valid:
    saturday = date(2026, 6, 6)
    assert not slot_is_available(discovery_call, et_at(saturday, 10, 0), now=far_future_now)
