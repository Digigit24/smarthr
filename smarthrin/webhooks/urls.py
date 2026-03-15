from django.urls import path
from .views import CallCompletedWebhookView, CallStatusWebhookView

urlpatterns = [
    path("voice/call-completed/", CallCompletedWebhookView.as_view(), name="webhook-call-completed"),
    path("voice/call-status/", CallStatusWebhookView.as_view(), name="webhook-call-status"),
]
