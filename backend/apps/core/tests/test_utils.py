"""Tests for core.utils helpers."""
from __future__ import annotations

from core.utils import phone_tel_uri


def test_phone_tel_uri_formats_us_number():
    assert phone_tel_uri("+1 (704) 686-8481") == "tel:+17046868481"


def test_phone_tel_uri_returns_empty_for_blank():
    assert phone_tel_uri("") == ""
    assert phone_tel_uri("   ") == ""
