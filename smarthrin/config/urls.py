"""Root URL configuration."""
from datetime import datetime

from django.contrib import admin
from django.http import JsonResponse
from django.urls import include, path
from drf_spectacular.views import SpectacularAPIView, SpectacularRedocView, SpectacularSwaggerView


def health_check(request):
    return JsonResponse(
        {
            "status": "healthy",
            "version": "1.0.0",
            "timestamp": datetime.utcnow().isoformat() + "Z",
        }
    )


urlpatterns = [
    path("health/", health_check, name="health-check"),
    path("admin/", admin.site.urls),
    # OpenAPI schema + Swagger/Redoc UI
    path("api/schema/", SpectacularAPIView.as_view(), name="schema"),
    path("api/docs/", SpectacularSwaggerView.as_view(url_name="schema"), name="swagger-ui"),
    path("api/redoc/", SpectacularRedocView.as_view(url_name="schema"), name="redoc"),
    # API v1
    path("api/v1/jobs/", include("jobs.urls")),
    path("api/v1/applicants/", include("applicants.urls")),
    path("api/v1/applications/", include("applications.urls")),
    path("api/v1/calls/", include("calls.urls")),
    path("api/v1/scorecards/", include("calls.scorecard_urls")),
    path("api/v1/interviews/", include("interviews.urls")),
    path("api/v1/pipeline/", include("pipeline.urls")),
    path("api/v1/analytics/", include("analytics.urls")),
    path("api/v1/notifications/", include("notifications.urls")),
    path("api/v1/activities/", include("activities.urls")),
    path("api/v1/call-queues/", include("call_queue.urls")),
    path("api/v1/voice-agents/", include("calls.voice_agent_urls")),
    # Webhooks (no auth)
    path("webhooks/", include("webhooks.urls")),
]
