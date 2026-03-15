"""Serializers for the Interview model."""
from rest_framework import serializers

from .models import Interview


class InterviewListSerializer(serializers.ModelSerializer):
    """Compact serializer for Interview list views."""

    class Meta:
        model = Interview
        fields = [
            "id",
            "application_id",
            "interview_type",
            "scheduled_at",
            "duration_minutes",
            "interviewer_name",
            "interviewer_email",
            "status",
            "meeting_link",
            "created_at",
        ]
        read_only_fields = ["id", "created_at"]


class InterviewDetailSerializer(serializers.ModelSerializer):
    """Full serializer for Interview detail views and create/update."""

    class Meta:
        model = Interview
        fields = [
            "id",
            "tenant_id",
            "owner_user_id",
            "application_id",
            "interview_type",
            "scheduled_at",
            "duration_minutes",
            "interviewer_user_id",
            "interviewer_name",
            "interviewer_email",
            "status",
            "meeting_link",
            "calendar_event_id",
            "feedback",
            "rating",
            "created_at",
            "updated_at",
        ]
        read_only_fields = ["id", "tenant_id", "owner_user_id", "created_at", "updated_at"]
