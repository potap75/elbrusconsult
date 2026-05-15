from django.contrib import admin

from .models import Service


@admin.register(Service)
class ServiceAdmin(admin.ModelAdmin):
    list_display = ("name", "order", "is_featured", "is_published", "updated_at")
    list_filter = ("is_featured", "is_published")
    list_editable = ("order", "is_featured", "is_published")
    search_fields = ("name", "tagline", "summary")
    prepopulated_fields = {"slug": ("name",)}
    fieldsets = (
        (None, {"fields": ("name", "slug", "icon", "order")}),
        ("Content", {"fields": ("tagline", "summary", "body_markdown")}),
        ("Flags", {"fields": ("is_featured", "is_published")}),
        ("SEO", {"fields": ("meta_description",)}),
    )
