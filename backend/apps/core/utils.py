"""Small shared helpers used across core apps."""
from __future__ import annotations

import re


def phone_tel_uri(display: str) -> str:
    """Convert a human-readable phone string to a ``tel:`` URI.

    Strips everything except digits and a leading ``+``. Returns an empty
    string when *display* is blank so templates can gate on truthiness.
    """
    if not display or not display.strip():
        return ""
    digits = re.sub(r"\D", "", display)
    if not digits:
        return ""
    return f"tel:+{digits}"
