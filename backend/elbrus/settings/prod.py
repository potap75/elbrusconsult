"""Production settings (Azure VM + PostgreSQL Flexible Server)."""
from __future__ import annotations

from .base import *  # noqa: F401,F403
from .base import STORAGES, env

DEBUG = False

# Production-grade static files: hashed filenames + gzip/brotli, served by
# WhiteNoise. Requires `collectstatic` to be run before serving traffic.
STORAGES["staticfiles"] = {
    "BACKEND": "whitenoise.storage.CompressedManifestStaticFilesStorage",
}

# ----------------------------------------------------------------------------
# Security
# ----------------------------------------------------------------------------
SECURE_SSL_REDIRECT = env("DJANGO_SECURE_SSL_REDIRECT")
SESSION_COOKIE_SECURE = True
CSRF_COOKIE_SECURE = True
SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")

SECURE_HSTS_SECONDS = env("DJANGO_SECURE_HSTS_SECONDS")
SECURE_HSTS_INCLUDE_SUBDOMAINS = SECURE_HSTS_SECONDS > 0
SECURE_HSTS_PRELOAD = SECURE_HSTS_SECONDS > 0

SECURE_CONTENT_TYPE_NOSNIFF = True
SECURE_REFERRER_POLICY = "strict-origin-when-cross-origin"
X_FRAME_OPTIONS = "DENY"

# ----------------------------------------------------------------------------
# Sentry (optional)
# ----------------------------------------------------------------------------
SENTRY_DSN = env("SENTRY_DSN", default="")
if SENTRY_DSN:
    try:
        import sentry_sdk
        from sentry_sdk.integrations.django import DjangoIntegration

        sentry_sdk.init(
            dsn=SENTRY_DSN,
            integrations=[DjangoIntegration()],
            send_default_pii=False,
            traces_sample_rate=0.1,
        )
    except ImportError:
        pass
