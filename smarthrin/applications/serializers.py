"""Serializers for Application model."""
from rest_framework import serializers

from .models import Application


class ApplicationListSerializer(serializers.ModelSerializer):
    """Flat serializer for list views — avoids N+1 when select_related is used."""

    job_title = serializers.SerializerMethodField()
    applicant_name = serializers.SerializerMethodField()
    applicant_email = serializers.SerializerMethodField()

    class Meta:
        model = Application
        fields = [
            "id",
            "job_id",
            "job_title",
            "applicant_id",
            "applicant_name",
            "applicant_email",
            "status",
            "score",
            "created_at",
            "updated_at",
        ]
        read_only_fields = ["id", "created_at", "updated_at"]

    def get_job_title(self, obj):
        return obj.job.title if obj.job_id else None

    def get_applicant_name(self, obj):
        if obj.applicant_id:
            return obj.applicant.full_name
        return None

    def get_applicant_email(self, obj):
        return obj.applicant.email if obj.applicant_id else None


# ---------------------------------------------------------------------------
# Inline nested serializers — defined here to avoid circular imports with
# calls.serializers and interviews.serializers.
# ---------------------------------------------------------------------------


class InlineApplicantSerializer(serializers.Serializer):
    id = serializers.UUIDField()
    first_name = serializers.CharField()
    last_name = serializers.CharField()
    email = serializers.EmailField()
    phone = serializers.CharField()
    skills = serializers.JSONField()
    experience_years = serializers.IntegerField(allow_null=True)
    current_role = serializers.CharField()
    current_company = serializers.CharField()
    source = serializers.CharField()


class InlineJobSerializer(serializers.Serializer):
    id = serializers.UUIDField()
    title = serializers.CharField()
    department = serializers.CharField()
    location = serializers.CharField()
    job_type = serializers.CharField()
    experience_level = serializers.CharField()
    status = serializers.CharField()


class InlineCallRecordSerializer(serializers.Serializer):
    id = serializers.UUIDField()
    provider = serializers.CharField()
    provider_call_id = serializers.CharField()
    phone = serializers.CharField()
    status = serializers.CharField()
    duration = serializers.IntegerField(allow_null=True)
    summary = serializers.CharField()
    recording_url = serializers.CharField()
    started_at = serializers.DateTimeField(allow_null=True)
    ended_at = serializers.DateTimeField(allow_null=True)
    created_at = serializers.DateTimeField()


class InlineScorecardSerializer(serializers.Serializer):
    id = serializers.UUIDField()
    communication_score = serializers.DecimalField(max_digits=4, decimal_places=2)
    knowledge_score = serializers.DecimalField(max_digits=4, decimal_places=2)
    confidence_score = serializers.DecimalField(max_digits=4, decimal_places=2)
    relevance_score = serializers.DecimalField(max_digits=4, decimal_places=2)
    overall_score = serializers.DecimalField(max_digits=4, decimal_places=2)
    recommendation = serializers.CharField()
    summary = serializers.CharField()
    strengths = serializers.JSONField()
    weaknesses = serializers.JSONField()
    created_at = serializers.DateTimeField()


class InlineInterviewSerializer(serializers.Serializer):
    id = serializers.UUIDField()
    interview_type = serializers.CharField()
    scheduled_at = serializers.DateTimeField()
    duration_minutes = serializers.IntegerField()
    interviewer_name = serializers.CharField()
    interviewer_email = serializers.EmailField()
    status = serializers.CharField()
    meeting_link = serializers.CharField()
    feedback = serializers.CharField()
    rating = serializers.IntegerField(allow_null=True)
    created_at = serializers.DateTimeField()


class ApplicationDetailSerializer(serializers.ModelSerializer):
    """Full serializer for detail, create, and update views — includes nested objects."""

    applicant = InlineApplicantSerializer(read_only=True)
    job = InlineJobSerializer(read_only=True)
    call_records = InlineCallRecordSerializer(many=True, read_only=True)
    scorecards = InlineScorecardSerializer(many=True, read_only=True)
    interviews = InlineInterviewSerializer(many=True, read_only=True)

    class Meta:
        model = Application
        fields = [
            "id",
            "tenant_id",
            "owner_user_id",
            "job",
            "job_id",
            "applicant",
            "applicant_id",
            "status",
            "score",
            "rejection_reason",
            "notes",
            "metadata",
            "call_records",
            "scorecards",
            "interviews",
            "created_at",
            "updated_at",
        ]
        read_only_fields = [
            "id",
            "tenant_id",
            "owner_user_id",
            "call_records",
            "scorecards",
            "interviews",
            "created_at",
            "updated_at",
        ]


class ApplicationCreateSerializer(serializers.ModelSerializer):
    class Meta:
        model = Application
        fields = [
            "job",
            "applicant",
            "status",
            "score",
            "rejection_reason",
            "notes",
            "metadata",
        ]


class ChangeStatusSerializer(serializers.Serializer):
    status = serializers.ChoiceField(choices=Application.Status.choices)
    reason = serializers.CharField(required=False, allow_blank=True, default="")


class BulkActionSerializer(serializers.Serializer):
    application_ids = serializers.ListField(child=serializers.UUIDField(), min_length=1)
    action = serializers.ChoiceField(choices=[("change_status", "Change Status")])
    status = serializers.ChoiceField(choices=Application.Status.choices, required=False)


class TriggerAICallResponseSerializer(serializers.Serializer):
    """Response shape for trigger-ai-call action — matches CallRecordDetailSerializer."""
    id = serializers.UUIDField()
    application_id = serializers.UUIDField()
    provider = serializers.CharField()
    status = serializers.CharField()
    phone = serializers.CharField()
    voice_agent_id = serializers.CharField()
    provider_call_id = serializers.CharField()
    created_at = serializers.DateTimeField()
