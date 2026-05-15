from django.urls import path

from .views import AboutView, HomeView, ServiceDetailView, ServiceListView

urlpatterns = [
    path("", HomeView.as_view(), name="home"),
    path("about/", AboutView.as_view(), name="about"),
    path("services/", ServiceListView.as_view(), name="services-list"),
    path("services/<slug:slug>/", ServiceDetailView.as_view(), name="service-detail"),
]
