"""Serializers for CallRecord and Scorecard models."""
from rest_framework import serializers

from .models import CallRecord, Scorecard


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


class CallRecordListSerializer(serializers.ModelSerializer):
    """Compact serializer for CallRecord list views."""

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
        ]
        read_only_fields = ["id", "created_at"]


class CallRecordQueueItemSerializer(serializers.Serializer):
    """Nested queue item info for call record detail."""
    queue_item_id = serializers.UUIDField()
    queue_id = serializers.UUIDField()
    queue_name = serializers.CharField()
    position = serializers.IntegerField()


class CallRecordDetailSerializer(serializers.ModelSerializer):
    """Full serializer for CallRecord detail views — includes nested scorecard and queue info."""

    scorecard = serializers.SerializerMethodField()
    queue_item = serializers.SerializerMethodField()

    class Meta:
        model = CallRecord
        fields = [
            "id",
            "tenant_id",
            "owner_user_id",
            "application_id",
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
        ]
        read_only_fields = [
            "id",
            "tenant_id",
            "owner_user_id",
            "created_at",
            "updated_at",
        ]

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


class RetryCallSerializer(serializers.Serializer):
    """Request body for retry-call action (no required fields)."""
    pass


class AvailableAgentSerializer(serializers.Serializer):
    """Represents a single Voice AI agent returned by the orchestrator."""
    id = serializers.CharField()
    name = serializers.CharField()
    provider = serializers.CharField()
    is_active = serializers.BooleanField()
    description = serializers.CharField(allow_blank=True, default="")
    created_at = serializers.CharField(allow_null=True)


class CallRecordSerializer(serializers.ModelSerializer):
    """Alias used by applications/views.py trigger_ai_call for response."""
    class Meta:
        model = CallRecord
        fields = [
            "id", "application_id", "provider", "voice_agent_id",
            "provider_call_id", "phone", "status", "duration",
            "summary", "recording_url", "started_at", "ended_at",
            "error_message", "created_at", "updated_at",
        ]
        read_only_fields = ["id", "created_at", "updated_at"]
