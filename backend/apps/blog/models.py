"""Blog models: Category, Tag, Post."""
from __future__ import annotations

from django.conf import settings
from django.db import models
from django.urls import reverse
from django.utils import timezone
from django.utils.text import slugify

from core.sanitize import DEFAULT_MARKDOWN_EXTENSIONS, safe_html

MARKDOWN_EXTENSIONS = DEFAULT_MARKDOWN_EXTENSIONS


class Category(models.Model):
    name = models.CharField(max_length=80, unique=True)
    slug = models.SlugField(max_length=100, unique=True, blank=True)
    description = models.CharField(max_length=200, blank=True)

    class Meta:
        ordering = ["name"]
        verbose_name_plural = "Categories"

    def __str__(self) -> str:
        return self.name

    def save(self, *args, **kwargs) -> None:
        if not self.slug:
            self.slug = slugify(self.name)[:100]
        super().save(*args, **kwargs)

    def get_absolute_url(self) -> str:
        return reverse("blog-category", kwargs={"slug": self.slug})


class Tag(models.Model):
    name = models.CharField(max_length=50, unique=True)
    slug = models.SlugField(max_length=60, unique=True, blank=True)

    class Meta:
        ordering = ["name"]

    def __str__(self) -> str:
        return self.name

    def save(self, *args, **kwargs) -> None:
        if not self.slug:
            self.slug = slugify(self.name)[:60]
        super().save(*args, **kwargs)

    def get_absolute_url(self) -> str:
        return reverse("blog-tag", kwargs={"slug": self.slug})


class PublishedPostManager(models.Manager):
    def get_queryset(self):
        return (
            super()
            .get_queryset()
            .filter(status=Post.Status.PUBLISHED, published_at__lte=timezone.now())
        )


class Post(models.Model):
    class Status(models.TextChoices):
        DRAFT = "draft", "Draft"
        PUBLISHED = "published", "Published"

    title = models.CharField(max_length=200)
    slug = models.SlugField(max_length=220, unique=True, blank=True)
    excerpt = models.CharField(
        max_length=300,
        help_text="Short summary shown on listing pages and meta description default.",
    )
    body_markdown = models.TextField(help_text="Markdown body for the post.")
    body_html = models.TextField(blank=True, editable=False)

    hero_image = models.ImageField(upload_to="blog/heroes/", blank=True, null=True)
    hero_image_alt = models.CharField(
        max_length=200,
        blank=True,
        help_text="Alt text for the hero image. Required for accessibility & SEO.",
    )

    author = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        related_name="blog_posts",
    )
    category = models.ForeignKey(
        Category,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="posts",
    )
    tags = models.ManyToManyField(Tag, blank=True, related_name="posts")

    status = models.CharField(
        max_length=10, choices=Status.choices, default=Status.DRAFT
    )
    published_at = models.DateTimeField(blank=True, null=True)

    meta_description = models.CharField(max_length=180, blank=True)
    og_image = models.ImageField(upload_to="blog/og/", blank=True, null=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    objects = models.Manager()
    published = PublishedPostManager()

    class Meta:
        ordering = ["-published_at", "-created_at"]
        indexes = [
            models.Index(fields=["-published_at"]),
            models.Index(fields=["status", "-published_at"]),
        ]

    def __str__(self) -> str:
        return self.title

    def save(self, *args, **kwargs) -> None:
        if not self.slug:
            self.slug = slugify(self.title)[:220]
        if (
            self.status == self.Status.PUBLISHED
            and self.published_at is None
        ):
            self.published_at = timezone.now()
        self.body_html = safe_html(self.body_markdown, extensions=MARKDOWN_EXTENSIONS)
        super().save(*args, **kwargs)

    def get_absolute_url(self) -> str:
        return reverse("blog-detail", kwargs={"slug": self.slug})

    @property
    def seo_description(self) -> str:
        return self.meta_description or self.excerpt
