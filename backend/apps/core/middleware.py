"""Security-related middleware for Elbrus Cloud.

Two middlewares live here:

* ``SecurityHeadersMiddleware`` - emits CSP, Permissions-Policy, and CORP
  headers and attaches a per-request CSP nonce so inline scripts (Consent
  Mode v2 bootstrap, GTM, dataLayer pushes) can run while keeping the
  ``script-src`` allowlist tight.
* ``AttributionMiddleware`` - captures UTMs / paid-channel click IDs into
  first- and last-touch cookies so that downstream forms (contact, booking
  inquiry, real booking) can persist a clean attribution snapshot without
  the views having to re-parse the URL.

The CSP allow-list is tuned for this codebase:

* Scripts are bundled (Tailwind output + the React scheduling island in
  ``backend/static/dist/scheduling/main.js``), so first-party scripts don't
  need ``'unsafe-inline'``.
* When GTM is enabled, every tag (Google Ads, LinkedIn Insight Tag, Meta
  Pixel, Microsoft UET, TikTok Pixel) loads via the GTM container. The
  allowlist below covers ALL of those vendor endpoints so a single CSP
  works for any combination of paid channels we turn on.
* Styles need ``'unsafe-inline'`` because Tailwind utility classes and
  small ``style`` attributes in markdown output occasionally use them. The
  script-src restriction is what actually mitigates XSS, so this trade-off
  is fine.
"""
from __future__ import annotations

import json
import logging
import re
import secrets
from typing import Callable
from urllib.parse import urlparse

from django.conf import settings
from django.http import HttpRequest, HttpResponse
from django.utils import timezone
from django.utils.http import http_date

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# CSP allow-list
# ---------------------------------------------------------------------------
# Vendor endpoints needed by the tags GTM can fan out to. Keep this list
# tight: every entry maps to a specific marketing/analytics surface we
# actually ship. If a future tag fails silently in the browser console, the
# fix is to add its host here, NOT to relax 'script-src' to 'unsafe-inline'.
_SCRIPT_SRC_VENDORS = (
    # Google Tag Manager + GA4 + Google Ads
    "https://*.googletagmanager.com",
    "https://*.google-analytics.com",
    "https://*.analytics.google.com",
    "https://*.googleadservices.com",
    "https://*.g.doubleclick.net",
    # LinkedIn Insight Tag
    "https://snap.licdn.com",
    # Meta Pixel
    "https://connect.facebook.net",
    # Microsoft Advertising UET
    "https://bat.bing.com",
    "https://*.clarity.ms",
    # TikTok Pixel
    "https://analytics.tiktok.com",
)

_CONNECT_SRC_VENDORS = (
    "https://*.google-analytics.com",
    "https://*.analytics.google.com",
    "https://*.googletagmanager.com",
    "https://*.g.doubleclick.net",
    "https://*.googleadservices.com",
    "https://px.ads.linkedin.com",
    "https://px4.ads.linkedin.com",
    "https://www.linkedin.com",
    "https://connect.facebook.net",
    "https://www.facebook.com",
    "https://*.facebook.com",
    "https://bat.bing.com",
    "https://*.clarity.ms",
    "https://analytics.tiktok.com",
    "https://*.tiktok.com",
)

_IMG_SRC_VENDORS = (
    "https://*.google-analytics.com",
    "https://*.analytics.google.com",
    "https://*.googletagmanager.com",
    "https://*.g.doubleclick.net",
    "https://*.googleadservices.com",
    "https://www.google.com",
    "https://www.google.co.uk",
    "https://px.ads.linkedin.com",
    "https://px4.ads.linkedin.com",
    "https://www.linkedin.com",
    "https://www.facebook.com",
    "https://*.facebook.com",
    "https://bat.bing.com",
    "https://*.clarity.ms",
    "https://analytics.tiktok.com",
)

_FRAME_SRC_VENDORS = (
    "https://td.doubleclick.net",
    "https://*.googletagmanager.com",
    "https://bid.g.doubleclick.net",
)

_PERMISSIONS_POLICY = ", ".join(
    [
        "camera=()",
        "microphone=()",
        "geolocation=()",
        "payment=()",
        "usb=()",
        "interest-cohort=()",
    ]
)


def _build_csp(nonce: str) -> str:
    """Render the full Content-Security-Policy header for a given nonce.

    Built fresh on every request because the nonce changes; cheap enough
    (string join over fixed lists).
    """
    script_src = " ".join(
        ("'self'", f"'nonce-{nonce}'", "'strict-dynamic'", *_SCRIPT_SRC_VENDORS)
    )
    connect_src = " ".join(("'self'", *_CONNECT_SRC_VENDORS))
    img_src = " ".join(("'self'", "data:", *_IMG_SRC_VENDORS))
    frame_src = " ".join(("'self'", *_FRAME_SRC_VENDORS))

    return "; ".join(
        [
            "default-src 'self'",
            f"img-src {img_src}",
            "style-src 'self' 'unsafe-inline'",
            f"script-src {script_src}",
            # script-src-elem mirrors script-src but only applies to <script>
            # elements (not inline event handlers). Some browsers require it
            # explicitly when 'strict-dynamic' is in play.
            f"script-src-elem {script_src}",
            "font-src 'self' data:",
            f"connect-src {connect_src}",
            f"frame-src {frame_src}",
            "frame-ancestors 'none'",
            "base-uri 'self'",
            "form-action 'self'",
            "object-src 'none'",
        ]
    )


class SecurityHeadersMiddleware:
    """Generate a per-request CSP nonce + emit CSP / Permissions-Policy / CORP."""

    def __init__(self, get_response: Callable[[HttpRequest], HttpResponse]) -> None:
        self.get_response = get_response

    def __call__(self, request: HttpRequest) -> HttpResponse:
        # 16 bytes = 128 bits of entropy; URL-safe base64 keeps the value
        # short enough to be cheap to repeat across many <script> tags.
        request.csp_nonce = secrets.token_urlsafe(16)
        response = self.get_response(request)
        response.setdefault("Content-Security-Policy", _build_csp(request.csp_nonce))
        response.setdefault("Permissions-Policy", _PERMISSIONS_POLICY)
        response.setdefault("Cross-Origin-Resource-Policy", "same-origin")
        return response


# ---------------------------------------------------------------------------
# Attribution capture
# ---------------------------------------------------------------------------
# Recognised query-string keys we want to persist on form submissions. The
# UTM 5-tuple is the open-standard set; the click-ID list covers the major
# paid networks we plan to run.
_UTM_KEYS = (
    "utm_source",
    "utm_medium",
    "utm_campaign",
    "utm_term",
    "utm_content",
)
_CLICK_ID_KEYS = (
    "gclid",      # Google Ads
    "gbraid",     # Google Ads (iOS app -> web)
    "wbraid",     # Google Ads (web -> app)
    "fbclid",     # Meta
    "li_fat_id",  # LinkedIn
    "msclkid",    # Microsoft Advertising
    "ttclid",     # TikTok Ads
)
# Anything else is dropped — we explicitly do NOT want to inadvertently log
# arbitrary query strings (could contain PII, search queries, etc.).
_ATTRIBUTION_KEYS = _UTM_KEYS + _CLICK_ID_KEYS

# Conservative length cap on any single value. Attackers will try to stuff
# huge strings in here to bloat cookies / DB rows. 256 chars handles even
# extreme real-world click IDs (gbraid/wbraid can be ~80) with headroom.
_MAX_VALUE_LEN = 256

# Strip everything except alnum + a few delimiters commonly used in click
# IDs and UTM values. Anything else gets dropped silently.
_VALUE_RE = re.compile(r"[^A-Za-z0-9_\-\.\+:%~|]+")


def _sanitize_value(raw: str) -> str:
    if not raw:
        return ""
    return _VALUE_RE.sub("", raw)[:_MAX_VALUE_LEN]


def _extract_attribution(request: HttpRequest) -> dict[str, str]:
    """Pull recognised attribution params out of the querystring.

    Returns an empty dict if no recognised keys are present. Values are
    sanitised to a strict allow-list of characters to keep the cookie /
    DB column hostile-payload-resistant.
    """
    found: dict[str, str] = {}
    for key in _ATTRIBUTION_KEYS:
        value = request.GET.get(key, "").strip()
        cleaned = _sanitize_value(value)
        if cleaned:
            found[key] = cleaned
    return found


def _safe_referrer(request: HttpRequest) -> str:
    """Return the Referer header iff it points at a different origin.

    Same-origin referers add no signal (just internal navigation) and would
    flood the column with our own URLs. Off-origin referers are the actual
    organic / social signal we want to keep.
    """
    referer = request.META.get("HTTP_REFERER", "").strip()
    if not referer:
        return ""
    try:
        ref_host = urlparse(referer).netloc.lower()
    except ValueError:
        return ""
    own_host = urlparse(settings.SITE_URL).netloc.lower()
    if ref_host and ref_host != own_host:
        return referer[:_MAX_VALUE_LEN]
    return ""


def _read_json_cookie(request: HttpRequest, name: str) -> dict | None:
    raw = request.COOKIES.get(name)
    if not raw:
        return None
    try:
        data = json.loads(raw)
    except (ValueError, TypeError):
        return None
    if not isinstance(data, dict):
        return None
    return data


class AttributionMiddleware:
    """Capture UTM + paid-channel click IDs into first/last-touch cookies.

    Behaviour:

    * On every request, parse recognised attribution params from the URL.
    * If any are present, write them to ``elb_attr_last`` (a session-length
      cookie overwritten every visit) with a fresh ``landing_page`` and
      cross-origin ``referrer`` if available.
    * If ``elb_attr_first`` is NOT already set, write the same payload there
      with a ``ATTRIBUTION_COOKIE_DAYS``-day expiry. Once set, first-touch is
      sticky for the full window.
    * If the request has no recognised params, the cookies are left alone -
      this middleware is read-only on every page that isn't an ad landing.

    The cookies are first-party, HttpOnly, SameSite=Lax. They are NOT
    Secure-only in dev (so localhost works); ``prod.py`` flips that on via
    the session cookie config, but cookies we set here pass ``secure`` from
    ``request.is_secure()``.
    """

    def __init__(self, get_response: Callable[[HttpRequest], HttpResponse]) -> None:
        self.get_response = get_response

    def __call__(self, request: HttpRequest) -> HttpResponse:
        new_attribution = _extract_attribution(request)

        # Always make the merged snapshot available to views, even on
        # requests with no new attribution data (so views can read cookies
        # without re-parsing).
        first_touch = _read_json_cookie(request, settings.ATTRIBUTION_FIRST_TOUCH_COOKIE)
        last_touch = _read_json_cookie(request, settings.ATTRIBUTION_LAST_TOUCH_COOKIE)
        request.attribution = {
            "first_touch": first_touch or {},
            "last_touch": last_touch or {},
            "current": new_attribution,
        }

        response = self.get_response(request)

        if not new_attribution:
            return response

        payload = {
            **new_attribution,
            "landing_page": request.path[:_MAX_VALUE_LEN],
            "referrer": _safe_referrer(request),
            "captured_at": timezone.now().isoformat(),
        }
        # Drop empty referrer to keep cookies small.
        if not payload["referrer"]:
            payload.pop("referrer")

        cookie_value = json.dumps(payload, separators=(",", ":"))
        secure = request.is_secure()

        # Always update last-touch.
        response.set_cookie(
            settings.ATTRIBUTION_LAST_TOUCH_COOKIE,
            cookie_value,
            max_age=None,  # session-length
            secure=secure,
            httponly=True,
            samesite="Lax",
        )

        # First-touch only if not already present.
        if first_touch is None:
            response.set_cookie(
                settings.ATTRIBUTION_FIRST_TOUCH_COOKIE,
                cookie_value,
                max_age=settings.ATTRIBUTION_COOKIE_DAYS * 24 * 60 * 60,
                secure=secure,
                httponly=True,
                samesite="Lax",
            )

        return response


# Keep http_date importable here in case future hooks need it (CSP report-uri,
# Set-Cookie expires, ...). Suppress the unused warning by re-exporting.
_ = http_date
