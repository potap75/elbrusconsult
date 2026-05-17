"""Tests for the server-rendered manage / cancel flow."""
from __future__ import annotations

from datetime import date, datetime, timedelta, timezone

import pytest
from django.core import mail
from django.test import Client, override_settings
from django.urls import reverse

from scheduling.models import Booking

from .conftest import et_at, make_booking


@pytest.mark.django_db
@override_settings(
    SCHEDULING_TIMEZONE="America/New_York",
    SCHEDULING_MIN_LEAD_MINUTES=0,
    SCHEDULING_MAX_LEAD_DAYS=365,
    SCHEDULING_SLOT_GRANULARITY_MINUTES=30,
)
def test_manage_page_renders(discovery_call, weekday_business_hours):
    monday = date(2099, 6, 7)
    booking = make_booking(discovery_call, et_at(monday, 10, 0))
    client = Client()
    resp = client.get(
        reverse("scheduling-manage", kwargs={"token": str(booking.manage_token)})
    )
    assert resp.status_code == 200
    body = resp.content.decode("utf-8")
    assert "Manage your booking" in body
    assert "Cancel booking" in body
    assert 'name="robots" content="noindex,nofollow"' in body


@pytest.mark.django_db
def test_manage_page_404_for_unknown_token():
    client = Client()
    resp = client.get(
        reverse(
            "scheduling-manage",
            kwargs={"token": "00000000-0000-0000-0000-000000000000"},
        )
    )
    assert resp.status_code == 404


@pytest.mark.django_db
@override_settings(
    SCHEDULING_TIMEZONE="America/New_York",
    SCHEDULING_MIN_LEAD_MINUTES=0,
    SCHEDULING_MAX_LEAD_DAYS=365,
    SCHEDULING_SLOT_GRANULARITY_MINUTES=30,
)
def test_cancel_marks_booking_and_sends_email(
    discovery_call, weekday_business_hours
):
    monday = date(2099, 6, 7)
    booking = make_booking(discovery_call, et_at(monday, 10, 0))
    mail.outbox.clear()
    client = Client(enforce_csrf_checks=False)
    resp = client.post(
        reverse(
            "scheduling-manage-cancel", kwargs={"token": str(booking.manage_token)}
        ),
        data={"reason": "Conflict came up"},
    )
    assert resp.status_code == 302
    booking.refresh_from_db()
    assert booking.status == Booking.Status.CANCELLED
    assert booking.cancel_reason == "Conflict came up"
    assert booking.cancelled_at is not None
    assert len(mail.outbox) == 2  # customer + staff
    customer = next(m for m in mail.outbox if m.to == [booking.email])

    def _ics_marks_cancel(att) -> bool:
        if not att[2].startswith("text/calendar"):
            return False
        content = att[1]
        if isinstance(content, bytes):
            return b"METHOD:CANCEL" in content
        return "METHOD:CANCEL" in content

    assert any(_ics_marks_cancel(a) for a in customer.attachments)


@pytest.mark.django_db
def test_cancel_rejects_past_booking(discovery_call):
    past_start = datetime.now(tz=timezone.utc) - timedelta(days=1)
    booking = Booking.objects.create(
        appointment_type=discovery_call,
        name="Past",
        email="past@example.com",
        start_at=past_start,
        end_at=past_start + timedelta(minutes=30),
        status=Booking.Status.CONFIRMED,
    )
    client = Client(enforce_csrf_checks=False)
    resp = client.post(
        reverse(
            "scheduling-manage-cancel", kwargs={"token": str(booking.manage_token)}
        ),
    )
    assert resp.status_code == 404
    booking.refresh_from_db()
    assert booking.status == Booking.Status.CONFIRMED


@pytest.mark.django_db
@override_settings(
    SCHEDULING_TIMEZONE="America/New_York",
    SCHEDULING_MIN_LEAD_MINUTES=0,
    SCHEDULING_MAX_LEAD_DAYS=365,
    SCHEDULING_SLOT_GRANULARITY_MINUTES=30,
)
def test_cancel_only_get_returns_405(discovery_call, weekday_business_hours):
    monday = date(2099, 6, 7)
    booking = make_booking(discovery_call, et_at(monday, 10, 0))
    client = Client()
    resp = client.get(
        reverse(
            "scheduling-manage-cancel", kwargs={"token": str(booking.manage_token)}
        )
    )
    assert resp.status_code == 405
