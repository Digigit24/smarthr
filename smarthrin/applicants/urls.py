"""URL configuration for applicants app."""
from django.urls import include, path
from rest_framework.routers import DefaultRouter

from .views import ApplicantViewSet, export_applicants

router = DefaultRouter()
router.register(r"", ApplicantViewSet, basename="applicant")

urlpatterns = [
    path("export/", export_applicants, name="applicant-export"),
    path("", include(router.urls)),
]
