from rest_framework import serializers
from .models import Notification


class NotificationSerializer(serializers.ModelSerializer):
    class Meta:
        model = Notification
        fields = [
            "id", "recipient_user_id", "notification_type", "category",
            "title", "message", "data", "is_read", "read_at", "sent_at",
            "created_at", "updated_at",
        ]
        read_only_fields = ["id", "tenant_id", "owner_user_id", "created_at", "updated_at"]
