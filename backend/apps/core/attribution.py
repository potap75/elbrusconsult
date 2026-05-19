"""Attribution snapshot helper.

The middleware (``core.middleware.AttributionMiddleware``) parses the
querystring into ``request.attribution = {"first_touch": ..., "last_touch":
..., "current": ...}`` on every request. This module exposes a small
helper that view code uses to build the dict it persists to a model row.

Why a helper rather than ``request.attribution`` directly:

* Views shouldn't care which cookie won; they want one clean payload to
  drop into a JSONField. We merge first-touch + last-touch + current here.
* If the middleware ever needs to grow (server-side ID resolution, hashing,
  etc.) it's one place to change instead of every view that captures a
  lead.
* Makes tests easy: a view can be tested against a fake snapshot without
  having to round-trip cookies through a test client.

The merged payload shape:

    {
        "first_touch": { "utm_source": "google", "gclid": "Cj0K...", "landing_page": "/services/risk/", "captured_at": "2026-..." },
        "last_touch":  { "utm_source": "linkedin", ... },
        "current":     { "utm_source": "linkedin", ... }
    }

Only the keys we recognised (UTMs + click IDs + landing_page + referrer)
ever appear; arbitrary querystring junk is dropped at middleware time.
"""
from __future__ import annotations

from typing import Any

from django.http import HttpRequest
from django.utils import timezone


def get_attribution_snapshot(request: HttpRequest) -> dict[str, Any]:
    """Return a merged attribution dict ready to persist to a JSONField.

    Safe to call from any view on any request. Returns an empty-shaped
    dict when no attribution data is available, so callers can always
    save the result without conditionals.
    """
    raw = getattr(request, "attribution", None) or {}
    first = dict(raw.get("first_touch") or {})
    last = dict(raw.get("last_touch") or {})
    current = dict(raw.get("current") or {})

    # Stamp a capture time so we can tell when this record's attribution
    # was finalised vs when first-touch was seeded.
    captured_at = timezone.now().isoformat()

    # If the cookies didn't have a timestamp yet (older sessions), backfill
    # one based on the current request — better than nothing.
    if first and "captured_at" not in first:
        first["captured_at"] = captured_at
    if last and "captured_at" not in last:
        last["captured_at"] = captured_at

    return {
        "first_touch": first,
        "last_touch": last,
        "current": current,
        "captured_at": captured_at,
    }
