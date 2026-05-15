"""WSGI config for the Elbrus Cloud project."""
import os
import sys
from pathlib import Path

BACKEND_DIR = Path(__file__).resolve().parent.parent
APPS_DIR = BACKEND_DIR / "apps"
if str(APPS_DIR) not in sys.path:
    sys.path.insert(0, str(APPS_DIR))

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "elbrus.settings.prod")

from django.core.wsgi import get_wsgi_application  # noqa: E402

application = get_wsgi_application()
