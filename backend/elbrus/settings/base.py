"""Base Django settings for the Elbrus Cloud project.

Environment-specific tweaks live in ``dev.py`` and ``prod.py``; pick which one
loads via the ``DJANGO_SETTINGS_MODULE`` environment variable.
"""
from __future__ import annotations

import sys
from pathlib import Path

import environ

# ----------------------------------------------------------------------------
# Paths
# ----------------------------------------------------------------------------
# backend/elbrus/settings/base.py -> backend/
BACKEND_DIR = Path(__file__).resolve().parent.parent.parent
# repo root (one above backend/)
REPO_ROOT = BACKEND_DIR.parent

# Make `apps.*` importable as `core`, `pages`, etc. (matches manage.py).
APPS_DIR = BACKEND_DIR / "apps"
if str(APPS_DIR) not in sys.path:
    sys.path.insert(0, str(APPS_DIR))

# ----------------------------------------------------------------------------
# Environment
# ----------------------------------------------------------------------------
env = environ.Env(
    DJANGO_DEBUG=(bool, False),
    DJANGO_ALLOWED_HOSTS=(list, ["localhost", "127.0.0.1"]),
    DJANGO_SECURE_SSL_REDIRECT=(bool, False),
    DJANGO_SECURE_HSTS_SECONDS=(int, 0),
    DJANGO_CSRF_TRUSTED_ORIGINS=(list, []),
    EMAIL_USE_TLS=(bool, True),
    EMAIL_PORT=(int, 587),
)

# Load .env from the repo root if present (does not override real env vars).
env_file = REPO_ROOT / ".env"
if env_file.exists():
    environ.Env.read_env(str(env_file))

SECRET_KEY = env("DJANGO_SECRET_KEY", default="django-insecure-change-me-in-prod")
DEBUG = env("DJANGO_DEBUG")
ALLOWED_HOSTS = env("DJANGO_ALLOWED_HOSTS")
CSRF_TRUSTED_ORIGINS = env("DJANGO_CSRF_TRUSTED_ORIGINS")

# ----------------------------------------------------------------------------
# Site / SEO defaults (overridable per environment)
# ----------------------------------------------------------------------------
SITE_NAME = env("SITE_NAME", default="Elbrus Cloud")
SITE_TAGLINE = env(
    "SITE_TAGLINE", default="Cloud Engineering & Cybersecurity Excellence"
)
SITE_DOMAIN = env("SITE_DOMAIN", default="elbruscloud.com")
SITE_URL = env("SITE_URL", default="https://elbruscloud.com").rstrip("/")
SITE_DEFAULT_OG_IMAGE = env(
    "SITE_DEFAULT_OG_IMAGE", default="/static/img/og-default.png"
)
SITE_TWITTER_HANDLE = env("SITE_TWITTER_HANDLE", default="")
INFO_EMAIL = env("INFO_EMAIL", default="info@elbruscloud.com")
CONTACT_RECIPIENT_EMAIL = env("CONTACT_RECIPIENT_EMAIL", default=INFO_EMAIL)

# ----------------------------------------------------------------------------
# Analytics, Tag Manager & paid channels
# ----------------------------------------------------------------------------
# Every ID below is opt-in: when the env var is empty, the corresponding
# script tag is NOT rendered and no third-party request is made. This keeps
# dev / preview environments completely tracker-free by default and means a
# half-configured production deploy can't leak data to vendors.
#
# Strategy: GTM is the single source of truth for tag delivery in production.
# Direct GA4 (G-...) is supported as a fallback for environments that don't
# want to maintain a GTM container. When both are set, GTM wins and GA4
# fires through the GTM container instead of via gtag.js directly.
GTM_CONTAINER_ID = env("GTM_CONTAINER_ID", default="")           # GTM-XXXXXXX
GA4_MEASUREMENT_ID = env("GA4_MEASUREMENT_ID", default="")       # G-XXXXXXXXXX
GOOGLE_ADS_CONVERSION_ID = env(
    "GOOGLE_ADS_CONVERSION_ID", default=""
)                                                                 # AW-XXXXXXXXX
LINKEDIN_PARTNER_ID = env("LINKEDIN_PARTNER_ID", default="")
META_PIXEL_ID = env("META_PIXEL_ID", default="")
BING_UET_TAG_ID = env("BING_UET_TAG_ID", default="")
TIKTOK_PIXEL_ID = env("TIKTOK_PIXEL_ID", default="")

# Search-engine site verification meta tags (rendered into <head> only when set)
GOOGLE_SITE_VERIFICATION = env("GOOGLE_SITE_VERIFICATION", default="")
BING_SITE_VERIFICATION = env("BING_SITE_VERIFICATION", default="")

# Google Consent Mode v2 defaults. We default to denied everywhere
# (privacy-by-default; Consent Mode still lets Google Ads do conversion
# modeling). If you ever want implied consent outside specific regions,
# leave CONSENT_DEFAULT_DENY_REGIONS empty and set CONSENT_DEFAULT_GRANTED=True.
CONSENT_DEFAULT_GRANTED = env.bool("CONSENT_DEFAULT_GRANTED", default=False)
CONSENT_DEFAULT_DENY_REGIONS = env.list(
    "CONSENT_DEFAULT_DENY_REGIONS", default=[]
)

# ----------------------------------------------------------------------------
# Attribution (UTM / click-ID capture for paid channels)
# ----------------------------------------------------------------------------
# First-touch cookie lives this many days (industry standard ~ 90).
ATTRIBUTION_COOKIE_DAYS = env.int("ATTRIBUTION_COOKIE_DAYS", default=90)
ATTRIBUTION_FIRST_TOUCH_COOKIE = "elb_attr_first"
ATTRIBUTION_LAST_TOUCH_COOKIE = "elb_attr_last"

# ----------------------------------------------------------------------------
# Scheduling (booking calendar)
# ----------------------------------------------------------------------------
# Company timezone the weekly AvailabilityRule windows are interpreted in.
SCHEDULING_TIMEZONE = env.str("SCHEDULING_TIMEZONE", default="America/New_York")
# Customers cannot book a slot starting sooner than this many minutes from now.
SCHEDULING_MIN_LEAD_MINUTES = env.int("SCHEDULING_MIN_LEAD_MINUTES", default=120)
# Customers cannot book further out than this many days from today.
SCHEDULING_MAX_LEAD_DAYS = env.int("SCHEDULING_MAX_LEAD_DAYS", default=60)
# Slot start times are aligned to this granularity inside an availability window.
SCHEDULING_SLOT_GRANULARITY_MINUTES = env.int(
    "SCHEDULING_SLOT_GRANULARITY_MINUTES", default=15
)

# ----------------------------------------------------------------------------
# Application definition
# ----------------------------------------------------------------------------
DJANGO_APPS = [
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    "django.contrib.sitemaps",
    "django.contrib.sites",
    "django.contrib.syndication",
]

THIRD_PARTY_APPS = [
    "robots",
    "axes",
]

LOCAL_APPS = [
    "core",
    "pages",
    "blog",
    "contact",
    "newsletter",
    "scheduling",
]

INSTALLED_APPS = DJANGO_APPS + THIRD_PARTY_APPS + LOCAL_APPS

SITE_ID = 1

# django-robots: emit sitemap URL in robots.txt, allow all crawlers by default.
ROBOTS_USE_SITEMAP = True
ROBOTS_USE_HOST = False
ROBOTS_SITEMAP_URLS = [f"{SITE_URL}/sitemap.xml"]

MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    # SecurityHeadersMiddleware MUST run early so it can attach a per-request
    # CSP nonce to the request BEFORE templates render. The CSP header itself
    # is set on the response on the way back out (default-setdefault, so
    # other layers can override).
    "core.middleware.SecurityHeadersMiddleware",
    "whitenoise.middleware.WhiteNoiseMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
    # AttributionMiddleware reads ?utm_*/gclid/fbclid/li_fat_id/ttclid/msclkid
    # from the request and persists first/last-touch attribution cookies.
    # It must run AFTER SessionMiddleware (no session dep today, but cheap
    # insurance) and BEFORE any view that wants to read the attribution
    # snapshot off the request.
    "core.middleware.AttributionMiddleware",
    # django-axes must be the LAST middleware in the stack so that it sees
    # the request after authentication has populated request.user.
    "axes.middleware.AxesMiddleware",
    # Renders Ratelimited exceptions via RATELIMIT_VIEW.
    "django_ratelimit.middleware.RatelimitMiddleware",
]

# When a view raises django_ratelimit.exceptions.Ratelimited (block=True),
# RatelimitMiddleware routes the request to this view instead of the
# default 403 page.
RATELIMIT_VIEW = "core.views.ratelimited"

ROOT_URLCONF = "elbrus.urls"

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [BACKEND_DIR / "templates"],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.debug",
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
                "core.context_processors.site_context",
                "core.context_processors.analytics_context",
            ],
        },
    },
]

WSGI_APPLICATION = "elbrus.wsgi.application"
ASGI_APPLICATION = "elbrus.asgi.application"

# ----------------------------------------------------------------------------
# Database
# ----------------------------------------------------------------------------
# Default to SQLite when no DATABASE_URL is provided (handy for local dev).
DATABASES = {
    "default": env.db_url(
        "DATABASE_URL",
        default=f"sqlite:///{BACKEND_DIR / 'db.sqlite3'}",
    )
}

# ----------------------------------------------------------------------------
# Password validation
# ----------------------------------------------------------------------------
AUTH_PASSWORD_VALIDATORS = [
    {"NAME": "django.contrib.auth.password_validation.UserAttributeSimilarityValidator"},
    {
        "NAME": "django.contrib.auth.password_validation.MinimumLengthValidator",
        "OPTIONS": {"min_length": 12},
    },
    {"NAME": "django.contrib.auth.password_validation.CommonPasswordValidator"},
    {"NAME": "django.contrib.auth.password_validation.NumericPasswordValidator"},
]

# ----------------------------------------------------------------------------
# Security headers / cookies (env-agnostic safe defaults)
# ----------------------------------------------------------------------------
# Cookies: never expose to JS; default to Lax so normal top-level form posts
# still work. prod.py tightens to "Strict".
SESSION_COOKIE_HTTPONLY = True
CSRF_COOKIE_HTTPONLY = True
SESSION_COOKIE_SAMESITE = "Lax"
CSRF_COOKIE_SAMESITE = "Lax"

# These are safe to set unconditionally (no HTTPS dependency).
SECURE_CONTENT_TYPE_NOSNIFF = True
SECURE_REFERRER_POLICY = "strict-origin-when-cross-origin"
X_FRAME_OPTIONS = "DENY"

# Cap inbound request bodies and individual file uploads at 5 MB. The Nginx
# `client_max_body_size` is 25 MB; this is the Django-side belt to that
# suspenders so a single malicious request can't tie up a Gunicorn worker
# reading hundreds of MB.
DATA_UPLOAD_MAX_MEMORY_SIZE = 5 * 1024 * 1024
FILE_UPLOAD_MAX_MEMORY_SIZE = 5 * 1024 * 1024

# ----------------------------------------------------------------------------
# Authentication / brute-force protection (django-axes)
# ----------------------------------------------------------------------------
# AxesStandaloneBackend must come BEFORE Django's ModelBackend so that
# axes can short-circuit lockouts before normal auth runs.
AUTHENTICATION_BACKENDS = [
    "axes.backends.AxesStandaloneBackend",
    "django.contrib.auth.backends.ModelBackend",
]

# Lock an attacker out after 5 failed admin logins, per (IP + username),
# for 1 hour. A successful login from that IP clears the counter.
AXES_FAILURE_LIMIT = 5
AXES_COOLOFF_TIME = 1
AXES_LOCKOUT_PARAMETERS = [["ip_address", "username"]]
AXES_RESET_ON_SUCCESS = True
# Trust nginx's X-Forwarded-For (rightmost entry) so the lockout key is
# the real client IP. See core.net.get_client_ip for the same logic.
AXES_IPWARE_PROXY_COUNT = 1
AXES_IPWARE_META_PRECEDENCE_ORDER = ["HTTP_X_FORWARDED_FOR", "REMOTE_ADDR"]

# ----------------------------------------------------------------------------
# Internationalization
# ----------------------------------------------------------------------------
LANGUAGE_CODE = "en-us"
TIME_ZONE = "UTC"
USE_I18N = True
USE_TZ = True

# ----------------------------------------------------------------------------
# Static & media files
# ----------------------------------------------------------------------------
STATIC_URL = "/static/"
STATICFILES_DIRS = [BACKEND_DIR / "static"]
STATIC_ROOT = BACKEND_DIR / "staticfiles"

MEDIA_URL = "/media/"
MEDIA_ROOT = BACKEND_DIR / "media"

STORAGES = {
    "default": {
        "BACKEND": "django.core.files.storage.FileSystemStorage",
    },
    "staticfiles": {
        # Dev-friendly default (no manifest). prod.py swaps in WhiteNoise's
        # CompressedManifestStaticFilesStorage after collectstatic runs.
        "BACKEND": "django.contrib.staticfiles.storage.StaticFilesStorage",
    },
}

# ----------------------------------------------------------------------------
# Email
# ----------------------------------------------------------------------------
EMAIL_HOST = env("EMAIL_HOST", default="")
EMAIL_PORT = env("EMAIL_PORT")
EMAIL_HOST_USER = env("EMAIL_HOST_USER", default="")
EMAIL_HOST_PASSWORD = env("EMAIL_HOST_PASSWORD", default="")
EMAIL_USE_TLS = env("EMAIL_USE_TLS")
DEFAULT_FROM_EMAIL = env(
    "DEFAULT_FROM_EMAIL",
    default=f"{SITE_NAME} <no-reply@elbruscloud.example>",
)
SERVER_EMAIL = DEFAULT_FROM_EMAIL

if EMAIL_HOST:
    EMAIL_BACKEND = "django.core.mail.backends.smtp.EmailBackend"
else:
    EMAIL_BACKEND = "django.core.mail.backends.console.EmailBackend"

# ----------------------------------------------------------------------------
# Defaults & misc
# ----------------------------------------------------------------------------
DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

# Reasonable logging defaults; environment-specific files may extend this.
LOGGING = {
    "version": 1,
    "disable_existing_loggers": False,
    "formatters": {
        "verbose": {
            "format": "[{asctime}] {levelname} {name} :: {message}",
            "style": "{",
        },
    },
    "handlers": {
        "console": {
            "class": "logging.StreamHandler",
            "formatter": "verbose",
        },
    },
    "root": {
        "handlers": ["console"],
        "level": "INFO",
    },
    "loggers": {
        "django": {
            "handlers": ["console"],
            "level": "INFO",
            "propagate": False,
        },
    },
}
