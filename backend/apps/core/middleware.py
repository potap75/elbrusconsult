"""Security-related middleware for Elbrus Cloud.

Adds headers that Django's built-in ``SecurityMiddleware`` does not handle:

* ``Content-Security-Policy`` - reduces XSS blast radius by restricting
  where scripts / styles / images may load from.
* ``Permissions-Policy`` - tells the browser which powerful features the
  site does NOT use (camera, mic, geolocation, ...).
* ``Cross-Origin-Resource-Policy`` - blocks other origins from embedding
  our resources via Spectre-style side channels.

The CSP allow-list is tuned for this codebase:

* Scripts are all bundled (Tailwind output + the React scheduling island
  in ``backend/static/dist/scheduling/main.js``), so we need no
  ``'unsafe-inline'`` for scripts.
* Styles need ``'unsafe-inline'`` because Tailwind utility classes and
  small ``style`` attributes in markdown output occasionally use them.
  The script-src restriction is what actually mitigates XSS, so this
  trade-off is fine.
"""
from __future__ import annotations

from typing import Callable

from django.http import HttpRequest, HttpResponse

_CSP = "; ".join(
    [
        "default-src 'self'",
        "img-src 'self' data:",
        "style-src 'self' 'unsafe-inline'",
        "script-src 'self'",
        "font-src 'self' data:",
        "connect-src 'self'",
        "frame-ancestors 'none'",
        "base-uri 'self'",
        "form-action 'self'",
        "object-src 'none'",
    ]
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


class SecurityHeadersMiddleware:
    """Apply CSP, Permissions-Policy, and CORP to every response."""

    def __init__(self, get_response: Callable[[HttpRequest], HttpResponse]) -> None:
        self.get_response = get_response

    def __call__(self, request: HttpRequest) -> HttpResponse:
        response = self.get_response(request)
        response.setdefault("Content-Security-Policy", _CSP)
        response.setdefault("Permissions-Policy", _PERMISSIONS_POLICY)
        response.setdefault("Cross-Origin-Resource-Policy", "same-origin")
        return response
