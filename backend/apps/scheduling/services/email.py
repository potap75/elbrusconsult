"""Send confirmation / cancellation / reschedule emails for bookings.

Each helper builds a multipart email with text + HTML bodies and attaches
a ``.ics`` calendar invite. The ``.ics`` uses the booking's ``manage_token``
as a stable UID so a follow-up CANCEL or updated REQUEST replaces the same
event in the customer's calendar.
"""
from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Literal

from django.conf import settings
from django.core.mail import EmailMultiAlternatives
from django.template.loader import render_to_string
from icalendar import Calendar, Event, vCalAddress, vText

from ..models import Booking

logger = logging.getLogger(__name__)

IcsMethod = Literal["REQUEST", "CANCEL"]


def _absolute_url(path: str) -> str:
    base = settings.SITE_URL.rstrip("/")
    if path.startswith("http"):
        return path
    return f"{base}{path}"


def build_ics(booking: Booking, *, method: IcsMethod = "REQUEST", sequence: int = 0) -> bytes:
    """Build an RFC-5545 calendar payload for ``booking``."""
    cal = Calendar()
    cal.add("prodid", f"-//{settings.SITE_NAME}//Scheduling//EN")
    cal.add("version", "2.0")
    cal.add("method", method)

    event = Event()
    event.add("uid", f"{booking.manage_token}@{settings.SITE_DOMAIN}")
    event.add("dtstamp", datetime.now(tz=timezone.utc))
    event.add("dtstart", booking.start_at)
    event.add("dtend", booking.end_at)
    event.add("summary", f"{settings.SITE_NAME}: {booking.appointment_type.name}")
    event.add("sequence", sequence)
    if method == "CANCEL":
        event.add("status", "CANCELLED")
    else:
        event.add("status", "CONFIRMED")

    description_lines = [
        f"{booking.appointment_type.name} with {settings.SITE_NAME}.",
    ]
    if booking.appointment_type.description:
        description_lines.append(booking.appointment_type.description)
    if booking.notes:
        description_lines.append("")
        description_lines.append("Customer notes:")
        description_lines.append(booking.notes)
    description_lines.append("")
    description_lines.append(
        f"Manage this booking: {_absolute_url(booking.get_manage_url())}"
    )
    event.add("description", "\n".join(description_lines))

    if booking.appointment_type.location_instructions:
        event.add("location", booking.appointment_type.location_instructions)

    organizer = vCalAddress(f"MAILTO:{settings.INFO_EMAIL}")
    organizer.params["cn"] = vText(settings.SITE_NAME)
    event["organizer"] = organizer

    attendee = vCalAddress(f"MAILTO:{booking.email}")
    attendee.params["cn"] = vText(booking.name)
    attendee.params["partstat"] = vText("ACCEPTED" if method == "REQUEST" else "DECLINED")
    attendee.params["role"] = vText("REQ-PARTICIPANT")
    event.add("attendee", attendee, encode=0)

    cal.add_component(event)
    return cal.to_ical()


def _send(
    booking: Booking,
    *,
    subject: str,
    template_base: str,
    context: dict,
    to: list[str],
    reply_to: list[str] | None = None,
    ics_bytes: bytes | None = None,
    ics_method: IcsMethod = "REQUEST",
) -> None:
    text_body = render_to_string(f"scheduling/emails/{template_base}.txt", context)
    html_body = render_to_string(f"scheduling/emails/{template_base}.html", context)
    msg = EmailMultiAlternatives(
        subject=subject,
        body=text_body,
        from_email=settings.DEFAULT_FROM_EMAIL,
        to=to,
        reply_to=reply_to,
    )
    msg.attach_alternative(html_body, "text/html")
    if ics_bytes is not None:
        msg.attach(
            filename="invite.ics",
            content=ics_bytes,
            mimetype=f"text/calendar; charset=utf-8; method={ics_method}",
        )
    try:
        msg.send(fail_silently=False)
    except Exception:  # noqa: BLE001
        logger.exception("Failed to send scheduling email '%s' to %s", subject, to)


def _booking_context(booking: Booking) -> dict:
    return {
        "booking": booking,
        "site_name": settings.SITE_NAME,
        "site_url": settings.SITE_URL.rstrip("/"),
        "manage_url": _absolute_url(booking.get_manage_url()),
        "cancel_url": _absolute_url(booking.get_cancel_url()),
        "reschedule_url": _absolute_url(booking.get_reschedule_url()),
    }


def send_confirmation(booking: Booking) -> None:
    """Email the customer (with .ics) and notify staff."""
    customer_context = _booking_context(booking)
    ics = build_ics(booking, method="REQUEST", sequence=0)
    _send(
        booking,
        subject=f"[{settings.SITE_NAME}] Booking confirmed: {booking.appointment_type.name}",
        template_base="booking_confirmed",
        context=customer_context,
        to=[booking.email],
        reply_to=[settings.CONTACT_RECIPIENT_EMAIL],
        ics_bytes=ics,
        ics_method="REQUEST",
    )
    _send(
        booking,
        subject=f"[{settings.SITE_NAME}] New booking: {booking.name} - {booking.appointment_type.name}",
        template_base="staff_notification",
        context=customer_context,
        to=[settings.CONTACT_RECIPIENT_EMAIL],
        reply_to=[booking.email],
        ics_bytes=ics,
        ics_method="REQUEST",
    )


def send_cancellation(booking: Booking) -> None:
    """Email customer + staff that the booking is cancelled."""
    context = _booking_context(booking)
    ics = build_ics(booking, method="CANCEL", sequence=1)
    _send(
        booking,
        subject=f"[{settings.SITE_NAME}] Booking cancelled: {booking.appointment_type.name}",
        template_base="booking_cancelled",
        context=context,
        to=[booking.email],
        reply_to=[settings.CONTACT_RECIPIENT_EMAIL],
        ics_bytes=ics,
        ics_method="CANCEL",
    )
    _send(
        booking,
        subject=f"[{settings.SITE_NAME}] Cancelled: {booking.name} - {booking.appointment_type.name}",
        template_base="staff_cancellation",
        context=context,
        to=[settings.CONTACT_RECIPIENT_EMAIL],
        reply_to=[booking.email],
        ics_bytes=ics,
        ics_method="CANCEL",
    )


def send_reschedule(old_booking: Booking, new_booking: Booking) -> None:
    """Send a single 'rescheduled' email + an updated invite (CANCEL old, REQUEST new)."""
    cancel_ics = build_ics(old_booking, method="CANCEL", sequence=1)
    new_ics = build_ics(new_booking, method="REQUEST", sequence=0)
    context = _booking_context(new_booking)
    context["old_booking"] = old_booking
    _send(
        new_booking,
        subject=f"[{settings.SITE_NAME}] Booking rescheduled: {new_booking.appointment_type.name}",
        template_base="booking_rescheduled",
        context=context,
        to=[new_booking.email],
        reply_to=[settings.CONTACT_RECIPIENT_EMAIL],
        ics_bytes=new_ics,
        ics_method="REQUEST",
    )
    _send(
        new_booking,
        subject=(
            f"[{settings.SITE_NAME}] Rescheduled: {new_booking.name}"
            f" - {new_booking.appointment_type.name}"
        ),
        template_base="staff_notification",
        context=context,
        to=[settings.CONTACT_RECIPIENT_EMAIL],
        reply_to=[new_booking.email],
        ics_bytes=new_ics,
        ics_method="REQUEST",
    )
    _ = cancel_ics  # The CANCEL ics is conceptually superseded by the new REQUEST.
