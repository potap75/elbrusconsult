"""Tests for the booking calendar HTTP endpoints."""
from __future__ import annotations

import json
from datetime import date

import pytest
from django.core import mail
from django.test import Client, override_settings
from django.urls import reverse

from scheduling.models import Booking

from .conftest import et_at


def _post_booking(client: Client, payload: dict) -> "object":
    return client.post(
        reverse("scheduling-api-bookings"),
        data=json.dumps(payload),
        content_type="application/json",
    )


@pytest.mark.django_db
@override_settings(
    SCHEDULING_TIMEZONE="America/New_York",
    SCHEDULING_MIN_LEAD_MINUTES=0,
    SCHEDULING_MAX_LEAD_DAYS=365,
    SCHEDULING_SLOT_GRANULARITY_MINUTES=30,
)
def test_appointment_types_endpoint_lists_active(
    discovery_call, deep_dive, weekday_business_hours
):
    deep_dive.is_active = False
    deep_dive.save()
    client = Client()
    resp = client.get(reverse("scheduling-api-appointment-types"))
    assert resp.status_code == 200
    slugs = [t["slug"] for t in resp.json()["appointment_types"]]
    assert "discovery-call" in slugs
    assert "deep-dive" not in slugs


@pytest.mark.django_db
@override_settings(
    SCHEDULING_TIMEZONE="America/New_York",
    SCHEDULING_MIN_LEAD_MINUTES=0,
    SCHEDULING_MAX_LEAD_DAYS=365,
    SCHEDULING_SLOT_GRANULARITY_MINUTES=30,
)
def test_slots_endpoint_returns_iso_strings(
    discovery_call, weekday_business_hours
):
    client = Client()
    monday = date(2026, 6, 8)
    resp = client.get(
        reverse("scheduling-api-slots"),
        {"type": "discovery-call", "from": str(monday), "to": str(monday)},
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["appointment_type"]["slug"] == "discovery-call"
    assert len(body["slots"]) > 0
    assert all(s.endswith("Z") for s in body["slots"])


@pytest.mark.django_db
def test_slots_endpoint_requires_params():
    client = Client()
    resp = client.get(reverse("scheduling-api-slots"))
    assert resp.status_code == 400


@pytest.mark.django_db
@override_settings(
    SCHEDULING_TIMEZONE="America/New_York",
    SCHEDULING_MIN_LEAD_MINUTES=0,
    SCHEDULING_MAX_LEAD_DAYS=365,
    SCHEDULING_SLOT_GRANULARITY_MINUTES=30,
)
def test_create_booking_happy_path(discovery_call, weekday_business_hours):
    mail.outbox.clear()
    client = Client(enforce_csrf_checks=False)
    monday = date(2026, 6, 8)
    start = et_at(monday, 10, 0)
    resp = _post_booking(
        client,
        {
            "appointment_type": "discovery-call",
            "start_at": start.isoformat().replace("+00:00", "Z"),
            "name": "Jane Doe",
            "email": "jane@example.com",
            "company": "Acme",
            "phone": "555-1234",
            "notes": "Quick chat",
            "customer_timezone": "America/New_York",
        },
    )
    assert resp.status_code == 200, resp.content
    body = resp.json()
    assert body["ok"] is True
    assert body["manage_url"].startswith("/schedule/manage/")
    booking = Booking.objects.get(id=body["id"])
    assert booking.status == Booking.Status.CONFIRMED
    assert booking.start_at == start
    assert len(mail.outbox) == 2  # customer + staff
    assert any(m.to == ["jane@example.com"] for m in mail.outbox)


@pytest.mark.django_db
@override_settings(
    SCHEDULING_TIMEZONE="America/New_York",
    SCHEDULING_MIN_LEAD_MINUTES=0,
    SCHEDULING_MAX_LEAD_DAYS=365,
    SCHEDULING_SLOT_GRANULARITY_MINUTES=30,
)
def test_double_booking_returns_409(discovery_call, weekday_business_hours):
    client = Client(enforce_csrf_checks=False)
    monday = date(2026, 6, 8)
    start = et_at(monday, 11, 0)
    payload = {
        "appointment_type": "discovery-call",
        "start_at": start.isoformat().replace("+00:00", "Z"),
        "name": "First",
        "email": "first@example.com",
        "customer_timezone": "UTC",
    }
    first = _post_booking(client, payload)
    assert first.status_code == 200
    second = _post_booking(
        client,
        {**payload, "name": "Second", "email": "second@example.com"},
    )
    assert second.status_code == 409
    assert second.json()["error"] == "slot_unavailable"
    assert Booking.objects.count() == 1


@pytest.mark.django_db
@override_settings(
    SCHEDULING_TIMEZONE="America/New_York",
    SCHEDULING_MIN_LEAD_MINUTES=0,
    SCHEDULING_MAX_LEAD_DAYS=365,
    SCHEDULING_SLOT_GRANULARITY_MINUTES=30,
)
def test_tampered_start_at_is_rejected(discovery_call, weekday_business_hours):
    """A start_at that doesn't align with the slot grid (e.g. 10:17) is rejected."""
    client = Client(enforce_csrf_checks=False)
    monday = date(2026, 6, 8)
    bogus = et_at(monday, 10, 17)
    resp = _post_booking(
        client,
        {
            "appointment_type": "discovery-call",
            "start_at": bogus.isoformat().replace("+00:00", "Z"),
            "name": "Sneaky",
            "email": "sneaky@example.com",
            "customer_timezone": "UTC",
        },
    )
    assert resp.status_code == 409
    assert Booking.objects.count() == 0


@pytest.mark.django_db
@override_settings(
    SCHEDULING_TIMEZONE="America/New_York",
    SCHEDULING_MIN_LEAD_MINUTES=0,
    SCHEDULING_MAX_LEAD_DAYS=365,
    SCHEDULING_SLOT_GRANULARITY_MINUTES=30,
)
def test_weekend_booking_is_rejected(discovery_call, weekday_business_hours):
    client = Client(enforce_csrf_checks=False)
    saturday = date(2026, 6, 6)
    resp = _post_booking(
        client,
        {
            "appointment_type": "discovery-call",
            "start_at": et_at(saturday, 10, 0).isoformat().replace("+00:00", "Z"),
            "name": "Weekender",
            "email": "weekend@example.com",
            "customer_timezone": "UTC",
        },
    )
    assert resp.status_code == 409


@pytest.mark.django_db
@override_settings(
    SCHEDULING_TIMEZONE="America/New_York",
    SCHEDULING_MIN_LEAD_MINUTES=0,
    SCHEDULING_MAX_LEAD_DAYS=365,
    SCHEDULING_SLOT_GRANULARITY_MINUTES=30,
)
def test_invalid_payload_returns_400(discovery_call, weekday_business_hours):
    client = Client(enforce_csrf_checks=False)
    resp = _post_booking(client, {"appointment_type": "discovery-call"})
    assert resp.status_code == 400
    body = resp.json()
    assert body["error"] == "validation_error"
    assert "name" in body["fields"]
    assert "email" in body["fields"]


@pytest.mark.django_db
@override_settings(
    SCHEDULING_TIMEZONE="America/New_York",
    SCHEDULING_MIN_LEAD_MINUTES=0,
    SCHEDULING_MAX_LEAD_DAYS=365,
    SCHEDULING_SLOT_GRANULARITY_MINUTES=30,
)
def test_reschedule_cancels_original_and_creates_new(
    discovery_call, weekday_business_hours
):
    client = Client(enforce_csrf_checks=False)
    monday = date(2026, 6, 8)
    start = et_at(monday, 10, 0)
    first = _post_booking(
        client,
        {
            "appointment_type": "discovery-call",
            "start_at": start.isoformat().replace("+00:00", "Z"),
            "name": "Jane",
            "email": "jane@example.com",
            "customer_timezone": "UTC",
        },
    )
    assert first.status_code == 200
    token = first.json()["manage_token"]

    new_start = et_at(monday, 14, 0)
    mail.outbox.clear()
    resp = _post_booking(
        client,
        {
            "appointment_type": "discovery-call",
            "start_at": new_start.isoformat().replace("+00:00", "Z"),
            "name": "Jane",
            "email": "jane@example.com",
            "customer_timezone": "UTC",
            "reschedule_token": token,
        },
    )
    assert resp.status_code == 200, resp.content
    original = Booking.objects.get(manage_token=token)
    assert original.status == Booking.Status.CANCELLED
    new_booking = Booking.objects.get(id=resp.json()["id"])
    assert new_booking.start_at == new_start
    assert new_booking.rescheduled_from_id == original.id


@pytest.mark.django_db
@override_settings(
    SCHEDULING_TIMEZONE="America/New_York",
    SCHEDULING_MIN_LEAD_MINUTES=0,
    SCHEDULING_MAX_LEAD_DAYS=365,
    SCHEDULING_SLOT_GRANULARITY_MINUTES=30,
)
def test_slots_endpoint_with_reschedule_token_treats_original_as_free(
    discovery_call, weekday_business_hours
):
    client = Client(enforce_csrf_checks=False)
    monday = date(2026, 6, 8)
    start = et_at(monday, 10, 0)
    first = _post_booking(
        client,
        {
            "appointment_type": "discovery-call",
            "start_at": start.isoformat().replace("+00:00", "Z"),
            "name": "Jane",
            "email": "jane@example.com",
            "customer_timezone": "UTC",
        },
    )
    token = first.json()["manage_token"]

    resp_default = client.get(
        reverse("scheduling-api-slots"),
        {"type": "discovery-call", "from": str(monday), "to": str(monday)},
    )
    resp_with_token = client.get(
        reverse("scheduling-api-slots"),
        {
            "type": "discovery-call",
            "from": str(monday),
            "to": str(monday),
            "reschedule": token,
        },
    )

    iso_slot = start.isoformat().replace("+00:00", "Z")
    assert iso_slot not in resp_default.json()["slots"]
    assert iso_slot in resp_with_token.json()["slots"]


@pytest.mark.django_db
@override_settings(
    SCHEDULING_TIMEZONE="America/New_York",
    SCHEDULING_MIN_LEAD_MINUTES=0,
    SCHEDULING_MAX_LEAD_DAYS=365,
    SCHEDULING_SLOT_GRANULARITY_MINUTES=30,
)
def test_booking_lookup_endpoint(discovery_call, weekday_business_hours):
    client = Client(enforce_csrf_checks=False)
    monday = date(2026, 6, 8)
    start = et_at(monday, 10, 0)
    first = _post_booking(
        client,
        {
            "appointment_type": "discovery-call",
            "start_at": start.isoformat().replace("+00:00", "Z"),
            "name": "Jane",
            "email": "jane@example.com",
            "customer_timezone": "America/New_York",
        },
    )
    token = first.json()["manage_token"]
    resp = client.get(
        reverse("scheduling-api-booking-lookup"), {"token": token}
    )
    assert resp.status_code == 200
    booking = resp.json()["booking"]
    assert booking["appointment_type"] == "discovery-call"
    assert booking["name"] == "Jane"
