"""Views for the scheduling placeholder page and its lead-capture API."""
from __future__ import annotations

import json
from typing import Any

from django.conf import settings
from django.core.mail import EmailMessage
from django.http import HttpRequest, HttpResponse, JsonResponse
from django.urls import reverse
from django.views.decorators.csrf import csrf_protect
from django.views.decorators.http import require_GET, require_POST
from django.views.generic import TemplateView

from core.schema import breadcrumb_schema
from core.seo import SeoMixin
from pages.models import Service

from .forms import BookingInquiryForm


def _get_client_ip(request: HttpRequest) -> str | None:
    xff = request.META.get("HTTP_X_FORWARDED_FOR")
    if xff:
        return xff.split(",")[0].strip()
    return request.META.get("REMOTE_ADDR")


class ScheduleView(SeoMixin, TemplateView):
    """Server-rendered page that hosts the React island."""

    template_name = "scheduling/index.html"
    seo_title = "Schedule a consultation"
    seo_description = (
        "Tell us about your project and pick a preferred time. We will follow up "
        "to confirm a meeting with a senior consultant."
    )

    def get_breadcrumbs(self) -> list[dict[str, str]]:
        return [
            {"name": "Home", "url": "/"},
            {"name": "Schedule", "url": "/schedule/"},
        ]

    def get_context_data(self, **kwargs: Any) -> dict[str, Any]:
        context = super().get_context_data(**kwargs)
        context["services_endpoint"] = reverse("scheduling-api-services")
        context["inquiry_endpoint"] = reverse("scheduling-api-inquiry")
        context["breadcrumb_schema"] = breadcrumb_schema(self.get_breadcrumbs())
        return context


@require_GET
def services_api(request: HttpRequest) -> JsonResponse:
    """Return published services so the React island can render a picker."""
    data = [
        {"id": s.id, "name": s.name, "slug": s.slug, "tagline": s.tagline}
        for s in Service.objects.filter(is_published=True)
    ]
    return JsonResponse({"services": data})


@csrf_protect
@require_POST
def inquiry_api(request: HttpRequest) -> HttpResponse:
    """Accept a booking inquiry from the React island (JSON payload)."""
    try:
        payload = json.loads(request.body.decode("utf-8"))
    except (ValueError, UnicodeDecodeError):
        return JsonResponse({"error": "Invalid JSON."}, status=400)

    form = BookingInquiryForm(payload)
    if not form.is_valid():
        return JsonResponse({"error": "validation_error", "fields": form.errors}, status=400)

    inquiry = form.save(commit=False)
    inquiry.ip_address = _get_client_ip(request)
    inquiry.user_agent = request.META.get("HTTP_USER_AGENT", "")[:500]
    inquiry.save()

    try:
        body = (
            f"New booking inquiry\n"
            f"---\n"
            f"Name:    {inquiry.name}\n"
            f"Email:   {inquiry.email}\n"
            f"Company: {inquiry.company or '-'}\n"
            f"Phone:   {inquiry.phone or '-'}\n"
            f"Service: {inquiry.service.name if inquiry.service else '-'}\n"
            f"Date:    {inquiry.preferred_date or '-'}\n"
            f"TZ:      {inquiry.timezone_label or '-'}\n"
            f"---\n"
            f"{inquiry.notes}\n"
        )
        EmailMessage(
            subject=f"[{settings.SITE_NAME}] Booking inquiry: {inquiry.name}",
            body=body,
            from_email=settings.DEFAULT_FROM_EMAIL,
            to=[settings.CONTACT_RECIPIENT_EMAIL],
            reply_to=[inquiry.email],
        ).send(fail_silently=True)
    except Exception:  # noqa: BLE001
        pass

    return JsonResponse({"ok": True, "id": inquiry.id})
