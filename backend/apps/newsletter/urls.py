from django.urls import path

from .views import ConfirmView, SubscribePendingView, SubscribeView, UnsubscribeView

urlpatterns = [
    path("", SubscribeView.as_view(), name="newsletter-subscribe"),
    path("pending/", SubscribePendingView.as_view(), name="newsletter-pending"),
    path("confirm/<str:token>/", ConfirmView.as_view(), name="newsletter-confirm"),
    path("unsubscribe/<str:token>/", UnsubscribeView.as_view(), name="newsletter-unsubscribe"),
]
