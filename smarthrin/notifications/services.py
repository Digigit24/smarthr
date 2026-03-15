"""Notification creation service."""
from typing import Optional
from .models import Notification


def create_notification(
    *,
    tenant_id: str,
    owner_user_id: str,
    recipient_user_id: str,
    notification_type: str = Notification.NotificationType.IN_APP,
    category: str = Notification.Category.SYSTEM,
    title: str,
    message: str,
    data: Optional[dict] = None,
) -> Notification:
    return Notification.objects.create(
        tenant_id=tenant_id,
        owner_user_id=owner_user_id,
        recipient_user_id=recipient_user_id,
        notification_type=notification_type,
        category=category,
        title=title,
        message=message,
        data=data or {},
    )
