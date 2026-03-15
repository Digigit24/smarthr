"""Serializers for Job model."""
from rest_framework import serializers
from .models import Job


class JobListSerializer(serializers.ModelSerializer):
    """Minimal fields for list views."""
    class Meta:
        model = Job
        fields = [
            "id", "title", "department", "location", "job_type",
            "experience_level", "status", "application_count",
            "voice_agent_id", "published_at", "closes_at", "created_at",
        ]
        read_only_fields = ["id", "application_count", "created_at"]


class JobCreateSerializer(serializers.ModelSerializer):
    """Write serializer for create/update — excludes computed/auto fields."""
    class Meta:
        model = Job
        fields = [
            "title", "department", "location", "job_type", "experience_level",
            "salary_min", "salary_max", "description", "requirements",
            "status", "voice_agent_id", "voice_agent_config",
            "published_at", "closes_at",
        ]


class JobDetailSerializer(serializers.ModelSerializer):
    """Full serializer for detail/retrieve views."""
    class Meta:
        model = Job
        fields = [
            "id", "tenant_id", "owner_user_id", "title", "department",
            "location", "job_type", "experience_level", "salary_min",
            "salary_max", "description", "requirements", "status",
            "application_count", "voice_agent_id", "voice_agent_config",
            "published_at", "closes_at", "created_at", "updated_at",
        ]
        read_only_fields = [
            "id", "tenant_id", "owner_user_id", "application_count",
            "created_at", "updated_at",
        ]
