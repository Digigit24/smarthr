"""Serializers for the PipelineStage model."""
from rest_framework import serializers

from .models import PipelineStage


class PipelineStageSerializer(serializers.ModelSerializer):
    """Full serializer for PipelineStage — used for all actions."""

    class Meta:
        model = PipelineStage
        fields = [
            "id",
            "tenant_id",
            "owner_user_id",
            "name",
            "slug",
            "order",
            "color",
            "is_default",
            "is_terminal",
            "auto_action",
            "created_at",
            "updated_at",
        ]
        read_only_fields = ["id", "tenant_id", "owner_user_id", "created_at", "updated_at"]
