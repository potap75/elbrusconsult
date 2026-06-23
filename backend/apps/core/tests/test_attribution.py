"""Tests for AttributionMiddleware and the JSONField persistence wiring."""
from __future__ import annotations

import json

import pytest
from django.conf import settings
from django.test import Client
from django.urls import reverse


# --------------------------------------------------------------------------
# Middleware: cookie capture
# --------------------------------------------------------------------------


@pytest.mark.django_db
def test_no_attribution_params_leaves_cookies_alone():
    client = Client()
    response = client.get(reverse("home"))
    assert settings.ATTRIBUTION_FIRST_TOUCH_COOKIE not in response.cookies
    assert settings.ATTRIBUTION_LAST_TOUCH_COOKIE not in response.cookies


@pytest.mark.django_db
def test_utm_params_set_first_and_last_touch_cookies():
    client = Client()
    response = client.get(
        reverse("home"),
        {
            "utm_source": "google",
            "utm_medium": "cpc",
            "utm_campaign": "spring-cloud",
            "gclid": "Cj0KCQjw_test_value-XYZ",
        },
    )
    first = response.cookies.get(settings.ATTRIBUTION_FIRST_TOUCH_COOKIE)
    last = response.cookies.get(settings.ATTRIBUTION_LAST_TOUCH_COOKIE)
    assert first is not None, "First-touch cookie must be set on first ad click"
    assert last is not None, "Last-touch cookie must be set on every ad click"

    payload = json.loads(first.value)
    assert payload["utm_source"] == "google"
    assert payload["utm_medium"] == "cpc"
    assert payload["utm_campaign"] == "spring-cloud"
    assert payload["gclid"] == "Cj0KCQjw_test_value-XYZ"
    assert payload["landing_page"] == reverse("home")
    assert "captured_at" in payload


@pytest.mark.django_db
def test_first_touch_is_sticky_across_subsequent_ad_clicks():
    client = Client()
    # First ad click: Google
    r1 = client.get(reverse("home"), {"utm_source": "google", "utm_medium": "cpc"})
    first_after_r1 = r1.cookies[settings.ATTRIBUTION_FIRST_TOUCH_COOKIE].value

    # Second ad click on a different channel — last-touch must update,
    # first-touch must NOT.
    r2 = client.get(reverse("home"), {"utm_source": "linkedin", "utm_medium": "social"})
    # First-touch cookie is only re-set if the middleware decides to send
    # a new value. Since the client preserves cookies across requests,
    # the absence of a new Set-Cookie header for first_touch on r2 is
    # the right signal.
    assert settings.ATTRIBUTION_FIRST_TOUCH_COOKIE not in r2.cookies, (
        "First-touch must NOT be re-set once it's been captured."
    )
    last_after_r2 = json.loads(
        r2.cookies[settings.ATTRIBUTION_LAST_TOUCH_COOKIE].value
    )
    assert last_after_r2["utm_source"] == "linkedin"
    # Sanity: original first-touch still around in the client jar.
    assert "google" in first_after_r1


@pytest.mark.django_db
def test_attribution_values_are_sanitized():
    """Hostile querystring values must be stripped to a strict allow-list."""
    client = Client()
    response = client.get(
        reverse("home"),
        {
            "utm_source": "google<script>alert(1)</script>",
            "gclid": "AAA' OR '1'='1",
        },
    )
    last = json.loads(
        response.cookies[settings.ATTRIBUTION_LAST_TOUCH_COOKIE].value
    )
    assert "<" not in last["utm_source"]
    assert "script" in last["utm_source"]  # alpha survives
    assert "'" not in last["gclid"]
    assert " " not in last["gclid"]


@pytest.mark.django_db
def test_arbitrary_query_keys_are_ignored():
    """Only the recognised attribution keys end up in the snapshot."""
    client = Client()
    response = client.get(
        reverse("home"),
        {"utm_source": "google", "q": "ssh secrets", "email": "a@b.com"},
    )
    last = json.loads(
        response.cookies[settings.ATTRIBUTION_LAST_TOUCH_COOKIE].value
    )
    assert "q" not in last
    assert "email" not in last
    assert last["utm_source"] == "google"


# --------------------------------------------------------------------------
# Model persistence
# --------------------------------------------------------------------------


@pytest.mark.django_db
def test_contact_form_persists_attribution():
    """A contact submission preceded by an ad click must store the
    attribution snapshot on the model row."""
    client = Client()
    # Ad-click landing
    client.get(
        reverse("home"),
        {"utm_source": "google", "utm_medium": "cpc", "gclid": "TESTCLICKID-123"},
    )
    # Conversion
    response = client.post(
        reverse("contact"),
        data={
            "name": "Attributed User",
            "email": "attributed@example.com",
            "company": "Acme",
            "subject": "Hello",
            "message": "From an ad.",
            "website": "",
        },
    )
    assert response.status_code == 302

    from contact.models import ContactMessage

    msg = ContactMessage.objects.get(email="attributed@example.com")
    assert msg.attribution, "Attribution snapshot must be persisted"
    assert msg.attribution["last_touch"]["gclid"] == "TESTCLICKID-123"
    assert msg.attribution["first_touch"]["utm_source"] == "google"


@pytest.mark.django_db
def test_scheduling_inquiry_persists_attribution(seeded_db):
    client = Client(enforce_csrf_checks=False)
    # Ad-click landing
    client.get(
        reverse("schedule"),
        {"utm_source": "linkedin", "li_fat_id": "LI-test-fat-id"},
    )
    # Inquiry submission
    response = client.post(
        reverse("scheduling-api-inquiry"),
        data=json.dumps(
            {
                "name": "Lead From LinkedIn",
                "email": "li-lead@example.com",
                "company": "Acme",
                "phone": "",
                "service": None,
                "preferred_date": None,
                "timezone_label": "America/New_York",
                "notes": "Hi from LinkedIn.",
            }
        ),
        content_type="application/json",
    )
    assert response.status_code == 200

    from scheduling.models import BookingInquiry

    inquiry = BookingInquiry.objects.get(email="li-lead@example.com")
    assert inquiry.attribution["last_touch"]["li_fat_id"] == "LI-test-fat-id"
    assert inquiry.attribution["last_touch"]["utm_source"] == "linkedin"


@pytest.mark.django_db
def test_newsletter_subscribe_persists_attribution():
    client = Client()
    client.get(
        reverse("newsletter-subscribe"),
        {"utm_source": "google", "utm_medium": "cpc", "gclid": "TESTCLICKID-456"},
    )
    response = client.post(
        reverse("newsletter-subscribe"),
        data={"email": "newsletter-ad@example.com", "website": ""},
    )
    assert response.status_code == 302

    from newsletter.models import Subscriber

    sub = Subscriber.objects.get(email="newsletter-ad@example.com")
    assert sub.attribution
    assert sub.attribution["last_touch"]["gclid"] == "TESTCLICKID-456"
    assert sub.attribution["first_touch"]["utm_source"] == "google"
