"""Views for the marketing static pages and Services catalog."""
from __future__ import annotations

from typing import Any

from django.conf import settings
from django.shortcuts import get_object_or_404
from django.views.generic import DetailView, ListView, TemplateView

from core.sanitize import safe_html
from core.schema import breadcrumb_schema
from core.seo import SeoMixin

from .models import Service


class HomeView(SeoMixin, TemplateView):
    template_name = "pages/home.html"
    seo_title = "Cloud Architecture & Cybersecurity Consulting"
    seo_description = (
        "Elbrus Cloud delivers expert cloud engineering and cybersecurity "
        "consulting: risk assessments, identity, controls, testing, detection, "
        "forensics, recovery, and application security."
    )

    def get_context_data(self, **kwargs: Any) -> dict[str, Any]:
        context = super().get_context_data(**kwargs)
        context["featured_services"] = Service.objects.filter(
            is_published=True, is_featured=True
        )
        context["all_services"] = Service.objects.filter(is_published=True)
        return context


class AboutView(SeoMixin, TemplateView):
    template_name = "pages/about.html"
    seo_title = "About Elbrus Cloud"
    seo_description = (
        "A boutique consultancy focused on cloud architecture and cybersecurity. "
        "Over two decades of experience securing applications, networks, "
        "operations, and data."
    )

    def get_breadcrumbs(self) -> list[dict[str, str]]:
        return [
            {"name": "Home", "url": "/"},
            {"name": "About", "url": "/about/"},
        ]

    def get_context_data(self, **kwargs: Any) -> dict[str, Any]:
        context = super().get_context_data(**kwargs)
        context["breadcrumb_schema"] = breadcrumb_schema(self.get_breadcrumbs())
        return context


class ServiceListView(SeoMixin, ListView):
    template_name = "pages/service_list.html"
    model = Service
    context_object_name = "services"
    seo_title = "Consulting Services"
    seo_description = (
        "Risk, Access, Controls, Testing, Detection, Forensics, Recovery, and "
        "Application security services from Elbrus Cloud."
    )

    def get_queryset(self):
        return Service.objects.filter(is_published=True)

    def get_breadcrumbs(self) -> list[dict[str, str]]:
        return [
            {"name": "Home", "url": "/"},
            {"name": "Services", "url": "/services/"},
        ]

    def get_context_data(self, **kwargs: Any) -> dict[str, Any]:
        context = super().get_context_data(**kwargs)
        context["breadcrumb_schema"] = breadcrumb_schema(self.get_breadcrumbs())
        return context


class ServiceDetailView(SeoMixin, DetailView):
    template_name = "pages/service_detail.html"
    model = Service
    context_object_name = "service"
    slug_url_kwarg = "slug"

    def get_queryset(self):
        return Service.objects.filter(is_published=True)

    def get_seo_title(self) -> str:
        return self.object.name

    def get_seo_description(self) -> str:
        return self.object.seo_description

    def get_breadcrumbs(self) -> list[dict[str, str]]:
        return [
            {"name": "Home", "url": "/"},
            {"name": "Services", "url": "/services/"},
            {"name": self.object.name, "url": self.object.get_absolute_url()},
        ]

    def get_context_data(self, **kwargs: Any) -> dict[str, Any]:
        context = super().get_context_data(**kwargs)
        context["body_html"] = safe_html(
            self.object.body_markdown,
            extensions=["extra", "sane_lists", "smarty"],
        )
        context["service_schema"] = {
            "@context": "https://schema.org",
            "@type": "Service",
            "name": self.object.name,
            "description": self.object.seo_description,
            "url": f"{settings.SITE_URL}{self.object.get_absolute_url()}",
            "provider": {
                "@type": "Organization",
                "name": settings.SITE_NAME,
                "url": settings.SITE_URL,
            },
        }
        context["breadcrumb_schema"] = breadcrumb_schema(self.get_breadcrumbs())
        return context
