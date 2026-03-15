"""URL configuration for voice agent proxy endpoints."""
from django.urls import path

from .voice_agent_views import VoiceAgentDetailView, VoiceAgentListView

urlpatterns = [
    path("", VoiceAgentListView.as_view(), name="voice-agent-list"),
    path("<str:agent_id>/", VoiceAgentDetailView.as_view(), name="voice-agent-detail"),
]
