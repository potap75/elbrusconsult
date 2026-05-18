"""Cross-cutting views."""
from __future__ import annotations

from django.http import HttpRequest, HttpResponse, JsonResponse
from django.shortcuts import render


def ratelimited(request: HttpRequest, exception: Exception | None = None) -> HttpResponse:
    """Friendly 429 response used by ``django_ratelimit``.

    Wired in via ``settings.RATELIMIT_VIEW`` so every blocked request
    funnels through here. We sniff for an AJAX / JSON caller and return
    JSON; otherwise we render the same minimal template the form pages
    can include.
    """
    wants_json = (
        request.headers.get("X-Requested-With") == "XMLHttpRequest"
        or "application/json" in request.headers.get("Accept", "")
        or request.path.startswith("/schedule/api/")
    )
    if wants_json:
        return JsonResponse(
            {
                "error": "rate_limited",
                "message": "Too many requests. Please slow down and try again later.",
            },
            status=429,
        )
    return render(
        request,
        "core/ratelimited.html",
        {
            "seo_title": "Too many requests",
            "seo_robots": "noindex,nofollow",
        },
        status=429,
    )
