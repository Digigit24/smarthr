"""URL configuration for applicants app."""
from django.urls import include, path
from rest_framework.routers import DefaultRouter

from .views import ApplicantViewSet, export_applicants, import_applicants, import_fields, import_preview

router = DefaultRouter()
router.register(r"", ApplicantViewSet, basename="applicant")

urlpatterns = [
    path("export/", export_applicants, name="applicant-export"),
    path("import/fields/", import_fields, name="applicant-import-fields"),
    path("import/preview/", import_preview, name="applicant-import-preview"),
    path("import/", import_applicants, name="applicant-import"),
    path("", include(router.urls)),
]
