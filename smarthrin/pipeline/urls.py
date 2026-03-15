"""URL configuration for the pipeline app."""
from django.urls import include, path
from rest_framework.routers import DefaultRouter

from .views import PipelineStageViewSet

router = DefaultRouter()
router.register(r"", PipelineStageViewSet, basename="pipeline-stage")

urlpatterns = [path("", include(router.urls))]
