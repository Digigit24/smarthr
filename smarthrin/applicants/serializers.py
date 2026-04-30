"""Serializers for Applicant model."""
from rest_framework import serializers

from common.phone import normalize_phone
from .models import Applicant


def _normalize_applicant_phone(value):
    """
    Shared validator body for applicant phone fields.
    Returns "" for blank input (phone is optional), otherwise returns the
    E.164-normalized value. Wraps ValueError in DRF's ValidationError.
    """
    if value in (None, ""):
        return ""
    try:
        return normalize_phone(value)
    except ValueError as exc:
        raise serializers.ValidationError(str(exc))


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
    """Write serializer for create/update — keeps full validation."""
    email = serializers.EmailField(required=True)
    resume_url = serializers.URLField(required=False, allow_blank=True)
    resume_file = serializers.FileField(required=False, allow_null=True)
    linkedin_url = serializers.URLField(required=False, allow_blank=True)
    portfolio_url = serializers.URLField(required=False, allow_blank=True)

    # Allowed resume content types — matched against the upload's MIME type.
    _ALLOWED_RESUME_CONTENT_TYPES = {
        "application/pdf",
        "application/msword",
        "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        "text/plain",
    }

    class Meta:
        model = Applicant
        fields = [
            "id",
            "first_name", "last_name", "email", "phone",
            "resume_url", "resume_file", "linkedin_url", "portfolio_url",
            "skills", "experience_years", "current_company", "current_role",
            "notes", "source", "tags", "custom_fields",
        ]
        read_only_fields = ["id"]

    def validate_resume_file(self, value):
        if value is None:
            return value
        from django.conf import settings
        max_bytes = getattr(settings, "MAX_RESUME_UPLOAD_BYTES", 10 * 1024 * 1024)
        if value.size > max_bytes:
            raise serializers.ValidationError(
                f"Resume file exceeds the {max_bytes // (1024 * 1024)} MB limit."
            )
        content_type = getattr(value, "content_type", "") or ""
        if content_type and content_type not in self._ALLOWED_RESUME_CONTENT_TYPES:
            raise serializers.ValidationError(
                "Resume must be a PDF, DOC, DOCX, or plain-text file."
            )
        return value

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

    def validate_phone(self, value):
        return _normalize_applicant_phone(value)

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
    Write serializer for bulk import – every field is optional, no format
    validation. Manual-entry validation (required fields, email format,
    uniqueness) stays in ApplicantCreateSerializer.
    """
    first_name = serializers.CharField(max_length=255, required=False, default="")
    last_name = serializers.CharField(max_length=255, required=False, default="")
    email = serializers.CharField(max_length=254, required=False, default="", allow_blank=True)
    phone = serializers.CharField(max_length=50, required=False, default="", allow_blank=True)
    resume_url = serializers.CharField(max_length=500, required=False, default="", allow_blank=True)
    linkedin_url = serializers.CharField(max_length=500, required=False, default="", allow_blank=True)
    portfolio_url = serializers.CharField(max_length=500, required=False, default="", allow_blank=True)
    skills = serializers.ListField(child=serializers.CharField(), required=False, default=list)
    experience_years = serializers.IntegerField(required=False, allow_null=True, default=None)
    current_company = serializers.CharField(max_length=255, required=False, default="")
    current_role = serializers.CharField(max_length=255, required=False, default="")
    notes = serializers.CharField(required=False, default="", allow_blank=True)
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

    def validate_phone(self, value):
        # Import path is deliberately permissive: normalize to E.164 when we
        # can, but fall back to the raw value on failure so the row still
        # lands in the DB. The user can fix invalid phones after import.
        if value in (None, ""):
            return ""
        try:
            return normalize_phone(value)
        except ValueError:
            return str(value)

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
    resume_file = serializers.FileField(read_only=True)
    resume_download_url = serializers.SerializerMethodField()

    class Meta:
        model = Applicant
        fields = [
            "id", "tenant_id", "owner_user_id",
            "first_name", "last_name", "full_name", "email", "phone",
            "resume_url", "resume_file", "resume_download_url",
            "linkedin_url", "portfolio_url",
            "skills", "experience_years", "current_company", "current_role",
            "notes", "source", "tags", "custom_fields", "applications", "created_at", "updated_at",
        ]
        read_only_fields = ["id", "tenant_id", "owner_user_id", "created_at", "updated_at"]

    def get_resume_download_url(self, obj) -> str:
        """API endpoint to download the uploaded resume; null when no file."""
        if not obj.resume_file:
            return None
        request = self.context.get("request")
        path = f"/api/v1/applicants/{obj.id}/download-resume/"
        return request.build_absolute_uri(path) if request else path

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
