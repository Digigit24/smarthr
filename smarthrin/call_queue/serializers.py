"""Serializers for CallQueue and CallQueueItem."""
from rest_framework import serializers

from .models import CallQueue, CallQueueItem


class CallQueueListSerializer(serializers.ModelSerializer):
    """Compact serializer for list views."""
    job_title = serializers.CharField(source="job.title", read_only=True)

    class Meta:
        model = CallQueue
        fields = [
            "id",
            "name",
            "job_title",
            "job_id",
            "voice_agent_id",
            "status",
            "total_queued",
            "total_called",
            "total_completed",
            "total_failed",
            "started_at",
            "completed_at",
            "created_at",
        ]
        read_only_fields = ["id", "created_at"]


class CallQueueDetailSerializer(serializers.ModelSerializer):
    """Full details including config and items summary."""
    job_title = serializers.CharField(source="job.title", read_only=True)
    config = serializers.SerializerMethodField()

    class Meta:
        model = CallQueue
        fields = [
            "id",
            "tenant_id",
            "owner_user_id",
            "name",
            "job_id",
            "job_title",
            "voice_agent_id",
            "status",
            "config",
            "total_queued",
            "total_called",
            "total_completed",
            "total_failed",
            "started_at",
            "completed_at",
            "created_at",
            "updated_at",
        ]
        read_only_fields = [
            "id",
            "tenant_id",
            "owner_user_id",
            "total_queued",
            "total_called",
            "total_completed",
            "total_failed",
            "started_at",
            "completed_at",
            "created_at",
            "updated_at",
        ]

    def get_config(self, obj: CallQueue) -> dict:
        return obj.get_config()


class CallQueueCreateSerializer(serializers.ModelSerializer):
    """Write serializer for creating a queue."""

    class Meta:
        model = CallQueue
        fields = [
            "name",
            "job",
            "voice_agent_id",
            "config",
        ]

    def validate_config(self, value: dict) -> dict:
        allowed_keys = {
            "max_concurrent_calls",
            "delay_between_calls_seconds",
            "max_retries",
            "call_window_start",
            "call_window_end",
            "timezone",
            "auto_shortlist_threshold",
            "auto_reject_threshold",
            "filter_statuses",
        }
        if value:
            unknown = set(value.keys()) - allowed_keys
            if unknown:
                raise serializers.ValidationError(
                    f"Unknown config keys: {unknown}. Allowed: {allowed_keys}"
                )
        return value


class CallQueueUpdateSerializer(serializers.ModelSerializer):
    """Write serializer for updating a queue config/name."""

    class Meta:
        model = CallQueue
        fields = ["name", "voice_agent_id", "config"]

    def validate_config(self, value: dict) -> dict:
        return CallQueueCreateSerializer().validate_config(value)


class CallQueueItemListSerializer(serializers.ModelSerializer):
    """Compact serializer for queue item list."""
    applicant_name = serializers.SerializerMethodField()
    applicant_email = serializers.SerializerMethodField()
    applicant_phone = serializers.SerializerMethodField()
    job_title = serializers.CharField(source="application.job.title", read_only=True)

    class Meta:
        model = CallQueueItem
        fields = [
            "id",
            "queue_id",
            "application_id",
            "applicant_name",
            "applicant_email",
            "applicant_phone",
            "job_title",
            "position",
            "status",
            "attempts",
            "score",
            "call_record_id",
            "last_attempt_at",
            "error_message",
            "completed_at",
            "created_at",
        ]
        read_only_fields = ["id", "created_at"]

    def get_applicant_name(self, obj: CallQueueItem) -> str:
        applicant = obj.application.applicant
        return f"{applicant.first_name} {applicant.last_name}".strip()

    def get_applicant_email(self, obj: CallQueueItem) -> str:
        return obj.application.applicant.email or ""

    def get_applicant_phone(self, obj: CallQueueItem) -> str:
        return obj.application.applicant.phone or ""
