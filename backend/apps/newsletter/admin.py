from django.contrib import admin

from .models import Subscriber


@admin.register(Subscriber)
class SubscriberAdmin(admin.ModelAdmin):
    list_display = ("email", "status", "source", "created_at", "confirmed_at", "unsubscribed_at")
    list_filter = ("source", "created_at", "confirmed_at", "unsubscribed_at")
    search_fields = ("email", "source")
    readonly_fields = ("token", "created_at", "updated_at", "ip_address", "attribution")
