"""Notification model."""
import uuid

from django.db import models

from common.models import TenantBaseModel


class Notification(TenantBaseModel):
    class NotificationType(models.TextChoices):
        EMAIL = "EMAIL", "Email"
        WHATSAPP = "WHATSAPP", "WhatsApp"
        IN_APP = "IN_APP", "In App"

    class Category(models.TextChoices):
        APPLICATION = "APPLICATION", "Application"
        INTERVIEW = "INTERVIEW", "Interview"
        CALL = "CALL", "Call"
        SYSTEM = "SYSTEM", "System"

    recipient_user_id = models.UUIDField()
    notification_type = models.CharField(
        max_length=20, choices=NotificationType.choices, default=NotificationType.IN_APP
    )
    category = models.CharField(max_length=20, choices=Category.choices, default=Category.SYSTEM)
    title = models.CharField(max_length=255)
    message = models.TextField()
    data = models.JSONField(default=dict, blank=True)
    is_read = models.BooleanField(default=False)
    read_at = models.DateTimeField(null=True, blank=True)
    sent_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        db_table = "notifications"
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["tenant_id", "recipient_user_id", "is_read"]),
        ]

    def __str__(self) -> str:
        return f"[{self.category}] {self.title} → {self.recipient_user_id}"
