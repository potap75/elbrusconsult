from django.contrib import admin

from .models import BookingInquiry


@admin.register(BookingInquiry)
class BookingInquiryAdmin(admin.ModelAdmin):
    list_display = (
        "name",
        "email",
        "service",
        "preferred_date",
        "created_at",
        "handled",
    )
    list_filter = ("handled", "service", "created_at")
    search_fields = ("name", "email", "company", "phone", "notes")
    readonly_fields = ("created_at", "updated_at", "ip_address", "user_agent")
    autocomplete_fields = ("service",)
    fieldsets = (
        ("Contact", {"fields": ("name", "email", "company", "phone")}),
        ("Request", {"fields": ("service", "preferred_date", "timezone_label", "notes")}),
        ("Triage", {"fields": ("handled",)}),
        ("Audit", {"fields": ("ip_address", "user_agent", "created_at", "updated_at")}),
    )
