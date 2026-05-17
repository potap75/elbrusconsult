"""Views for the scheduling page, REST-style booking API, and manage page.

Two parallel paths live here:

* Legacy lead-capture (``BookingInquiry``): ``services_api`` + ``inquiry_api``,
  kept for backward compatibility with the old island UI and tests.
* Real booking calendar: ``appointment_types_api``, ``slots_api``,
  ``bookings_api``, plus the server-rendered ``manage_booking`` view.
"""
from __future__ import annotations

import json
import logging
from datetime import date, datetime, timedelta, timezone
from typing import Any
from uuid import UUID

from django.conf import settings
from django.core.mail import EmailMessage
from django.db import IntegrityError, transaction
from django.http import (
    Http404,
    HttpRequest,
    HttpResponse,
    HttpResponseNotAllowed,
    JsonResponse,
)
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils import timezone as djtz
from django.views.decorators.csrf import csrf_protect
from django.views.decorators.http import require_GET, require_POST
from django.views.generic import TemplateView

from core.schema import breadcrumb_schema
from core.seo import SeoMixin
from pages.models import Service

from .forms import BookingInquiryForm
from .models import AppointmentType, Booking
from .services.email import send_cancellation, send_confirmation, send_reschedule
from .services.slots import generate_slots, slot_is_available

logger = logging.getLogger(__name__)

MAX_RANGE_DAYS = 90


def _get_client_ip(request: HttpRequest) -> str | None:
    xff = request.META.get("HTTP_X_FORWARDED_FOR")
    if xff:
        return xff.split(",")[0].strip()
    return request.META.get("REMOTE_ADDR")


class ScheduleView(SeoMixin, TemplateView):
    """Server-rendered page that hosts the React booking island."""

    template_name = "scheduling/index.html"
    seo_title = "Book a consultation"
    seo_description = (
        "Pick a time that works for you and book a video consultation with a "
        "senior Elbrus Cloud consultant."
    )

    def get_breadcrumbs(self) -> list[dict[str, str]]:
        return [
            {"name": "Home", "url": "/"},
            {"name": "Schedule", "url": "/schedule/"},
        ]

    def get_context_data(self, **kwargs: Any) -> dict[str, Any]:
        context = super().get_context_data(**kwargs)
        context.update(
            {
                "appointment_types_endpoint": reverse(
                    "scheduling-api-appointment-types"
                ),
                "slots_endpoint": reverse("scheduling-api-slots"),
                "bookings_endpoint": reverse("scheduling-api-bookings"),
                "booking_lookup_endpoint": reverse("scheduling-api-booking-lookup"),
                "services_endpoint": reverse("scheduling-api-services"),
                "inquiry_endpoint": reverse("scheduling-api-inquiry"),
                "default_timezone": getattr(
                    settings, "SCHEDULING_TIMEZONE", "UTC"
                ),
                "breadcrumb_schema": breadcrumb_schema(self.get_breadcrumbs()),
            }
        )
        return context


# ----------------------------------------------------------------------------
# Legacy lead-capture endpoints (kept for backward compatibility)
# ----------------------------------------------------------------------------


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
    """Accept a 'no specific time' booking inquiry (JSON payload)."""
    try:
        payload = json.loads(request.body.decode("utf-8"))
    except (ValueError, UnicodeDecodeError):
        return JsonResponse({"error": "Invalid JSON."}, status=400)

    form = BookingInquiryForm(payload)
    if not form.is_valid():
        return JsonResponse(
            {"error": "validation_error", "fields": form.errors}, status=400
        )

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


# ----------------------------------------------------------------------------
# Real booking calendar
# ----------------------------------------------------------------------------


@require_GET
def appointment_types_api(request: HttpRequest) -> JsonResponse:
    """Return active appointment types for the picker UI."""
    types = AppointmentType.objects.filter(is_active=True)
    return JsonResponse(
        {
            "appointment_types": [
                {
                    "slug": t.slug,
                    "name": t.name,
                    "duration_minutes": t.duration_minutes,
                    "description": t.description,
                    "location_instructions": t.location_instructions,
                }
                for t in types
            ]
        }
    )


def _parse_date(raw: str | None) -> date | None:
    if not raw:
        return None
    try:
        return datetime.strptime(raw, "%Y-%m-%d").date()
    except ValueError:
        return None


@require_GET
def slots_api(request: HttpRequest) -> JsonResponse:
    """Return UTC ISO-8601 slot start times for an appointment type and date range."""
    type_slug = request.GET.get("type")
    date_from = _parse_date(request.GET.get("from"))
    date_to = _parse_date(request.GET.get("to"))
    if not type_slug or not date_from or not date_to:
        return JsonResponse(
            {"error": "Required query params: type, from (YYYY-MM-DD), to (YYYY-MM-DD)."},
            status=400,
        )
    if date_to < date_from:
        return JsonResponse({"error": "'to' must not precede 'from'."}, status=400)
    if (date_to - date_from).days > MAX_RANGE_DAYS:
        return JsonResponse(
            {"error": f"Range cannot exceed {MAX_RANGE_DAYS} days."}, status=400
        )

    appointment_type = AppointmentType.objects.filter(
        slug=type_slug, is_active=True
    ).first()
    if appointment_type is None:
        return JsonResponse({"error": "Unknown appointment type."}, status=404)

    ignore_ids: tuple[int, ...] = ()
    reschedule_token = request.GET.get("reschedule")
    if reschedule_token:
        try:
            uuid = UUID(reschedule_token)
        except ValueError:
            return JsonResponse({"error": "Invalid reschedule token."}, status=400)
        original = Booking.objects.filter(
            manage_token=uuid, status=Booking.Status.CONFIRMED
        ).only("id")
        ignore_ids = tuple(original.values_list("id", flat=True))

    slots = generate_slots(
        appointment_type, date_from, date_to, ignore_booking_ids=ignore_ids
    )
    return JsonResponse(
        {
            "appointment_type": {
                "slug": appointment_type.slug,
                "duration_minutes": appointment_type.duration_minutes,
            },
            "slots": [s.isoformat().replace("+00:00", "Z") for s in slots],
        }
    )


def _parse_iso_utc(raw: str | None) -> datetime | None:
    if not raw:
        return None
    text = raw.strip()
    if text.endswith("Z"):
        text = text[:-1] + "+00:00"
    try:
        dt = datetime.fromisoformat(text)
    except ValueError:
        return None
    if dt.tzinfo is None:
        return dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc)


@csrf_protect
@require_POST
def bookings_api(request: HttpRequest) -> HttpResponse:
    """Create (or reschedule) a confirmed booking."""
    try:
        payload = json.loads(request.body.decode("utf-8"))
    except (ValueError, UnicodeDecodeError):
        return JsonResponse({"error": "Invalid JSON."}, status=400)

    fields: dict[str, list[str]] = {}

    type_slug = (payload.get("appointment_type") or "").strip()
    if not type_slug:
        fields["appointment_type"] = ["This field is required."]
    name = (payload.get("name") or "").strip()
    if not name:
        fields["name"] = ["This field is required."]
    email = (payload.get("email") or "").strip()
    if not email or "@" not in email:
        fields["email"] = ["Enter a valid email address."]

    start_at = _parse_iso_utc(payload.get("start_at"))
    if start_at is None:
        fields["start_at"] = ["Enter a valid ISO-8601 datetime."]

    if fields:
        return JsonResponse({"error": "validation_error", "fields": fields}, status=400)

    appointment_type = AppointmentType.objects.filter(
        slug=type_slug, is_active=True
    ).first()
    if appointment_type is None:
        return JsonResponse({"error": "Unknown appointment type."}, status=404)

    end_at = start_at + timedelta(minutes=appointment_type.duration_minutes)

    service_id = payload.get("service")
    service_obj = None
    if service_id:
        try:
            service_obj = Service.objects.filter(id=int(service_id)).first()
        except (TypeError, ValueError):
            service_obj = None

    reschedule_token = payload.get("reschedule_token")
    original_booking: Booking | None = None
    if reschedule_token:
        try:
            uuid = UUID(reschedule_token)
        except ValueError:
            return JsonResponse({"error": "Invalid reschedule token."}, status=400)
        original_booking = Booking.objects.filter(
            manage_token=uuid, status=Booking.Status.CONFIRMED
        ).first()
        if original_booking is None:
            return JsonResponse(
                {"error": "Original booking not found or already cancelled."},
                status=404,
            )

    if not slot_is_available(
        appointment_type,
        start_at,
        exclude_booking_id=original_booking.id if original_booking else None,
    ):
        return JsonResponse(
            {"error": "slot_unavailable", "message": "That time is no longer available."},
            status=409,
        )

    try:
        with transaction.atomic():
            overlap = (
                Booking.objects.select_for_update()
                .filter(
                    status=Booking.Status.CONFIRMED,
                    start_at__lt=end_at,
                    end_at__gt=start_at,
                )
                .exclude(id=original_booking.id if original_booking else 0)
                .exists()
            )
            if overlap:
                return JsonResponse(
                    {
                        "error": "slot_unavailable",
                        "message": "That time was just booked. Please pick another.",
                    },
                    status=409,
                )

            if original_booking is not None:
                original_booking.status = Booking.Status.CANCELLED
                original_booking.cancelled_at = djtz.now()
                original_booking.cancel_reason = "rescheduled"
                original_booking.save(
                    update_fields=["status", "cancelled_at", "cancel_reason", "updated_at"]
                )

            booking = Booking.objects.create(
                appointment_type=appointment_type,
                service=service_obj,
                name=name,
                email=email,
                company=(payload.get("company") or "").strip(),
                phone=(payload.get("phone") or "").strip(),
                notes=(payload.get("notes") or "").strip(),
                start_at=start_at,
                end_at=end_at,
                customer_timezone=(payload.get("customer_timezone") or "").strip(),
                status=Booking.Status.CONFIRMED,
                rescheduled_from=original_booking,
                ip_address=_get_client_ip(request),
                user_agent=request.META.get("HTTP_USER_AGENT", "")[:500],
            )
    except IntegrityError:
        return JsonResponse(
            {
                "error": "slot_unavailable",
                "message": "That time was just booked. Please pick another.",
            },
            status=409,
        )

    if original_booking is not None:
        send_reschedule(original_booking, booking)
    else:
        send_confirmation(booking)

    return JsonResponse(
        {
            "ok": True,
            "id": booking.id,
            "manage_token": str(booking.manage_token),
            "manage_url": booking.get_manage_url(),
            "start_at": booking.start_at.isoformat().replace("+00:00", "Z"),
            "end_at": booking.end_at.isoformat().replace("+00:00", "Z"),
        }
    )


@require_GET
def booking_lookup_api(request: HttpRequest) -> JsonResponse:
    """Return enough info to pre-fill the island for a reschedule.

    Looked up by ``?token=<uuid>`` to keep the URL building on the React
    side trivial.
    """
    raw = request.GET.get("token", "").strip()
    try:
        token = UUID(raw)
    except ValueError:
        return JsonResponse({"error": "Invalid token."}, status=400)
    booking = Booking.objects.filter(manage_token=token).select_related(
        "appointment_type", "service"
    ).first()
    if booking is None:
        return JsonResponse({"error": "Not found."}, status=404)
    return JsonResponse(
        {
            "booking": {
                "manage_token": str(booking.manage_token),
                "status": booking.status,
                "appointment_type": booking.appointment_type.slug,
                "appointment_type_name": booking.appointment_type.name,
                "duration_minutes": booking.appointment_type.duration_minutes,
                "name": booking.name,
                "email": booking.email,
                "company": booking.company,
                "phone": booking.phone,
                "notes": booking.notes,
                "service": booking.service_id,
                "start_at": booking.start_at.isoformat().replace("+00:00", "Z"),
                "end_at": booking.end_at.isoformat().replace("+00:00", "Z"),
                "customer_timezone": booking.customer_timezone,
            }
        }
    )


# ----------------------------------------------------------------------------
# Server-rendered manage page
# ----------------------------------------------------------------------------


def manage_booking(request: HttpRequest, token: UUID) -> HttpResponse:
    booking = get_object_or_404(
        Booking.objects.select_related("appointment_type", "service"),
        manage_token=token,
    )
    return render(
        request,
        "scheduling/manage.html",
        {
            "booking": booking,
            "can_modify": booking.is_active and booking.start_at > djtz.now(),
            "seo_title": "Manage your booking",
            "seo_description": "Manage or cancel your scheduled consultation.",
            "seo_robots": "noindex,nofollow",
        },
    )


@csrf_protect
def cancel_booking(request: HttpRequest, token: UUID) -> HttpResponse:
    if request.method != "POST":
        return HttpResponseNotAllowed(["POST"])
    booking = get_object_or_404(Booking, manage_token=token)
    if not booking.is_active:
        return redirect("scheduling-manage", token=token)
    if booking.start_at <= djtz.now():
        raise Http404("This booking has already occurred.")

    booking.status = Booking.Status.CANCELLED
    booking.cancelled_at = djtz.now()
    booking.cancel_reason = (request.POST.get("reason") or "")[:200]
    booking.save(update_fields=["status", "cancelled_at", "cancel_reason", "updated_at"])

    try:
        send_cancellation(booking)
    except Exception:  # noqa: BLE001
        logger.exception("Failed to send cancellation email for booking %s", booking.id)

    return redirect("scheduling-manage", token=token)
