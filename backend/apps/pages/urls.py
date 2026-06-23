from django.urls import path

from .views import AboutView, HomeView, PrivacyView, ServiceDetailView, ServiceListView

urlpatterns = [
    path("", HomeView.as_view(), name="home"),
    path("about/", AboutView.as_view(), name="about"),
    path("privacy/", PrivacyView.as_view(), name="privacy"),
    path("services/", ServiceListView.as_view(), name="services-list"),
    path("services/<slug:slug>/", ServiceDetailView.as_view(), name="service-detail"),
]
