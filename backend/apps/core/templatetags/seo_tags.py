"""Template tags for emitting JSON-LD blocks and CSP nonces.

Usage::

    {% load seo_tags %}
    {% json_ld organization_schema %}
    <script {% csp_nonce_attr %}>/* inline script */</script>

JSON-LD payloads are serialized with HTML-safe escaping. CSP nonces come
from ``SecurityHeadersMiddleware`` and are attached to ``request.csp_nonce``.
"""
from __future__ import annotations

import json
from typing import Any

from django import template
from django.utils.safestring import mark_safe

register = template.Library()


def _safe_json(payload: Any) -> str:
    """Serialize a payload to JSON, escaping characters unsafe in HTML."""
    return (
        json.dumps(payload, ensure_ascii=False, separators=(",", ":"))
        .replace("<", "\\u003c")
        .replace(">", "\\u003e")
        .replace("&", "\\u0026")
        .replace("\u2028", "\\u2028")
        .replace("\u2029", "\\u2029")
    )


@register.simple_tag(takes_context=True)
def json_ld(context, payload: Any) -> str:
    """Render a JSON-LD ``<script>`` block, nonced if a CSP nonce is set.

    The nonce is read from ``request.csp_nonce`` (set by
    ``SecurityHeadersMiddleware``). Adding a nonce here is harmless if CSP
    isn't enforcing nonces; it keeps a single code path for all inline
    scripts on the page.
    """
    if not payload:
        return ""
    request = context.get("request")
    nonce = getattr(request, "csp_nonce", "") if request is not None else ""
    nonce_attr = f' nonce="{nonce}"' if nonce else ""
    return mark_safe(
        f'<script type="application/ld+json"{nonce_attr}>{_safe_json(payload)}</script>'
    )


@register.simple_tag(takes_context=True)
def csp_nonce_attr(context) -> str:
    """Emit `` nonce="<value>"`` (with leading space) for inline scripts.

    Empty string if no nonce is available (e.g. in management commands
    rendering templates without a request). Designed so templates can drop
    it inside a ``<script>`` tag without worrying about presence.
    """
    request = context.get("request")
    nonce = getattr(request, "csp_nonce", "") if request is not None else ""
    if not nonce:
        return ""
    return mark_safe(f' nonce="{nonce}"')


@register.simple_tag(takes_context=True)
def csp_nonce(context) -> str:
    """Return the raw CSP nonce value (no surrounding markup).

    Useful when building third-party loader URLs that need the nonce
    baked into the path or query string. Most callers want
    ``csp_nonce_attr`` instead.
    """
    request = context.get("request")
    return getattr(request, "csp_nonce", "") if request is not None else ""
