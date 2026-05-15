"""RSS feed for the latest blog posts."""
from __future__ import annotations

from django.conf import settings
from django.contrib.syndication.views import Feed
from django.urls import reverse

from .models import Post


class LatestPostsFeed(Feed):
    title = f"{settings.SITE_NAME} - Blog"
    link = "/blog/"
    description = "Latest insights on cloud architecture and cybersecurity."

    def __call__(self, request, *args, **kwargs):
        # Refresh title each call so SITE_NAME tweaks reflect immediately.
        self.title = f"{settings.SITE_NAME} - Blog"
        return super().__call__(request, *args, **kwargs)

    def items(self):
        return Post.published.all()[:20]

    def item_title(self, item: Post) -> str:
        return item.title

    def item_description(self, item: Post) -> str:
        return item.excerpt

    def item_link(self, item: Post) -> str:
        return item.get_absolute_url()

    def item_pubdate(self, item: Post):
        return item.published_at

    def item_author_name(self, item: Post) -> str:
        if item.author:
            return item.author.get_full_name() or item.author.get_username()
        return settings.SITE_NAME
