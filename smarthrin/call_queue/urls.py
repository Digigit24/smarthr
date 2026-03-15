"""URL configuration for the call_queue app."""
from django.urls import include, path
from rest_framework.routers import DefaultRouter

from .views import CallQueueViewSet

router = DefaultRouter()
router.register(r"", CallQueueViewSet, basename="call-queue")

urlpatterns = [
    path("", include(router.urls)),
]
