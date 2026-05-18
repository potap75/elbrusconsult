from __future__ import annotations

from typing import Any

from django.conf import settings
from django.contrib import messages
from django.core.mail import EmailMessage
from django.urls import reverse_lazy
from django.utils.decorators import method_decorator
from django.views.generic import FormView, TemplateView
from django_ratelimit.decorators import ratelimit

from core.net import get_client_ip
from core.schema import breadcrumb_schema
from core.seo import SeoMixin

from .forms import ContactForm


@method_decorator(
    ratelimit(key="ip", rate="5/h", method="POST", block=True),
    name="post",
)
class ContactView(SeoMixin, FormView):
    template_name = "contact/contact.html"
    form_class = ContactForm
    success_url = reverse_lazy("contact-thanks")
    seo_title = "Contact"
    seo_description = (
        "Get in touch with Elbrus Cloud about cloud architecture, cybersecurity "
        "consulting, risk assessments, and incident response."
    )

    def form_valid(self, form: ContactForm) -> Any:
        instance = form.save(commit=False)
        instance.ip_address = get_client_ip(self.request)
        instance.user_agent = self.request.META.get("HTTP_USER_AGENT", "")[:500]
        instance.save()

        try:
            body = (
                f"New contact form submission\n"
                f"---\n"
                f"Name:    {instance.name}\n"
                f"Email:   {instance.email}\n"
                f"Company: {instance.company or '-'}\n"
                f"Subject: {instance.subject or '-'}\n"
                f"---\n"
                f"{instance.message}\n"
            )
            email = EmailMessage(
                subject=f"[{settings.SITE_NAME}] Contact: {instance.subject or instance.name}",
                body=body,
                from_email=settings.DEFAULT_FROM_EMAIL,
                to=[settings.CONTACT_RECIPIENT_EMAIL],
                reply_to=[instance.email],
            )
            email.send(fail_silently=True)
        except Exception:  # noqa: BLE001
            pass

        messages.success(self.request, "Thanks - we will be in touch shortly.")
        return super().form_valid(form)

    def get_breadcrumbs(self) -> list[dict[str, str]]:
        return [
            {"name": "Home", "url": "/"},
            {"name": "Contact", "url": "/contact/"},
        ]

    def get_context_data(self, **kwargs: Any) -> dict[str, Any]:
        context = super().get_context_data(**kwargs)
        context["local_business_schema"] = {
            "@context": "https://schema.org",
            "@type": "LocalBusiness",
            "name": settings.SITE_NAME,
            "description": settings.SITE_TAGLINE,
            "url": settings.SITE_URL,
            "email": settings.INFO_EMAIL,
        }
        context["breadcrumb_schema"] = breadcrumb_schema(self.get_breadcrumbs())
        return context


class ContactThanksView(SeoMixin, TemplateView):
    template_name = "contact/thanks.html"
    seo_title = "Thanks for reaching out"
    seo_description = "Your message was received. We will reply soon."
    seo_robots = "noindex,follow"
