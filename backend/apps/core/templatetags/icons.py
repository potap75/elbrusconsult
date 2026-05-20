"""Inline SVG icon template tag.

Renders Heroicons (v2 outline, 24x24) inline so we can:

* Style them with Tailwind utilities (``stroke="currentColor"``).
* Avoid an extra HTTP request per icon.
* Keep the markup CSP-safe (no external script / font hosting an icon set).

Usage::

    {% load icons %}
    {% heroicon "shield-check" class="h-6 w-6 text-summit-600" %}
    {% heroicon "lock-closed" class="h-7 w-7" aria_label="Encryption at rest" %}

The ``class`` argument is dropped onto the wrapping ``<svg>``. ``aria_label``
promotes the icon from decorative (``aria-hidden="true"``) to semantic
(``role="img"`` + ``<title>``). Unknown names render a neutral fallback
glyph and emit a stdlib ``logging`` warning - we never raise so a stale
``Service.icon`` value in the DB can never take the page down.

The icon body markup (just the inner ``<path>``) is the verbatim output of
the official Heroicons v2 outline set
(https://github.com/tailwindlabs/heroicons, ``optimized/24/outline``).
"""
from __future__ import annotations

import logging
from typing import Optional

from django import template
from django.utils.html import conditional_escape
from django.utils.safestring import mark_safe

register = template.Library()

logger = logging.getLogger(__name__)


# Inner SVG bodies for the Heroicons we actually use across the site.
# Keep this set tight: every entry must be a verbatim copy of the
# corresponding ``optimized/24/outline/<name>.svg`` inner markup from
# https://github.com/tailwindlabs/heroicons. To add a new icon, drop in
# the inner ``<path>`` (or ``<rect>``) tags exactly as published; the
# surrounding ``<svg>`` is supplied by ``heroicon`` below.
_HEROICONS: dict[str, str] = {
    "cloud": (
        '<path stroke-linecap="round" stroke-linejoin="round" '
        'd="M2.25 15a4.5 4.5 0 0 0 4.5 4.5H18a3.75 3.75 0 0 0 1.332-7.257 '
        "3 3 0 0 0-3.758-3.848 5.25 5.25 0 0 0-10.233 2.33A4.502 4.502 0 0 0 "
        '2.25 15Z"/>'
    ),
    "shield-check": (
        '<path stroke-linecap="round" stroke-linejoin="round" '
        'd="M9 12.75 11.25 15 15 9.75m-3-7.036A11.959 11.959 0 0 1 3.598 6 '
        "11.99 11.99 0 0 0 3 9.749c0 5.592 3.824 10.29 9 11.623 5.176-1.332 "
        "9-6.03 9-11.622 0-1.31-.21-2.571-.598-3.751h-.152c-3.196 0-6.1-1.248-"
        '8.25-3.285Z"/>'
    ),
    "shield-exclamation": (
        '<path stroke-linecap="round" stroke-linejoin="round" '
        'd="M12 9v3.75m0-10.036A11.959 11.959 0 0 1 3.598 6 11.99 11.99 0 0 0 '
        "3 9.75c0 5.592 3.824 10.29 9 11.622 5.176-1.332 9-6.03 9-11.622 "
        "0-1.31-.21-2.57-.598-3.75h-.152c-3.196 0-6.1-1.25-8.25-3.286Zm0 "
        '13.036h.008v.008H12v-.008Z"/>'
    ),
    "key": (
        '<path stroke-linecap="round" stroke-linejoin="round" '
        'd="M15.75 5.25a3 3 0 0 1 3 3m3 0a6 6 0 0 1-7.029 5.912c-.563-.097-'
        "1.159.026-1.563.43L10.5 17.25H8.25v2.25H6v2.25H2.25v-2.818c0-.597"
        ".237-1.17.659-1.591l6.499-6.499c.404-.404.527-1 .43-1.563A6 6 0 1 "
        '1 21.75 8.25Z"/>'
    ),
    "lock-closed": (
        '<path stroke-linecap="round" stroke-linejoin="round" '
        'd="M16.5 10.5V6.75a4.5 4.5 0 1 0-9 0v3.75m-.75 11.25h10.5a2.25 2.25 '
        "0 0 0 2.25-2.25v-6.75a2.25 2.25 0 0 0-2.25-2.25H6.75a2.25 2.25 0 0 "
        '0-2.25 2.25v6.75a2.25 2.25 0 0 0 2.25 2.25Z"/>'
    ),
    "adjustments-horizontal": (
        '<path stroke-linecap="round" stroke-linejoin="round" '
        'd="M10.5 6h9.75M10.5 6a1.5 1.5 0 1 1-3 0m3 0a1.5 1.5 0 1 0-3 0M3.75 '
        "6H7.5m3 12h9.75m-9.75 0a1.5 1.5 0 0 1-3 0m3 0a1.5 1.5 0 0 0-3 "
        "0m-3.75 0H7.5m9-6h3.75m-3.75 0a1.5 1.5 0 0 1-3 0m3 0a1.5 1.5 0 0 "
        '0-3 0m-9.75 0h9.75"/>'
    ),
    "beaker": (
        '<path stroke-linecap="round" stroke-linejoin="round" '
        'd="M9.75 3.104v5.714a2.25 2.25 0 0 1-.659 1.591L5 14.5M9.75 3.104c-'
        ".251.023-.501.05-.75.082m.75-.082a24.301 24.301 0 0 1 4.5 0m0 0v5.714c"
        "0 .597.237 1.17.659 1.591L19.8 15.3M14.25 3.104c.251.023.501.05.75."
        "082M19.8 15.3l-1.57.393A9.065 9.065 0 0 1 12 15a9.065 9.065 0 0 0-6"
        ".23-.693L5 14.5m14.8.8 1.402 1.402c1.232 1.232.65 3.318-1.067 "
        "3.611A48.309 48.309 0 0 1 12 21c-2.773 0-5.491-.235-8.135-.687-1.718-"
        '.293-2.3-2.379-1.067-3.61L5 14.5"/>'
    ),
    "magnifying-glass": (
        '<path stroke-linecap="round" stroke-linejoin="round" '
        'd="m21 21-5.197-5.197m0 0A7.5 7.5 0 1 0 5.196 5.196a7.5 7.5 0 0 0 '
        '10.607 10.607Z"/>'
    ),
    "finger-print": (
        '<path stroke-linecap="round" stroke-linejoin="round" '
        'd="M7.864 4.243A7.5 7.5 0 0 1 19.5 10.5c0 2.92-.556 5.709-1.568 '
        "8.268M5.742 6.364A7.465 7.465 0 0 0 4.5 10.5a7.464 7.464 0 0 1-1.15 "
        "3.993m1.989 3.559A11.209 11.209 0 0 0 8.25 10.5a3.75 3.75 0 1 1 7.5 "
        "0c0 .527-.021 1.049-.064 1.565M12 10.5a14.94 14.94 0 0 1-3.6 "
        '9.75m6.633-4.596a18.666 18.666 0 0 1-2.485 5.33"/>'
    ),
    "arrow-path": (
        '<path stroke-linecap="round" stroke-linejoin="round" '
        'd="M16.023 9.348h4.992v-.001M2.985 19.644v-4.992m0 0h4.992m-4.993 0 '
        "3.181 3.183a8.25 8.25 0 0 0 13.803-3.7M4.031 9.865a8.25 8.25 0 0 1 "
        '13.803-3.7l3.181 3.182m0-4.991v4.99"/>'
    ),
    "code-bracket": (
        '<path stroke-linecap="round" stroke-linejoin="round" '
        'd="M17.25 6.75 22.5 12l-5.25 5.25m-10.5 0L1.5 12l5.25-5.25m7.5-3-4.5 '
        '16.5"/>'
    ),
    "server-stack": (
        '<path stroke-linecap="round" stroke-linejoin="round" '
        'd="M5.25 14.25h13.5m-13.5 0a3 3 0 0 1-3-3m3 3a3 3 0 1 0 0 6h13.5a3 3 '
        "0 1 0 0-6m-16.5-3a3 3 0 0 1 3-3h13.5a3 3 0 0 1 3 3m-19.5 0a4.5 4.5 0 "
        "0 1 .9-2.7L5.737 5.1a3.375 3.375 0 0 1 2.7-1.35h7.126c1.062 0 2.062.5 "
        "2.7 1.35l2.587 3.45a4.5 4.5 0 0 1 .9 2.7m0 0a3 3 0 0 1-3 3m0 "
        "3h.008v.008h-.008v-.008Zm0-6h.008v.008h-.008v-.008Zm-3 "
        '6h.008v.008h-.008v-.008Zm0-6h.008v.008h-.008v-.008Z"/>'
    ),
    "cpu-chip": (
        '<path stroke-linecap="round" stroke-linejoin="round" '
        'd="M8.25 3v1.5M4.5 8.25H3m18 0h-1.5M4.5 12H3m18 0h-1.5m-15 3.75H3m18 '
        "0h-1.5M8.25 19.5V21M12 3v1.5m0 15V21m3.75-18v1.5m0 15V21m-9-1.5h10.5"
        "a2.25 2.25 0 0 0 2.25-2.25V6.75a2.25 2.25 0 0 0-2.25-2.25H6.75A2.25 "
        "2.25 0 0 0 4.5 6.75v10.5a2.25 2.25 0 0 0 2.25 2.25Zm.75-12h9v9h-9v-"
        '9Z"/>'
    ),
    "chart-bar": (
        '<path stroke-linecap="round" stroke-linejoin="round" '
        'd="M3 13.125C3 12.504 3.504 12 4.125 12h2.25c.621 0 1.125.504 1.125 '
        "1.125v6.75C7.5 20.496 6.996 21 6.375 21h-2.25A1.125 1.125 0 0 1 3 "
        "19.875v-6.75ZM9.75 8.625c0-.621.504-1.125 1.125-1.125h2.25c.621 0 "
        "1.125.504 1.125 1.125v11.25c0 .621-.504 1.125-1.125 1.125h-2.25a1.125 "
        "1.125 0 0 1-1.125-1.125V8.625ZM16.5 4.125c0-.621.504-1.125 1.125-"
        "1.125h2.25C20.496 3 21 3.504 21 4.125v15.75c0 .621-.504 1.125-1.125 "
        '1.125h-2.25a1.125 1.125 0 0 1-1.125-1.125V4.125Z"/>'
    ),
    "sparkles": (
        '<path stroke-linecap="round" stroke-linejoin="round" '
        'd="M9.813 15.904 9 18.75l-.813-2.846a4.5 4.5 0 0 0-3.09-3.09L2.25 12l'
        "2.846-.813a4.5 4.5 0 0 0 3.09-3.09L9 5.25l.813 2.846a4.5 4.5 0 0 0 "
        "3.09 3.09L15.75 12l-2.846.813a4.5 4.5 0 0 0-3.09 3.09ZM18.259 8.715 "
        "18 9.75l-.259-1.035a3.375 3.375 0 0 0-2.455-2.456L14.25 6l1.036-.259a"
        "3.375 3.375 0 0 0 2.455-2.456L18 2.25l.259 1.035a3.375 3.375 0 0 0 "
        "2.456 2.456L21.75 6l-1.035.259a3.375 3.375 0 0 0-2.456 2.456ZM16.894 "
        "20.567 16.5 21.75l-.394-1.183a2.25 2.25 0 0 0-1.423-1.423L13.5 18.75l"
        "1.183-.394a2.25 2.25 0 0 0 1.423-1.423l.394-1.183.394 1.183a2.25 "
        "2.25 0 0 0 1.423 1.423l1.183.394-1.183.394a2.25 2.25 0 0 0-1.423 "
        '1.423Z"/>'
    ),
}

# Neutral fallback (a small dot inside the circle of "questionable but
# safe" - rendered when the requested name is missing from the registry).
_FALLBACK_ICON = (
    '<path stroke-linecap="round" stroke-linejoin="round" '
    'd="M12 21a9 9 0 1 1 0-18 9 9 0 0 1 0 18Zm0-9.75h.008v.008H12v-.008Z"/>'
)


@register.simple_tag
def heroicon(
    name: str,
    *,
    class_: str = "",
    aria_label: Optional[str] = None,
    **kwargs: str,
) -> str:
    """Render a Heroicon as inline SVG.

    Arguments:
        name: Heroicon identifier (e.g. ``"shield-check"``). Unknown names
            fall back to a neutral glyph and log a warning.
        class_ (alias ``class``): CSS classes to apply to the ``<svg>``.
            Tailwind ``stroke="currentColor"`` lets a parent's text color
            drive the icon's stroke color.
        aria_label: When set, the icon is rendered with ``role="img"`` and
            an inner ``<title>``, making it semantically meaningful to
            assistive tech. When omitted (the default), the icon is marked
            ``aria-hidden="true"`` because the brand convention is that the
            icon decorates a heading that already carries the meaning.
    """
    # Django's simple_tag rejects ``class`` as a kwarg name (it's a Python
    # keyword), so we accept either ``class`` (preferred at the template
    # boundary, via **kwargs) or ``class_`` (Python-friendly).
    css_class = kwargs.pop("class", class_) or ""
    if kwargs:
        logger.warning(
            "heroicon: ignoring unexpected kwargs %s for icon %r",
            sorted(kwargs),
            name,
        )

    body = _HEROICONS.get(name)
    if body is None:
        logger.warning(
            "heroicon: unknown icon name %r - rendering fallback glyph", name
        )
        body = _FALLBACK_ICON

    # All user-controlled bits get escaped. The body markup is a constant
    # from our own registry, not user input, so it is safe to inline.
    css_attr = (
        f' class="{conditional_escape(css_class)}"' if css_class else ""
    )
    if aria_label:
        a11y = (
            f' role="img" aria-label="{conditional_escape(aria_label)}"'
        )
        title = f"<title>{conditional_escape(aria_label)}</title>"
    else:
        a11y = ' aria-hidden="true"'
        title = ""

    return mark_safe(
        '<svg xmlns="http://www.w3.org/2000/svg" fill="none" '
        'viewBox="0 0 24 24" stroke-width="1.5" stroke="currentColor"'
        f"{css_attr}{a11y}>{title}{body}</svg>"
    )
