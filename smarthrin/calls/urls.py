"""URL configuration for the calls app (CallRecord endpoints)."""
from django.urls import include, path
from rest_framework.routers import DefaultRouter

from .views import CallRecordViewSet

router = DefaultRouter()
router.register(r"", CallRecordViewSet, basename="call")

urlpatterns = [path("", include(router.urls))]
