"""Top-level URL configuration for Elbrus Cloud."""
from __future__ import annotations

from django.conf import settings
from django.conf.urls.static import static
from django.contrib import admin
from django.contrib.sitemaps.views import sitemap
from django.urls import include, path
from django.views.generic import TemplateView

from blog.feeds import LatestPostsFeed
from blog.sitemaps import BlogPostSitemap
from core.sitemaps import StaticViewSitemap
from pages.sitemaps import ServiceSitemap

sitemaps = {
    "static": StaticViewSitemap,
    "services": ServiceSitemap,
    "blog": BlogPostSitemap,
}

urlpatterns = [
    path("admin/", admin.site.urls),
    path("", include("pages.urls")),
    path("blog/", include("blog.urls")),
    path("contact/", include("contact.urls")),
    path("newsletter/", include("newsletter.urls")),
    path("schedule/", include("scheduling.urls")),
    # SEO
    path("sitemap.xml", sitemap, {"sitemaps": sitemaps}, name="sitemap"),
    path("robots.txt", include("robots.urls")),
    path("feed/", LatestPostsFeed(), name="blog-feed"),
    # Health
    path(
        "healthz",
        TemplateView.as_view(
            template_name="healthz.txt", content_type="text/plain"
        ),
        name="healthz",
    ),
]

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
    try:
        import debug_toolbar  # noqa: F401

        urlpatterns += [path("__debug__/", include("debug_toolbar.urls"))]
    except ImportError:
        pass
