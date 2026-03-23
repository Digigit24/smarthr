"""URL configuration for jobs app."""
from django.urls import include, path
from rest_framework.routers import DefaultRouter

from .views import JobViewSet, export_jobs

router = DefaultRouter()
router.register(r"", JobViewSet, basename="job")

urlpatterns = [
    path("export/", export_jobs, name="job-export"),
    path("", include(router.urls)),
]
