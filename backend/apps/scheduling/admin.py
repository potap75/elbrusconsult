from django.contrib import admin, messages
from django.utils import timezone

from .models import (
    AppointmentType,
    AvailabilityException,
    AvailabilityRule,
    Booking,
    BookingInquiry,
)
from .services.email import send_cancellation


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


@admin.register(AppointmentType)
class AppointmentTypeAdmin(admin.ModelAdmin):
    list_display = (
        "name",
        "duration_minutes",
        "buffer_after_minutes",
        "order",
        "is_active",
    )
    list_filter = ("is_active",)
    search_fields = ("name", "slug", "description")
    prepopulated_fields = {"slug": ("name",)}
    list_editable = ("order", "is_active")


@admin.register(AvailabilityRule)
class AvailabilityRuleAdmin(admin.ModelAdmin):
    list_display = ("weekday", "start_time", "end_time", "is_active")
    list_filter = ("weekday", "is_active")
    ordering = ("weekday", "start_time")


@admin.register(AvailabilityException)
class AvailabilityExceptionAdmin(admin.ModelAdmin):
    list_display = ("start_at", "end_at", "reason")
    list_filter = ("start_at",)
    search_fields = ("reason",)
    ordering = ("-start_at",)


@admin.action(description="Cancel selected bookings and email customers")
def cancel_selected_bookings(modeladmin, request, queryset):
    cancelled = 0
    for booking in queryset.filter(status=Booking.Status.CONFIRMED):
        booking.status = Booking.Status.CANCELLED
        booking.cancelled_at = timezone.now()
        booking.cancel_reason = booking.cancel_reason or "cancelled by staff"
        booking.save(
            update_fields=["status", "cancelled_at", "cancel_reason", "updated_at"]
        )
        try:
            send_cancellation(booking)
        except Exception:  # noqa: BLE001
            messages.warning(
                request, f"Cancelled #{booking.id} but failed to email {booking.email}."
            )
        cancelled += 1
    messages.success(request, f"Cancelled {cancelled} booking(s).")


@admin.register(Booking)
class BookingAdmin(admin.ModelAdmin):
    list_display = (
        "start_at",
        "appointment_type",
        "name",
        "email",
        "status",
        "created_at",
    )
    list_filter = ("status", "appointment_type", "start_at")
    search_fields = ("name", "email", "company", "phone", "notes")
    autocomplete_fields = ("appointment_type", "service")
    readonly_fields = (
        "manage_token",
        "rescheduled_from",
        "cancelled_at",
        "ip_address",
        "user_agent",
        "created_at",
        "updated_at",
    )
    date_hierarchy = "start_at"
    actions = [cancel_selected_bookings]
    fieldsets = (
        (
            "Meeting",
            {
                "fields": (
                    "appointment_type",
                    "service",
                    "start_at",
                    "end_at",
                    "customer_timezone",
                    "status",
                )
            },
        ),
        ("Customer", {"fields": ("name", "email", "company", "phone", "notes")}),
        (
            "Audit",
            {
                "fields": (
                    "manage_token",
                    "rescheduled_from",
                    "cancelled_at",
                    "cancel_reason",
                    "ip_address",
                    "user_agent",
                    "created_at",
                    "updated_at",
                )
            },
        ),
    )
