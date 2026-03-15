"""Serializers for Job model."""
from rest_framework import serializers

from .models import Job


class JobListSerializer(serializers.ModelSerializer):
    """Flat serializer used for list views."""

    class Meta:
        model = Job
        fields = [
            "id",
            "title",
            "department",
            "location",
            "job_type",
            "experience_level",
            "status",
            "application_count",
            "voice_agent_id",
            "published_at",
            "closes_at",
            "created_at",
        ]
        read_only_fields = ["id", "application_count", "created_at"]


class JobDetailSerializer(serializers.ModelSerializer):
    """Full serializer used for detail, create, and update views."""

    class Meta:
        model = Job
        fields = [
            "id",
            "tenant_id",
            "owner_user_id",
            "title",
            "department",
            "location",
            "job_type",
            "experience_level",
            "salary_min",
            "salary_max",
            "description",
            "requirements",
            "status",
            "application_count",
            "voice_agent_id",
            "voice_agent_config",
            "published_at",
            "closes_at",
            "created_at",
            "updated_at",
        ]
        read_only_fields = [
            "id",
            "tenant_id",
            "owner_user_id",
            "application_count",
            "created_at",
            "updated_at",
        ]
