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


class InterviewCreateSerializer(serializers.ModelSerializer):
    """Write serializer — excludes read-only system fields."""
    class Meta:
        model = Interview
        fields = [
            "application",
            "interview_type",
            "scheduled_at",
            "duration_minutes",
            "interviewer_user_id",
            "interviewer_name",
            "interviewer_email",
            "meeting_link",
            "calendar_event_id",
        ]


class CompleteInterviewSerializer(serializers.Serializer):
    """Request body for the complete action."""
    feedback = serializers.CharField(required=False, allow_blank=True)
    rating = serializers.IntegerField(required=False, min_value=1, max_value=5, allow_null=True)
