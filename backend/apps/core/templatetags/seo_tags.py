"""Template tags for emitting JSON-LD blocks.

Usage::

    {% load seo_tags %}
    {% json_ld organization_schema %}

Where ``organization_schema`` is any dict / list. The tag emits a
``<script type="application/ld+json">`` block with safe JSON serialization.
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


@register.simple_tag
def json_ld(payload: Any) -> str:
    if not payload:
        return ""
    return mark_safe(
        f'<script type="application/ld+json">{_safe_json(payload)}</script>'
    )
