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


def notify_with_email(
    *,
    tenant_id: str,
    owner_user_id: str,
    recipient_user_id: str,
    recipient_email: str,
    category: str,
    title: str,
    message: str,
    email_type: str,
    extra_data: Optional[dict] = None,
) -> None:
    """
    Create an IN_APP notification immediately, then queue an EMAIL notification
    via Celery for async SendGrid delivery.
    """
    data = extra_data or {}

    # 1. Create in-app notification synchronously
    create_notification(
        tenant_id=tenant_id,
        owner_user_id=owner_user_id,
        recipient_user_id=recipient_user_id,
        notification_type=Notification.NotificationType.IN_APP,
        category=category,
        title=title,
        message=message,
        data=data,
    )

    # 2. Queue email notification for async delivery
    from .tasks import send_notification

    email_data = {
        **data,
        "email_type": email_type,
        "recipient_email": recipient_email,
    }

    send_notification.delay(
        tenant_id=tenant_id,
        recipient_user_id=recipient_user_id,
        notification_type="EMAIL",
        title=title,
        message=message,
        data=email_data,
        category=category,
        owner_user_id=owner_user_id,
    )
