"""Serializers for Applicant model."""
from rest_framework import serializers
from .models import Applicant


class ApplicantListSerializer(serializers.ModelSerializer):
    full_name = serializers.SerializerMethodField()

    class Meta:
        model = Applicant
        fields = [
            "id", "first_name", "last_name", "full_name", "email", "phone",
            "source", "skills", "experience_years", "current_role",
            "current_company", "tags", "created_at",
        ]
        read_only_fields = ["id", "created_at"]

    def get_full_name(self, obj) -> str:
        return f"{obj.first_name} {obj.last_name}"


class ApplicantCreateSerializer(serializers.ModelSerializer):
    """Write serializer for create/update."""
    class Meta:
        model = Applicant
        fields = [
            "first_name", "last_name", "email", "phone",
            "resume_url", "linkedin_url", "portfolio_url",
            "skills", "experience_years", "current_company", "current_role",
            "notes", "source", "tags",
        ]

    def validate_email(self, value):
        request = self.context.get("request")
        if not request:
            return value
        tenant_id = getattr(request, "tenant_id", None)
        if not tenant_id:
            return value
        qs = Applicant.objects.filter(tenant_id=tenant_id, email=value)
        if self.instance:
            qs = qs.exclude(pk=self.instance.pk)
        if qs.exists():
            raise serializers.ValidationError(
                "An applicant with this email already exists for this tenant."
            )
        return value


class ApplicantDetailSerializer(serializers.ModelSerializer):
    full_name = serializers.SerializerMethodField()

    class Meta:
        model = Applicant
        fields = [
            "id", "tenant_id", "owner_user_id",
            "first_name", "last_name", "full_name", "email", "phone",
            "resume_url", "linkedin_url", "portfolio_url",
            "skills", "experience_years", "current_company", "current_role",
            "notes", "source", "tags", "created_at", "updated_at",
        ]
        read_only_fields = ["id", "tenant_id", "owner_user_id", "created_at", "updated_at"]

    def get_full_name(self, obj) -> str:
        return f"{obj.first_name} {obj.last_name}"

    def validate_email(self, value):
        request = self.context.get("request")
        if not request:
            return value
        tenant_id = getattr(request, "tenant_id", None)
        if not tenant_id:
            return value
        qs = Applicant.objects.filter(tenant_id=tenant_id, email=value)
        if self.instance:
            qs = qs.exclude(pk=self.instance.pk)
        if qs.exists():
            raise serializers.ValidationError(
                "An applicant with this email already exists for this tenant."
            )
        return value
