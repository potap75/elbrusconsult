from django.contrib.sitemaps import Sitemap

from .models import Post


class BlogPostSitemap(Sitemap):
    changefreq = "weekly"
    priority = 0.6
    protocol = "https"

    def items(self):
        return Post.published.all()

    def lastmod(self, obj: Post):
        return obj.updated_at

    def location(self, obj: Post) -> str:
        return obj.get_absolute_url()
