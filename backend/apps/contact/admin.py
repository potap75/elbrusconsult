from django.contrib import admin

from .models import ContactMessage


@admin.register(ContactMessage)
class ContactMessageAdmin(admin.ModelAdmin):
    list_display = ("name", "email", "subject", "submitted_at", "handled")
    list_filter = ("handled", "submitted_at")
    search_fields = ("name", "email", "company", "subject", "message")
    readonly_fields = (
        "submitted_at",
        "ip_address",
        "user_agent",
        "name",
        "email",
        "company",
        "subject",
        "message",
    )
    fieldsets = (
        ("Submission", {
            "fields": ("submitted_at", "name", "email", "company", "subject", "message"),
        }),
        ("Triage", {"fields": ("handled", "notes")}),
        ("Audit", {"fields": ("ip_address", "user_agent")}),
    )
