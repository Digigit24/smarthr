"""URL configuration for the calls app (CallRecord and Scorecard endpoints)."""
from django.urls import include, path
from rest_framework.routers import DefaultRouter

from .views import AvailableVoiceAgentsView, CallRecordViewSet
from .voice_agent_views import VoiceAgentDetailView, VoiceAgentListView

router = DefaultRouter()
router.register(r"", CallRecordViewSet, basename="call")

urlpatterns = [
    path("available-agents/", AvailableVoiceAgentsView.as_view(), name="available-agents"),
    path("", include(router.urls)),
]

# Voice agent proxy routes — registered separately at /api/v1/voice-agents/
voice_agent_urlpatterns = [
    path("", VoiceAgentListView.as_view(), name="voice-agent-list"),
    path("<str:agent_id>/", VoiceAgentDetailView.as_view(), name="voice-agent-detail"),
]
