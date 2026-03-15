from rest_framework import serializers
from .models import Activity


class ActivitySerializer(serializers.ModelSerializer):
    class Meta:
        model = Activity
        fields = [
            "id", "tenant_id", "actor_user_id", "actor_email", "verb",
            "resource_type", "resource_id", "resource_label",
            "before", "after", "metadata", "created_at",
        ]
        read_only_fields = fields
