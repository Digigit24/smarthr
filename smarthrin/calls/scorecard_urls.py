"""URL configuration for scorecards mounted at /api/v1/scorecards/."""
from django.urls import include, path
from rest_framework.routers import DefaultRouter

from .views import ScorecardViewSet

router = DefaultRouter()
router.register(r"", ScorecardViewSet, basename="scorecard")

urlpatterns = [path("", include(router.urls))]
