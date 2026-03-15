"""Serializers for Applicant model."""
from rest_framework import serializers

from .models import Applicant


class ApplicantListSerializer(serializers.ModelSerializer):
    """Flat serializer for list views."""

    class Meta:
        model = Applicant
        fields = [
            "id",
            "first_name",
            "last_name",
            "email",
            "phone",
            "source",
            "skills",
            "experience_years",
            "current_role",
            "current_company",
            "tags",
            "created_at",
        ]
        read_only_fields = ["id", "created_at"]


class ApplicantDetailSerializer(serializers.ModelSerializer):
    """Full serializer for detail, create, and update views."""

    class Meta:
        model = Applicant
        fields = [
            "id",
            "tenant_id",
            "owner_user_id",
            "first_name",
            "last_name",
            "email",
            "phone",
            "resume_url",
            "linkedin_url",
            "portfolio_url",
            "skills",
            "experience_years",
            "current_company",
            "current_role",
            "notes",
            "source",
            "tags",
            "created_at",
            "updated_at",
        ]
        read_only_fields = [
            "id",
            "tenant_id",
            "owner_user_id",
            "created_at",
            "updated_at",
        ]
