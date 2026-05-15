"""Development settings."""
from .base import *  # noqa: F401,F403
from .base import INSTALLED_APPS, MIDDLEWARE, env

DEBUG = True
ALLOWED_HOSTS = env(
    "DJANGO_ALLOWED_HOSTS",
    default=["localhost", "127.0.0.1", "0.0.0.0"],
)

# django-debug-toolbar (only when installed)
try:
    import debug_toolbar  # noqa: F401
except ImportError:
    pass
else:
    INSTALLED_APPS += ["debug_toolbar"]
    MIDDLEWARE.insert(
        0, "debug_toolbar.middleware.DebugToolbarMiddleware"
    )
    INTERNAL_IPS = ["127.0.0.1"]

# Always use the console email backend in dev so we never accidentally email
# people from a developer machine.
EMAIL_BACKEND = "django.core.mail.backends.console.EmailBackend"
