from django.urls import path

from .views import (
    AboutView,
    AdsEngineView,
    HomeView,
    PrivacyView,
    ServiceDetailView,
    ServiceListView,
    TermsView,
)

urlpatterns = [
    path("", HomeView.as_view(), name="home"),
    path("about/", AboutView.as_view(), name="about"),
    path("ads-engine/", AdsEngineView.as_view(), name="ads-engine"),
    path("privacy/", PrivacyView.as_view(), name="privacy"),
    path("terms/", TermsView.as_view(), name="terms"),
    path("services/", ServiceListView.as_view(), name="services-list"),
    path("services/<slug:slug>/", ServiceDetailView.as_view(), name="service-detail"),
]
