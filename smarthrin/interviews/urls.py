"""URL configuration for the interviews app."""
from django.urls import include, path
from rest_framework.routers import DefaultRouter

from .views import InterviewViewSet

router = DefaultRouter()
router.register(r"", InterviewViewSet, basename="interview")

urlpatterns = [path("", include(router.urls))]
