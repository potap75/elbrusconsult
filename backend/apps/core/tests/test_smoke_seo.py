"""Smoke + SEO assertions for every public route.

Strategy: hit each URL, expect 200, and check that the response contains the
SEO essentials (title, meta description, canonical link, OG tags, JSON-LD).
"""
from __future__ import annotations

import pytest
from django.test import Client
from django.urls import reverse

PUBLIC_ROUTES_BY_NAME = [
    "home",
    "about",
    "privacy",
    "terms",
    "services-list",
    "blog-list",
    "contact",
    "newsletter-subscribe",
    "schedule",
]


@pytest.mark.django_db
def test_seed_command_runs_clean():
    from django.core.management import call_command
    from blog.models import Post
    from pages.models import Service

    call_command("seed")
    assert Service.objects.filter(is_published=True).count() >= 8
    assert Post.published.exists()

    # Idempotent
    call_command("seed")
    assert Service.objects.filter(is_published=True).count() >= 8


@pytest.mark.django_db
@pytest.mark.parametrize("url_name", PUBLIC_ROUTES_BY_NAME)
def test_public_route_has_seo_essentials(url_name, seeded_db):
    client = Client()
    response = client.get(reverse(url_name))
    assert response.status_code == 200, f"{url_name} returned {response.status_code}"

    body = response.content.decode("utf-8")

    assert "<title>" in body and "</title>" in body, f"{url_name}: missing <title>"
    assert 'name="description"' in body, f"{url_name}: missing meta description"
    assert 'rel="canonical"' in body, f"{url_name}: missing canonical link"
    assert 'property="og:title"' in body, f"{url_name}: missing og:title"
    assert 'property="og:type"' in body, f"{url_name}: missing og:type"
    assert 'name="twitter:card"' in body, f"{url_name}: missing twitter:card"

    # Site-wide JSON-LD blocks come from the context processor.
    assert '"@type":"Organization"' in body, f"{url_name}: missing Organization JSON-LD"
    assert '"@type":"WebSite"' in body, f"{url_name}: missing WebSite JSON-LD"


@pytest.mark.django_db
def test_sitemap_lists_static_and_dynamic_urls(seeded_db):
    client = Client()
    response = client.get("/sitemap.xml")
    assert response.status_code == 200
    body = response.content.decode("utf-8")

    # Static views
    for path in ["/", "/about/", "/privacy/", "/terms/", "/services/", "/blog/", "/contact/", "/newsletter/", "/schedule/"]:
        assert path in body, f"sitemap missing static path {path}"

    # At least one service detail and the sample blog post
    assert "/services/risk/" in body
    assert "/blog/cloud-baseline-matters-more/" in body


@pytest.mark.django_db
def test_robots_txt_serves_and_references_sitemap():
    client = Client()
    response = client.get("/robots.txt")
    assert response.status_code == 200
    body = response.content.decode("utf-8")
    assert "Sitemap:" in body
    assert "/sitemap.xml" in body


@pytest.mark.django_db
def test_blog_feed_serves_rss(seeded_db):
    client = Client()
    response = client.get(reverse("blog-feed"))
    assert response.status_code == 200
    body = response.content.decode("utf-8")
    assert "<rss" in body or "<feed" in body


@pytest.mark.django_db
def test_blog_detail_emits_article_jsonld(seeded_db):
    from blog.models import Post

    post = Post.published.first()
    assert post is not None

    client = Client()
    response = client.get(post.get_absolute_url())
    assert response.status_code == 200
    body = response.content.decode("utf-8")
    assert '"@type":"Article"' in body


@pytest.mark.django_db
def test_service_detail_emits_service_jsonld(seeded_db):
    from pages.models import Service

    service = Service.objects.filter(is_published=True).first()
    assert service is not None

    client = Client()
    response = client.get(service.get_absolute_url())
    assert response.status_code == 200
    body = response.content.decode("utf-8")
    assert '"@type":"Service"' in body


@pytest.mark.django_db
def test_contact_detail_emits_local_business_jsonld():
    client = Client()
    response = client.get(reverse("contact"))
    assert response.status_code == 200
    body = response.content.decode("utf-8")
    assert '"@type":"LocalBusiness"' in body
    assert '"telephone":"+1 (704) 686-8481"' in body


@pytest.mark.django_db
def test_home_includes_advisory_phone_link():
    client = Client()
    response = client.get(reverse("home"))
    assert response.status_code == 200
    body = response.content.decode("utf-8")
    assert 'href="tel:+17046868481"' in body
    assert "Paid advisory line" in body
    assert "Call for advice" in body


@pytest.mark.django_db
def test_organization_jsonld_includes_advisory_phone():
    client = Client()
    response = client.get(reverse("home"))
    assert response.status_code == 200
    body = response.content.decode("utf-8")
    assert '"@type":"Organization"' in body
    assert '"telephone":"+1 (704) 686-8481"' in body
    assert "/static/img/logo.png" in body


@pytest.mark.django_db
def test_privacy_page_renders_and_is_in_sitemap():
    client = Client()
    response = client.get(reverse("privacy"))
    assert response.status_code == 200
    body = response.content.decode("utf-8")
    assert 'id="privacy"' in body
    assert "Cookie consent" in body or "cookies" in body.lower()

    sitemap = client.get("/sitemap.xml")
    assert "/privacy/" in sitemap.content.decode("utf-8")


@pytest.mark.django_db
def test_terms_page_renders_and_is_linked_from_footer():
    client = Client()
    response = client.get(reverse("terms"))
    assert response.status_code == 200
    body = response.content.decode("utf-8")
    assert 'id="terms"' in body
    assert "Terms of Service" in body

    # Footer on every page links to both legal pages.
    home = client.get(reverse("home")).content.decode("utf-8")
    assert 'href="/terms/"' in home
    assert 'href="/privacy/"' in home

    sitemap = client.get("/sitemap.xml")
    assert "/terms/" in sitemap.content.decode("utf-8")


@pytest.mark.django_db
def test_blog_article_jsonld_uses_png_logo(seeded_db):
    from blog.models import Post

    post = Post.published.first()
    assert post is not None

    client = Client()
    response = client.get(post.get_absolute_url())
    assert response.status_code == 200
    body = response.content.decode("utf-8")
    assert "/static/img/logo.png" in body
    assert "logo.svg" not in body


@pytest.mark.django_db
def test_healthz_returns_ok():
    client = Client()
    response = client.get("/healthz")
    assert response.status_code == 200
    assert b"ok" in response.content


@pytest.mark.django_db
def test_contact_form_creates_message_and_redirects():
    client = Client()
    payload = {
        "name": "Test User",
        "email": "test@example.com",
        "company": "Acme",
        "subject": "Hello",
        "message": "Please reach out.",
        "website": "",  # honeypot must stay empty
    }
    response = client.post(reverse("contact"), data=payload)
    assert response.status_code == 302
    assert response.url == reverse("contact-thanks")

    from contact.models import ContactMessage

    assert ContactMessage.objects.filter(email="test@example.com").exists()


@pytest.mark.django_db
def test_contact_form_rejects_honeypot():
    client = Client()
    payload = {
        "name": "Spam Bot",
        "email": "spam@example.com",
        "message": "Buy something.",
        "website": "https://spam.example/",  # honeypot triggered
    }
    response = client.post(reverse("contact"), data=payload)
    # Form is invalid; we re-render the page (no redirect).
    assert response.status_code == 200

    from contact.models import ContactMessage

    assert not ContactMessage.objects.filter(email="spam@example.com").exists()


@pytest.mark.django_db
def test_newsletter_subscribe_creates_pending_subscriber():
    client = Client()
    response = client.post(
        reverse("newsletter-subscribe"),
        data={"email": "reader@example.com", "website": ""},
    )
    assert response.status_code == 302
    assert response.url == reverse("newsletter-pending")

    from newsletter.models import Subscriber

    sub = Subscriber.objects.get(email="reader@example.com")
    assert sub.confirmed_at is None
    assert sub.unsubscribed_at is None

    # Confirm link
    confirm = client.get(
        reverse("newsletter-confirm", kwargs={"token": sub.token})
    )
    assert confirm.status_code == 200
    sub.refresh_from_db()
    assert sub.confirmed_at is not None

    # Unsubscribe link
    unsub = client.get(
        reverse("newsletter-unsubscribe", kwargs={"token": sub.token})
    )
    assert unsub.status_code == 200
    sub.refresh_from_db()
    assert sub.unsubscribed_at is not None


@pytest.mark.django_db
def test_scheduling_inquiry_api_accepts_json(seeded_db):
    import json

    client = Client(enforce_csrf_checks=False)
    response = client.post(
        reverse("scheduling-api-inquiry"),
        data=json.dumps(
            {
                "name": "Jane Doe",
                "email": "jane@example.com",
                "company": "Acme",
                "phone": "",
                "service": None,
                "preferred_date": None,
                "timezone_label": "America/New_York",
                "notes": "Need a 30-min intro call.",
            }
        ),
        content_type="application/json",
    )
    assert response.status_code == 200
    payload = response.json()
    assert payload["ok"] is True

    from scheduling.models import BookingInquiry

    assert BookingInquiry.objects.filter(email="jane@example.com").exists()


@pytest.mark.django_db
def test_scheduling_services_api_lists_published(seeded_db):
    client = Client()
    response = client.get(reverse("scheduling-api-services"))
    assert response.status_code == 200
    data = response.json()
    assert "services" in data
    names = [s["name"] for s in data["services"]]
    assert "Risk" in names


@pytest.mark.django_db
def test_scheduling_appointment_types_api_lists_seeded(seeded_db):
    client = Client()
    response = client.get(reverse("scheduling-api-appointment-types"))
    assert response.status_code == 200
    data = response.json()
    slugs = [t["slug"] for t in data["appointment_types"]]
    assert "discovery-call" in slugs
    assert "deep-dive-consultation" in slugs
