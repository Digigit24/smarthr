"""URL configuration for the calls app (CallRecord and Scorecard endpoints)."""
from django.urls import include, path
from rest_framework.routers import DefaultRouter

from .views import AvailableVoiceAgentsView, CallRecordViewSet

router = DefaultRouter()
router.register(r"", CallRecordViewSet, basename="call")

urlpatterns = [
    path("available-agents/", AvailableVoiceAgentsView.as_view(), name="available-agents"),
    path("", include(router.urls)),
]
