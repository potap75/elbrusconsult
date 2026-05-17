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
SITE_DOMAIN = env("SITE_DOMAIN", default="localhost:8000")
SITE_URL = env("SITE_URL", default="http://localhost:8000").rstrip("/")
SITE_DEFAULT_OG_IMAGE = env(
    "SITE_DEFAULT_OG_IMAGE", default="/static/img/og-default.png"
)
SITE_TWITTER_HANDLE = env("SITE_TWITTER_HANDLE", default="")
INFO_EMAIL = env("INFO_EMAIL", default="info@elbruscloud.example")
CONTACT_RECIPIENT_EMAIL = env("CONTACT_RECIPIENT_EMAIL", default=INFO_EMAIL)

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
    "whitenoise.middleware.WhiteNoiseMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
]

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
    {"NAME": "django.contrib.auth.password_validation.MinimumLengthValidator"},
    {"NAME": "django.contrib.auth.password_validation.CommonPasswordValidator"},
    {"NAME": "django.contrib.auth.password_validation.NumericPasswordValidator"},
]

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
