from django.urls import path

from .views import (
    ScheduleView,
    appointment_types_api,
    booking_lookup_api,
    bookings_api,
    cancel_booking,
    inquiry_api,
    manage_booking,
    services_api,
    slots_api,
)

urlpatterns = [
    path("", ScheduleView.as_view(), name="schedule"),
    # Booking calendar
    path(
        "api/appointment-types/",
        appointment_types_api,
        name="scheduling-api-appointment-types",
    ),
    path("api/slots/", slots_api, name="scheduling-api-slots"),
    path("api/bookings/", bookings_api, name="scheduling-api-bookings"),
    path(
        "api/bookings/lookup/",
        booking_lookup_api,
        name="scheduling-api-booking-lookup",
    ),
    path(
        "manage/<uuid:token>/",
        manage_booking,
        name="scheduling-manage",
    ),
    path(
        "manage/<uuid:token>/cancel/",
        cancel_booking,
        name="scheduling-manage-cancel",
    ),
    # Legacy lead-capture endpoints
    path("api/services/", services_api, name="scheduling-api-services"),
    path("api/inquiry/", inquiry_api, name="scheduling-api-inquiry"),
]
