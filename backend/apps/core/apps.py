from django.apps import AppConfig

# Module import (not `from ... import AdminConfig`) so Django's app-config
# scan of this module doesn't see the stock AdminConfig class (default=True)
# as a candidate config for the "core" app.
from django.contrib.admin import apps as admin_apps


class CoreConfig(AppConfig):
    # Explicit default so Django picks this (not ElbrusAdminConfig below,
    # which inherits default=True from AdminConfig) for the plain "core"
    # INSTALLED_APPS entry.
    default = True
    default_auto_field = "django.db.models.BigAutoField"
    name = "core"
    verbose_name = "Core"


class ElbrusAdminConfig(admin_apps.AdminConfig):
    """Swaps the default admin site for the branded dashboard site.

    Referenced from ``INSTALLED_APPS`` in place of ``django.contrib.admin``.
    """

    default = False
    default_site = "core.admin_site.ElbrusAdminSite"
