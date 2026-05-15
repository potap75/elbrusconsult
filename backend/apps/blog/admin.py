from django.contrib import admin

from .models import Category, Post, Tag


@admin.register(Category)
class CategoryAdmin(admin.ModelAdmin):
    list_display = ("name", "slug")
    prepopulated_fields = {"slug": ("name",)}
    search_fields = ("name", "description")


@admin.register(Tag)
class TagAdmin(admin.ModelAdmin):
    list_display = ("name", "slug")
    prepopulated_fields = {"slug": ("name",)}
    search_fields = ("name",)


@admin.register(Post)
class PostAdmin(admin.ModelAdmin):
    list_display = ("title", "status", "category", "published_at", "updated_at")
    list_filter = ("status", "category", "tags")
    search_fields = ("title", "excerpt", "body_markdown")
    prepopulated_fields = {"slug": ("title",)}
    date_hierarchy = "published_at"
    autocomplete_fields = ("category", "tags", "author")
    fieldsets = (
        (None, {"fields": ("title", "slug", "excerpt", "body_markdown")}),
        ("Hero", {"fields": ("hero_image", "hero_image_alt")}),
        ("Taxonomy", {"fields": ("author", "category", "tags")}),
        ("Publishing", {"fields": ("status", "published_at")}),
        ("SEO", {"fields": ("meta_description", "og_image")}),
    )
