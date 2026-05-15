from django.urls import path

from .views import ScheduleView, inquiry_api, services_api

urlpatterns = [
    path("", ScheduleView.as_view(), name="schedule"),
    path("api/services/", services_api, name="scheduling-api-services"),
    path("api/inquiry/", inquiry_api, name="scheduling-api-inquiry"),
]
