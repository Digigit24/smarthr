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


class CallRecordDetailSerializer(serializers.ModelSerializer):
    """Full serializer for CallRecord detail views — includes nested scorecard."""

    scorecard = serializers.SerializerMethodField()

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
