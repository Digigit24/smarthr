"""Serializers for Applicant model."""
from rest_framework import serializers
from .models import Applicant


class ApplicantApplicationSerializer(serializers.Serializer):
    """Inline application summary nested inside ApplicantDetailSerializer."""
    id = serializers.UUIDField()
    job_id = serializers.UUIDField()
    job_title = serializers.SerializerMethodField()
    status = serializers.CharField()
    score = serializers.DecimalField(max_digits=5, decimal_places=2, allow_null=True)
    created_at = serializers.DateTimeField()

    def get_job_title(self, obj):
        return obj.job.title if obj.job_id else None


class ApplicantListSerializer(serializers.ModelSerializer):
    full_name = serializers.SerializerMethodField()

    class Meta:
        model = Applicant
        fields = [
            "id", "first_name", "last_name", "full_name", "email", "phone",
            "source", "skills", "experience_years", "current_role",
            "current_company", "tags", "custom_fields", "created_at",
        ]
        read_only_fields = ["id", "created_at"]

    def get_full_name(self, obj) -> str:
        return f"{obj.first_name} {obj.last_name}"


class ApplicantCreateSerializer(serializers.ModelSerializer):
    """Write serializer for create/update."""
    class Meta:
        model = Applicant
        fields = [
            "id",
            "first_name", "last_name", "email", "phone",
            "resume_url", "linkedin_url", "portfolio_url",
            "skills", "experience_years", "current_company", "current_role",
            "notes", "source", "tags", "custom_fields",
        ]
        read_only_fields = ["id"]

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

    def validate_custom_fields(self, value):
        if not isinstance(value, dict):
            raise serializers.ValidationError("custom_fields must be a JSON object.")
        if len(value) > 20:
            raise serializers.ValidationError(
                f"Maximum 20 custom fields allowed, got {len(value)}."
            )
        for key, val in value.items():
            if len(key) > 100:
                raise serializers.ValidationError(
                    f"Custom field key '{key[:50]}...' exceeds 100 characters."
                )
            if not isinstance(val, (str, int, float, bool, type(None))):
                raise serializers.ValidationError(
                    f"Custom field '{key}' must be a simple value (string, number, or boolean)."
                )
        return value


class ApplicantImportSerializer(serializers.ModelSerializer):
    """
    Write serializer for bulk import – every field is optional.

    Manual-entry validation (required first_name, last_name, email) stays
    in ApplicantCreateSerializer and is NOT affected by this serializer.
    """
    first_name = serializers.CharField(max_length=255, required=False, default="")
    last_name = serializers.CharField(max_length=255, required=False, default="")
    email = serializers.EmailField(required=False, default="")
    phone = serializers.CharField(max_length=20, required=False, default="")
    resume_url = serializers.URLField(required=False, default="")
    linkedin_url = serializers.URLField(required=False, default="")
    portfolio_url = serializers.URLField(required=False, default="")
    skills = serializers.ListField(child=serializers.CharField(), required=False, default=list)
    experience_years = serializers.IntegerField(required=False, allow_null=True, default=None)
    current_company = serializers.CharField(max_length=255, required=False, default="")
    current_role = serializers.CharField(max_length=255, required=False, default="")
    notes = serializers.CharField(required=False, default="")
    source = serializers.ChoiceField(choices=Applicant.Source.choices, required=False, default=Applicant.Source.IMPORT)
    tags = serializers.ListField(child=serializers.CharField(), required=False, default=list)
    custom_fields = serializers.DictField(
        child=serializers.CharField(max_length=1000),
        required=False,
        default=dict,
    )

    def validate_custom_fields(self, value):
        if len(value) > 20:
            raise serializers.ValidationError(
                f"Maximum 20 custom fields allowed, got {len(value)}."
            )
        for key in value:
            if len(key) > 100:
                raise serializers.ValidationError(
                    f"Custom field key '{key[:50]}...' exceeds 100 characters."
                )
        return value

    class Meta:
        model = Applicant
        fields = [
            "first_name", "last_name", "email", "phone",
            "resume_url", "linkedin_url", "portfolio_url",
            "skills", "experience_years", "current_company", "current_role",
            "notes", "source", "tags", "custom_fields",
        ]


class ApplicantDetailSerializer(serializers.ModelSerializer):
    full_name = serializers.SerializerMethodField()
    applications = ApplicantApplicationSerializer(many=True, read_only=True)

    class Meta:
        model = Applicant
        fields = [
            "id", "tenant_id", "owner_user_id",
            "first_name", "last_name", "full_name", "email", "phone",
            "resume_url", "linkedin_url", "portfolio_url",
            "skills", "experience_years", "current_company", "current_role",
            "notes", "source", "tags", "custom_fields", "applications", "created_at", "updated_at",
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
