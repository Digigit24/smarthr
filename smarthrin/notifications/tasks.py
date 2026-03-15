from celery import shared_task
from celery.utils.log import get_task_logger

logger = get_task_logger(__name__)


@shared_task(bind=True, max_retries=3)
def send_notification(
    self,
    tenant_id: str,
    recipient_user_id: str,
    notification_type: str,
    title: str,
    message: str,
    data: dict | None = None,
    category: str = "SYSTEM",
    owner_user_id: str | None = None,
) -> str:
    """Create a notification record. Email/WhatsApp delivery is stubbed."""
    try:
        from .services import create_notification
        notif = create_notification(
            tenant_id=tenant_id,
            owner_user_id=owner_user_id or recipient_user_id,
            recipient_user_id=recipient_user_id,
            notification_type=notification_type,
            category=category,
            title=title,
            message=message,
            data=data or {},
        )
        logger.info(f"Notification {notif.id} created for user {recipient_user_id}")
        # TODO Phase 2: dispatch email via SendGrid / WhatsApp via Twilio
        return str(notif.id)
    except Exception as exc:
        logger.error(f"send_notification task failed: {exc}")
        raise self.retry(exc=exc, countdown=30)
