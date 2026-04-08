"""Serializers for CallRecord and Scorecard models."""
from rest_framework import serializers

from .models import CallRecord, Scorecard
from .services import (
    compute_call_stale_at,
    compute_seconds_until_stale,
    get_call_stale_threshold_minutes,
)


class _CallStaleFieldsMixin:
    """
    Adds stale_at / seconds_until_stale / stale_threshold_minutes fields to a
    CallRecord serializer so the frontend can render a "minutes until you can
    re-trigger" countdown without computing the threshold itself.
    """

    def get_stale_at(self, obj):
        stale_at = compute_call_stale_at(obj)
        return stale_at.isoformat() if stale_at else None

    def get_seconds_until_stale(self, obj):
        return compute_seconds_until_stale(obj)

    def get_stale_threshold_minutes(self, obj):
        return get_call_stale_threshold_minutes()


class ScorecardSerializer(serializers.ModelSerializer):
    """Full serializer for Scorecard — used for create/update and nested detail."""

    class Meta:
        model = Scorecard
        fields = [
            "id",
            "tenant_id",
            "owner_user_id",
            "application_id",
            "call_record_id",
            "communication_score",
            "knowledge_score",
            "confidence_score",
            "relevance_score",
            "overall_score",
            "summary",
            "strengths",
            "weaknesses",
            "recommendation",
            "detailed_feedback",
            "created_at",
            "updated_at",
        ]
        read_only_fields = ["id", "tenant_id", "owner_user_id", "created_at", "updated_at"]


class ScorecardListSerializer(serializers.ModelSerializer):
    """Compact serializer for Scorecard list views."""

    class Meta:
        model = Scorecard
        fields = [
            "id",
            "application_id",
            "overall_score",
            "communication_score",
            "knowledge_score",
            "confidence_score",
            "relevance_score",
            "recommendation",
            "summary",
            "created_at",
        ]
        read_only_fields = ["id", "created_at"]


class CallRecordListSerializer(_CallStaleFieldsMixin, serializers.ModelSerializer):
    """Compact serializer for CallRecord list views."""

    stale_at = serializers.SerializerMethodField()
    seconds_until_stale = serializers.SerializerMethodField()
    stale_threshold_minutes = serializers.SerializerMethodField()

    class Meta:
        model = CallRecord
        fields = [
            "id",
            "application_id",
            "provider",
            "status",
            "phone",
            "duration",
            "summary",
            "started_at",
            "ended_at",
            "created_at",
            "provider_call_id",
            "voice_agent_id",
            "stale_at",
            "seconds_until_stale",
            "stale_threshold_minutes",
        ]
        read_only_fields = ["id", "created_at"]


class CallRecordQueueItemSerializer(serializers.Serializer):
    """Nested queue item info for call record detail."""
    queue_item_id = serializers.UUIDField()
    queue_id = serializers.UUIDField()
    queue_name = serializers.CharField()
    position = serializers.IntegerField()


class CallRecordDetailSerializer(_CallStaleFieldsMixin, serializers.ModelSerializer):
    """Full serializer for CallRecord detail views — includes nested scorecard and queue info."""

    scorecard = serializers.SerializerMethodField()
    queue_item = serializers.SerializerMethodField()
    applicant_name = serializers.SerializerMethodField()
    applicant_email = serializers.SerializerMethodField()
    job_title = serializers.SerializerMethodField()
    stale_at = serializers.SerializerMethodField()
    seconds_until_stale = serializers.SerializerMethodField()
    stale_threshold_minutes = serializers.SerializerMethodField()

    class Meta:
        model = CallRecord
        fields = [
            "id",
            "tenant_id",
            "owner_user_id",
            "application_id",
            "applicant_name",
            "applicant_email",
            "job_title",
            "provider",
            "voice_agent_id",
            "provider_call_id",
            "phone",
            "status",
            "duration",
            "transcript",
            "recording_url",
            "summary",
            "raw_response",
            "started_at",
            "ended_at",
            "error_message",
            "created_at",
            "updated_at",
            "scorecard",
            "queue_item",
            "stale_at",
            "seconds_until_stale",
            "stale_threshold_minutes",
        ]
        read_only_fields = [
            "id",
            "tenant_id",
            "owner_user_id",
            "created_at",
            "updated_at",
        ]

    def get_applicant_name(self, obj):
        try:
            return obj.application.applicant.full_name
        except AttributeError:
            return None

    def get_applicant_email(self, obj):
        try:
            return obj.application.applicant.email
        except AttributeError:
            return None

    def get_job_title(self, obj):
        try:
            return obj.application.job.title
        except AttributeError:
            return None

    def get_scorecard(self, call_record: CallRecord):
        scorecard = call_record.scorecard.first()
        if scorecard is None:
            return None
        return ScorecardSerializer(scorecard, context=self.context).data

    def get_queue_item(self, call_record: CallRecord):
        queue_item = call_record.queue_items.select_related("queue").first()
        if queue_item is None:
            return None
        return {
            "queue_item_id": str(queue_item.id),
            "queue_id": str(queue_item.queue_id),
            "queue_name": queue_item.queue.name,
            "position": queue_item.position,
        }


class CallRecordUpdateStatusSerializer(serializers.Serializer):
    """Request body for update-status action."""
    status = serializers.ChoiceField(choices=CallRecord.Status.choices)


class RetryCallSerializer(serializers.Serializer):
    """Request body for retry-call action (no required fields)."""
    pass


class AvailableAgentSerializer(serializers.Serializer):
    """Represents a single Voice AI agent returned by the orchestrator."""
    id = serializers.CharField()
    name = serializers.CharField()
    provider = serializers.CharField()
    is_active = serializers.SerializerMethodField()
    description = serializers.CharField(allow_blank=True, default="")
    created_at = serializers.CharField(allow_null=True)

    def get_is_active(self, obj):
        if isinstance(obj, dict):
            return obj.get("is_active", True)
        return getattr(obj, "is_active", True)


class CallRecordSerializer(_CallStaleFieldsMixin, serializers.ModelSerializer):
    """Alias used by applications/views.py trigger_ai_call for response."""

    stale_at = serializers.SerializerMethodField()
    seconds_until_stale = serializers.SerializerMethodField()
    stale_threshold_minutes = serializers.SerializerMethodField()

    class Meta:
        model = CallRecord
        fields = [
            "id", "application_id", "provider", "voice_agent_id",
            "provider_call_id", "phone", "status", "duration",
            "summary", "recording_url", "started_at", "ended_at",
            "error_message", "created_at", "updated_at",
            "stale_at", "seconds_until_stale", "stale_threshold_minutes",
        ]
        read_only_fields = ["id", "created_at", "updated_at"]
