"""Smoke tests for the security hardening layer.

Covers:

* Security response headers we promise to emit on every page
  (``Content-Security-Policy``, ``Permissions-Policy``, ``X-Frame-Options``,
  ``X-Content-Type-Options``, ``Referrer-Policy``,
  ``Cross-Origin-Resource-Policy``).
* Markdown -> HTML rendering strips ``<script>`` / ``javascript:`` URLs
  via :mod:`bleach` so that even a compromised staff account cannot inject
  XSS into the public blog or services pages.
* Per-endpoint rate limiting via ``django-ratelimit`` returns 429 (handled
  by ``core.views.ratelimited`` and wired through ``RATELIMIT_VIEW``)
  once the configured threshold is exceeded.
"""
from __future__ import annotations

import pytest
from django.core.cache import cache
from django.test import Client
from django.urls import reverse


@pytest.fixture(autouse=True)
def _clear_ratelimit_cache():
    """django-ratelimit stores counters in the default cache.

    LocMemCache survives across tests in the same process, so unrelated
    tests would otherwise see each other's counters. Clear before AND
    after each test to keep them isolated.
    """
    cache.clear()
    yield
    cache.clear()


# ---------------------------------------------------------------------------
# Security headers
# ---------------------------------------------------------------------------
EXPECTED_HEADERS = {
    "Content-Security-Policy",
    "Permissions-Policy",
    "Cross-Origin-Resource-Policy",
    "X-Frame-Options",
    "X-Content-Type-Options",
    "Referrer-Policy",
}


@pytest.mark.django_db
def test_homepage_emits_all_security_headers():
    client = Client()
    response = client.get(reverse("home"))
    assert response.status_code == 200
    missing = EXPECTED_HEADERS - set(response.headers)
    assert not missing, f"Missing security headers: {missing}"

    csp = response.headers["Content-Security-Policy"]
    assert "frame-ancestors 'none'" in csp
    assert "object-src 'none'" in csp
    assert "script-src 'self'" in csp

    assert response.headers["X-Frame-Options"] == "DENY"
    assert response.headers["X-Content-Type-Options"] == "nosniff"


# ---------------------------------------------------------------------------
# Bleach sanitization of admin-authored markdown
# ---------------------------------------------------------------------------


@pytest.mark.django_db
def test_blog_post_strips_script_and_javascript_urls():
    from blog.models import Category, Post

    category = Category.objects.create(name="Security")
    post = Post.objects.create(
        title="XSS canary",
        slug="xss-canary",
        category=category,
        excerpt="canary",
        body_markdown=(
            "Hello <script>alert('xss')</script> world.\n\n"
            "[click me](javascript:alert('xss'))\n\n"
            "<img src=\"x\" onerror=\"alert('xss')\">"
        ),
        status=Post.Status.PUBLISHED,
    )
    html = post.body_html
    assert "<script" not in html.lower()
    assert "javascript:" not in html.lower()
    assert "onerror" not in html.lower()


# ---------------------------------------------------------------------------
# django-ratelimit on public POST endpoints
# ---------------------------------------------------------------------------


def _contact_payload(suffix: str = "") -> dict[str, str]:
    return {
        "name": f"Test User{suffix}",
        "email": f"user{suffix}@example.com",
        "company": "Acme",
        "subject": "Hello",
        "message": "Please reach out.",
        "website": "",
    }


@pytest.mark.django_db
def test_contact_form_rate_limited_after_threshold():
    client = Client()
    # Configured rate is 5/h per IP; the test client always reports
    # 127.0.0.1, so the 6th POST must trip the limiter.
    for i in range(5):
        response = client.post(reverse("contact"), data=_contact_payload(str(i)))
        assert response.status_code == 302, (
            f"POST {i + 1} unexpectedly returned {response.status_code}"
        )

    blocked = client.post(reverse("contact"), data=_contact_payload("blocked"))
    assert blocked.status_code == 429, (
        f"6th POST should be rate-limited; got {blocked.status_code}"
    )


@pytest.mark.django_db
def test_scheduling_inquiry_api_rate_limit_returns_json_429(seeded_db):
    import json

    client = Client(enforce_csrf_checks=False)
    payload = json.dumps(
        {
            "name": "Jane Doe",
            "email": "jane@example.com",
            "company": "Acme",
            "phone": "",
            "service": None,
            "preferred_date": None,
            "timezone_label": "America/New_York",
            "notes": "Intro call.",
        }
    )

    # Rate is 10/h; first 10 succeed, the 11th is rate-limited.
    for i in range(10):
        response = client.post(
            reverse("scheduling-api-inquiry"),
            data=payload,
            content_type="application/json",
        )
        assert response.status_code == 200, f"call {i + 1} returned {response.status_code}"

    blocked = client.post(
        reverse("scheduling-api-inquiry"),
        data=payload,
        content_type="application/json",
    )
    assert blocked.status_code == 429
    assert blocked.json()["error"] == "rate_limited"
