"""Blog views: list, detail, category/tag listings."""
from __future__ import annotations

from typing import Any

from django.conf import settings
from django.db.models import Q
from django.shortcuts import get_object_or_404
from django.views.generic import DetailView, ListView

from core.schema import breadcrumb_schema
from core.seo import SeoMixin

from .models import Category, Post, Tag


class BlogListView(SeoMixin, ListView):
    template_name = "blog/list.html"
    paginate_by = 10
    context_object_name = "posts"
    seo_title = "Blog"
    seo_description = (
        "Insights on cloud architecture, cybersecurity, identity, controls, "
        "and threat response from the Elbrus Cloud team."
    )

    def get_queryset(self):
        qs = Post.published.select_related("category", "author").prefetch_related("tags")
        query = self.request.GET.get("q", "").strip()
        if query:
            qs = qs.filter(
                Q(title__icontains=query)
                | Q(excerpt__icontains=query)
                | Q(body_markdown__icontains=query)
            )
        return qs

    def get_breadcrumbs(self) -> list[dict[str, str]]:
        return [
            {"name": "Home", "url": "/"},
            {"name": "Blog", "url": "/blog/"},
        ]

    def get_context_data(self, **kwargs: Any) -> dict[str, Any]:
        context = super().get_context_data(**kwargs)
        context["query"] = self.request.GET.get("q", "")
        context["categories"] = Category.objects.all()
        context["breadcrumb_schema"] = breadcrumb_schema(self.get_breadcrumbs())
        return context


class BlogDetailView(SeoMixin, DetailView):
    template_name = "blog/detail.html"
    context_object_name = "post"
    slug_url_kwarg = "slug"
    seo_og_type = "article"

    def get_queryset(self):
        return Post.published.select_related("category", "author").prefetch_related("tags")

    def get_seo_title(self) -> str:
        return self.object.title

    def get_seo_description(self) -> str:
        return self.object.seo_description

    def get_seo_og_image(self) -> str:
        if self.object.og_image:
            return self.object.og_image.url
        if self.object.hero_image:
            return self.object.hero_image.url
        return settings.SITE_DEFAULT_OG_IMAGE

    def get_breadcrumbs(self) -> list[dict[str, str]]:
        return [
            {"name": "Home", "url": "/"},
            {"name": "Blog", "url": "/blog/"},
            {"name": self.object.title, "url": self.object.get_absolute_url()},
        ]

    def _article_schema(self) -> dict:
        post = self.object
        image_url = self.get_seo_og_image()
        if image_url.startswith("/"):
            image_url = f"{settings.SITE_URL}{image_url}"
        author_name = post.author.get_full_name() if post.author else settings.SITE_NAME
        return {
            "@context": "https://schema.org",
            "@type": "Article",
            "headline": post.title,
            "description": post.seo_description,
            "image": [image_url],
            "datePublished": post.published_at.isoformat() if post.published_at else None,
            "dateModified": post.updated_at.isoformat(),
            "author": {"@type": "Person", "name": author_name or settings.SITE_NAME},
            "publisher": {
                "@type": "Organization",
                "name": settings.SITE_NAME,
                "logo": {
                    "@type": "ImageObject",
                    "url": f"{settings.SITE_URL}/static/img/logo.svg",
                },
            },
            "mainEntityOfPage": {
                "@type": "WebPage",
                "@id": f"{settings.SITE_URL}{post.get_absolute_url()}",
            },
        }

    def get_context_data(self, **kwargs: Any) -> dict[str, Any]:
        context = super().get_context_data(**kwargs)
        context["article_schema"] = self._article_schema()
        context["breadcrumb_schema"] = breadcrumb_schema(self.get_breadcrumbs())
        return context


class CategoryPostListView(BlogListView):
    template_name = "blog/list.html"

    def get_queryset(self):
        self.category = get_object_or_404(Category, slug=self.kwargs["slug"])
        return (
            Post.published.filter(category=self.category)
            .select_related("category", "author")
            .prefetch_related("tags")
        )

    def get_seo_title(self) -> str:
        return f"{self.category.name} - Blog"

    def get_seo_description(self) -> str:
        return self.category.description or super().get_seo_description()

    def get_breadcrumbs(self) -> list[dict[str, str]]:
        return [
            {"name": "Home", "url": "/"},
            {"name": "Blog", "url": "/blog/"},
            {"name": self.category.name, "url": self.category.get_absolute_url()},
        ]

    def get_context_data(self, **kwargs: Any) -> dict[str, Any]:
        context = super().get_context_data(**kwargs)
        context["current_category"] = self.category
        return context


class TagPostListView(BlogListView):
    template_name = "blog/list.html"

    def get_queryset(self):
        self.tag = get_object_or_404(Tag, slug=self.kwargs["slug"])
        return (
            Post.published.filter(tags=self.tag)
            .select_related("category", "author")
            .prefetch_related("tags")
        )

    def get_seo_title(self) -> str:
        return f"#{self.tag.name} - Blog"

    def get_breadcrumbs(self) -> list[dict[str, str]]:
        return [
            {"name": "Home", "url": "/"},
            {"name": "Blog", "url": "/blog/"},
            {"name": f"#{self.tag.name}", "url": self.tag.get_absolute_url()},
        ]

    def get_context_data(self, **kwargs: Any) -> dict[str, Any]:
        context = super().get_context_data(**kwargs)
        context["current_tag"] = self.tag
        return context
