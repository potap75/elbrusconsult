from django.contrib.sitemaps import Sitemap

from .models import Service


class ServiceSitemap(Sitemap):
    changefreq = "monthly"
    priority = 0.7
    protocol = "https"

    def items(self):
        return Service.objects.filter(is_published=True)

    def lastmod(self, obj: Service):
        return obj.updated_at

    def location(self, obj: Service) -> str:
        return obj.get_absolute_url()
