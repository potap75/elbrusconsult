"""Custom admin site: Elbrus Cloud branding + operational dashboard.

Wired in via ``core.apps.ElbrusAdminConfig`` (which replaces
``django.contrib.admin`` in ``INSTALLED_APPS``), so every existing
``@admin.register(...)`` decorator keeps targeting the default site.
"""
from __future__ import annotations

from django.contrib import admin
from django.urls import reverse
from django.utils import timezone


class ElbrusAdminSite(admin.AdminSite):
    site_header = "Elbrus Cloud Admin"
    site_title = "Elbrus Cloud Admin"
    index_title = "Dashboard"
    # Rendered template extends the stock admin/index.html; using a distinct
    # name avoids the recursive template-loader trap of shadowing it in DIRS.
    index_template = "admin/elbrus_index.html"

    def index(self, request, extra_context=None):
        extra_context = extra_context or {}
        extra_context["dashboard_panels"] = self._dashboard_panels()
        return super().index(request, extra_context=extra_context)

    def _dashboard_panels(self) -> list[dict]:
        # Imported here (not at module level) because this module is loaded
        # while the app registry is still populating.
        from blog.models import Post
        from contact.models import ContactMessage
        from newsletter.models import Subscriber
        from scheduling.models import Booking, BookingInquiry

        now = timezone.now()

        def change_url(obj) -> str:
            return reverse(
                f"admin:{obj._meta.app_label}_{obj._meta.model_name}_change",
                args=[obj.pk],
                current_app=self.name,
            )

        def changelist_url(model, query: str = "") -> str:
            url = reverse(
                f"admin:{model._meta.app_label}_{model._meta.model_name}_changelist",
                current_app=self.name,
            )
            return f"{url}{query}"

        panels: list[dict] = []

        unhandled_messages = ContactMessage.objects.filter(handled=False)
        panels.append(
            {
                "title": "Unhandled contact messages",
                "count": unhandled_messages.count(),
                "changelist_url": changelist_url(
                    ContactMessage, "?handled__exact=0"
                ),
                "empty_label": "No unhandled messages.",
                "rows": [
                    {
                        "url": change_url(m),
                        "primary": f"{m.name} <{m.email}>",
                        "secondary": m.subject or m.message[:60],
                        "when": m.submitted_at,
                    }
                    for m in unhandled_messages[:5]
                ],
            }
        )

        upcoming_bookings = Booking.objects.filter(
            status=Booking.Status.CONFIRMED, start_at__gte=now
        ).order_by("start_at").select_related("appointment_type")
        panels.append(
            {
                "title": "Upcoming confirmed bookings",
                "count": upcoming_bookings.count(),
                "changelist_url": changelist_url(
                    Booking, "?status__exact=confirmed"
                ),
                "empty_label": "No upcoming bookings.",
                "rows": [
                    {
                        "url": change_url(b),
                        "primary": f"{b.name} - {b.appointment_type.name}",
                        "secondary": b.email,
                        "when": b.start_at,
                    }
                    for b in upcoming_bookings[:5]
                ],
            }
        )

        unhandled_inquiries = BookingInquiry.objects.filter(handled=False)
        panels.append(
            {
                "title": "Unhandled booking inquiries",
                "count": unhandled_inquiries.count(),
                "changelist_url": changelist_url(
                    BookingInquiry, "?handled__exact=0"
                ),
                "empty_label": "No unhandled inquiries.",
                "rows": [
                    {
                        "url": change_url(i),
                        "primary": f"{i.name} <{i.email}>",
                        "secondary": i.service.name if i.service_id else "General",
                        "when": i.created_at,
                    }
                    for i in unhandled_inquiries.select_related("service")[:5]
                ],
            }
        )

        recent_subscribers = Subscriber.objects.order_by("-created_at")
        confirmed_count = Subscriber.objects.filter(
            confirmed_at__isnull=False, unsubscribed_at__isnull=True
        ).count()
        panels.append(
            {
                "title": "Newsletter subscribers",
                "count": confirmed_count,
                "count_label": "confirmed",
                "changelist_url": changelist_url(Subscriber),
                "empty_label": "No subscribers yet.",
                "rows": [
                    {
                        "url": change_url(s),
                        "primary": s.email,
                        "secondary": s.status,
                        "when": s.created_at,
                    }
                    for s in recent_subscribers[:5]
                ],
            }
        )

        draft_posts = Post.objects.filter(status=Post.Status.DRAFT).order_by(
            "-updated_at"
        )
        panels.append(
            {
                "title": "Draft blog posts",
                "count": draft_posts.count(),
                "changelist_url": changelist_url(Post, "?status__exact=draft"),
                "empty_label": "No drafts.",
                "rows": [
                    {
                        "url": change_url(p),
                        "primary": p.title,
                        "secondary": p.category.name if p.category_id else "",
                        "when": p.updated_at,
                    }
                    for p in draft_posts.select_related("category")[:5]
                ],
            }
        )

        return panels
