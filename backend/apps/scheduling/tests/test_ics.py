"""Tests that the ICS payload we attach to emails parses correctly."""
from __future__ import annotations

from datetime import date

import pytest
from icalendar import Calendar

from scheduling.services.email import build_ics

from .conftest import et_at, make_booking


@pytest.mark.django_db
def test_build_ics_request_round_trips(discovery_call, weekday_business_hours):
    monday = date(2099, 6, 7)
    booking = make_booking(discovery_call, et_at(monday, 10, 0))
    raw = build_ics(booking, method="REQUEST", sequence=0)
    cal = Calendar.from_ical(raw)
    assert cal["method"] == "REQUEST"
    events = [c for c in cal.walk() if c.name == "VEVENT"]
    assert len(events) == 1
    event = events[0]
    assert str(event["uid"]).startswith(str(booking.manage_token))
    assert event["dtstart"].dt == booking.start_at
    assert event["dtend"].dt == booking.end_at
    assert "Discovery call" in str(event["summary"])
    assert event["status"] == "CONFIRMED"


@pytest.mark.django_db
def test_build_ics_cancel(discovery_call, weekday_business_hours):
    monday = date(2099, 6, 7)
    booking = make_booking(discovery_call, et_at(monday, 10, 0))
    raw = build_ics(booking, method="CANCEL", sequence=1)
    cal = Calendar.from_ical(raw)
    assert cal["method"] == "CANCEL"
    event = next(c for c in cal.walk() if c.name == "VEVENT")
    assert event["status"] == "CANCELLED"
    assert int(event["sequence"]) == 1


@pytest.mark.django_db
def test_build_ics_includes_manage_link(discovery_call, weekday_business_hours):
    monday = date(2099, 6, 7)
    booking = make_booking(discovery_call, et_at(monday, 10, 0))
    raw = build_ics(booking, method="REQUEST").decode("utf-8")
    assert str(booking.manage_token) in raw
