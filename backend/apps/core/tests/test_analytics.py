"""Tests for the analytics + Consent Mode v2 + GTM + consent-banner stack.

Strategy: never hit real third-party endpoints. Render pages under a range
of settings combinations and assert the right markup is or isn't emitted.
"""
from __future__ import annotations

import pytest
from django.test import Client, override_settings
from django.urls import reverse


@pytest.mark.django_db
def test_analytics_partial_renders_nothing_when_no_ids_configured():
    """Default settings = no tag manager IDs = zero third-party requests.

    This is the privacy-by-default contract: a deploy that forgets to set
    GTM_CONTAINER_ID must not leak data to any vendor.
    """
    client = Client()
    response = client.get(reverse("home"))
    body = response.content.decode("utf-8")

    assert "googletagmanager.com/gtm.js" not in body
    assert "googletagmanager.com/gtag/js" not in body
    assert "elbrus-consent" not in body, (
        "Consent banner must not render when no analytics are configured."
    )
    assert "google-site-verification" not in body
    assert "msvalidate.01" not in body


@pytest.mark.django_db
@override_settings(GTM_CONTAINER_ID="GTM-TEST123")
def test_gtm_loader_renders_when_container_id_set():
    client = Client()
    response = client.get(reverse("home"))
    body = response.content.decode("utf-8")

    assert "GTM-TEST123" in body
    assert "googletagmanager.com/gtm.js" in body
    # noscript fallback iframe for JS-disabled visitors.
    assert "googletagmanager.com/ns.html?id=GTM-TEST123" in body
    # Consent Mode v2 default must precede GTM so the container sees it on
    # first tick. Look for the consent default call.
    assert 'gtag("consent", "default"' in body
    assert "ad_storage" in body
    # Default is denied (privacy-by-default).
    assert '"denied"' in body
    # Consent banner is rendered (server-side; JS shows/hides it).
    assert 'id="elbrus-consent"' in body


@pytest.mark.django_db
@override_settings(GA4_MEASUREMENT_ID="G-TEST", GTM_CONTAINER_ID="")
def test_ga4_direct_loader_renders_when_gtm_unset():
    """GA4 falls back to direct gtag.js when no GTM container is set."""
    client = Client()
    response = client.get(reverse("home"))
    body = response.content.decode("utf-8")

    assert "googletagmanager.com/gtag/js?id=G-TEST" in body
    assert "googletagmanager.com/gtm.js" not in body


@pytest.mark.django_db
@override_settings(
    GTM_CONTAINER_ID="GTM-TEST123",
    GA4_MEASUREMENT_ID="G-TEST",
)
def test_gtm_wins_when_both_set():
    client = Client()
    response = client.get(reverse("home"))
    body = response.content.decode("utf-8")

    # GTM loader URL is built via JS string concatenation, so the rendered
    # body contains the gtm.js base and the container ID separately.
    assert "googletagmanager.com/gtm.js" in body
    assert "GTM-TEST123" in body
    # Direct gtag.js loader is NOT rendered when GTM is configured (GA4
    # fires through the GTM container instead).
    assert "gtag/js?id=G-TEST" not in body


@pytest.mark.django_db
@override_settings(GTM_CONTAINER_ID="GTM-TEST123", CONSENT_DEFAULT_GRANTED=True)
def test_consent_default_can_be_set_to_granted():
    """For non-EEA-restricted deploys we can default consent to granted."""
    client = Client()
    response = client.get(reverse("home"))
    body = response.content.decode("utf-8")

    assert '"granted"' in body
    # When consent defaults to granted, we still always allow analytics +
    # ads. The denied state should NOT appear in the default block.
    consent_block = body[body.index('gtag("consent", "default"'):]
    consent_block = consent_block[: consent_block.index(")")]
    assert "denied" not in consent_block


@pytest.mark.django_db
@override_settings(
    GOOGLE_SITE_VERIFICATION="abc123-google",
    BING_SITE_VERIFICATION="xyz789-bing",
)
def test_search_engine_verification_meta_rendered_when_set():
    client = Client()
    response = client.get(reverse("home"))
    body = response.content.decode("utf-8")

    assert 'name="google-site-verification" content="abc123-google"' in body
    assert 'name="msvalidate.01" content="xyz789-bing"' in body


@pytest.mark.django_db
@override_settings(GTM_CONTAINER_ID="GTM-TEST123")
def test_elbrus_track_shim_is_always_emitted_when_analytics_on():
    """The cross-channel conversion API (window.elbrusTrack) is the only
    correct way for first-party JS / the React island to fire conversions.
    It must be present whenever ANY analytics ID is configured.
    """
    client = Client()
    response = client.get(reverse("home"))
    body = response.content.decode("utf-8")

    assert "window.elbrusTrack" in body


@pytest.mark.django_db
@override_settings(GTM_CONTAINER_ID="GTM-TEST123")
def test_contact_thanks_page_pushes_lead_conversion():
    """The contact form's thanks page must push a conversion event so GTM
    can map it to a Google Ads / LinkedIn / Meta conversion."""
    client = Client()
    response = client.get(reverse("contact-thanks"))
    body = response.content.decode("utf-8")

    assert "contact_form_submit" in body
    assert '"conversion_type":"lead"' in body or "conversion_type" in body
