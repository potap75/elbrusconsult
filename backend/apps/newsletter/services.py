"""Thin service layer so an external provider (Mailchimp/Brevo) can be slotted
in later without touching views."""
from __future__ import annotations

from django.conf import settings
from django.core.mail import EmailMessage
from django.urls import reverse


def send_confirmation_email(subscriber, request) -> None:
    confirm_path = reverse("newsletter-confirm", kwargs={"token": subscriber.token})
    confirm_url = request.build_absolute_uri(confirm_path)

    body = (
        f"Hi,\n\n"
        f"Please confirm your subscription to the {settings.SITE_NAME} newsletter "
        f"by clicking the link below:\n\n"
        f"{confirm_url}\n\n"
        f"If you didn't request this, you can ignore this email.\n"
    )
    email = EmailMessage(
        subject=f"Confirm your {settings.SITE_NAME} newsletter subscription",
        body=body,
        from_email=settings.DEFAULT_FROM_EMAIL,
        to=[subscriber.email],
    )
    email.send(fail_silently=True)
