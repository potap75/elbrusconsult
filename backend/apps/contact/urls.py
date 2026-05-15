from django.urls import path

from .views import ContactThanksView, ContactView

urlpatterns = [
    path("", ContactView.as_view(), name="contact"),
    path("thanks/", ContactThanksView.as_view(), name="contact-thanks"),
]
