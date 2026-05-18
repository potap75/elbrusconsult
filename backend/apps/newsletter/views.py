from __future__ import annotations

from typing import Any

from django.contrib import messages
from django.http import HttpResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse_lazy
from django.utils import timezone
from django.utils.decorators import method_decorator
from django.views.generic import FormView, TemplateView
from django_ratelimit.decorators import ratelimit

from core.net import get_client_ip
from core.seo import SeoMixin

from .forms import SubscribeForm
from .models import Subscriber
from .services import send_confirmation_email


@method_decorator(
    ratelimit(key="ip", rate="5/h", method="POST", block=True),
    name="post",
)
class SubscribeView(SeoMixin, FormView):
    template_name = "newsletter/subscribe.html"
    form_class = SubscribeForm
    success_url = reverse_lazy("newsletter-pending")
    seo_title = "Newsletter"
    seo_description = (
        "Monthly insights from Elbrus Cloud on cloud architecture, identity, "
        "controls, threat detection, and incident response."
    )

    def form_valid(self, form: SubscribeForm) -> HttpResponse:
        email = form.cleaned_data["email"].lower().strip()
        subscriber, created = Subscriber.objects.get_or_create(
            email=email,
            defaults={
                "source": "/newsletter/",
                "ip_address": get_client_ip(self.request),
            },
        )
        # If they previously unsubscribed, allow them to re-confirm.
        if subscriber.unsubscribed_at:
            subscriber.unsubscribed_at = None
            subscriber.confirmed_at = None
            subscriber.save(update_fields=["unsubscribed_at", "confirmed_at"])

        if not subscriber.is_confirmed:
            send_confirmation_email(subscriber, self.request)

        return super().form_valid(form)


class SubscribePendingView(SeoMixin, TemplateView):
    template_name = "newsletter/pending.html"
    seo_title = "Check your inbox"
    seo_robots = "noindex,follow"


class ConfirmView(SeoMixin, TemplateView):
    template_name = "newsletter/confirmed.html"
    seo_title = "Subscription confirmed"
    seo_robots = "noindex,follow"

    def get(self, request, *args, **kwargs):
        token = kwargs["token"]
        subscriber = get_object_or_404(Subscriber, token=token)
        if not subscriber.confirmed_at:
            subscriber.confirmed_at = timezone.now()
            subscriber.unsubscribed_at = None
            subscriber.save(update_fields=["confirmed_at", "unsubscribed_at"])
        return self.render_to_response(self.get_context_data(subscriber=subscriber))


class UnsubscribeView(SeoMixin, TemplateView):
    template_name = "newsletter/unsubscribed.html"
    seo_title = "Unsubscribed"
    seo_robots = "noindex,follow"

    def get(self, request, *args, **kwargs):
        token = kwargs["token"]
        subscriber = get_object_or_404(Subscriber, token=token)
        if not subscriber.unsubscribed_at:
            subscriber.unsubscribed_at = timezone.now()
            subscriber.save(update_fields=["unsubscribed_at"])
        return self.render_to_response(self.get_context_data(subscriber=subscriber))
