"""URL configuration for applications app."""
from django.urls import include, path
from rest_framework.routers import DefaultRouter

from .views import ApplicationViewSet, export_applications

router = DefaultRouter()
router.register(r"", ApplicationViewSet, basename="application")

urlpatterns = [
    path("export/", export_applications, name="application-export"),
    path("", include(router.urls)),
]
