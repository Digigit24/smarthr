"""Job model signals."""
import logging

from django.db.models.signals import post_save
from django.dispatch import receiver
from django.utils import timezone

logger = logging.getLogger(__name__)


@receiver(post_save, sender="jobs.Job")
def on_job_saved(sender, instance, created, **kwargs):
    """Handle Job status changes."""
    if created:
        return

    original_status = getattr(instance, "_original_status", None)
    if original_status is None or original_status == instance.status:
        return

    from notifications.models import Notification
    from notifications.services import create_notification

    if instance.status == "OPEN":
        # Set published_at if not already set
        if not instance.published_at:
            instance.__class__.objects.filter(id=instance.id).update(
                published_at=timezone.now()
            )
        try:
            create_notification(
                tenant_id=str(instance.tenant_id),
                owner_user_id=str(instance.owner_user_id),
                recipient_user_id=str(instance.owner_user_id),
                notification_type=Notification.NotificationType.IN_APP,
                category=Notification.Category.SYSTEM,
                title="Job Published",
                message=f"Job '{instance.title}' is now live and accepting applications",
                data={"job_id": str(instance.id)},
            )
        except Exception as exc:
            logger.warning(f"Failed to create job-published notification: {exc}")

    elif instance.status == "CLOSED":
        try:
            create_notification(
                tenant_id=str(instance.tenant_id),
                owner_user_id=str(instance.owner_user_id),
                recipient_user_id=str(instance.owner_user_id),
                notification_type=Notification.NotificationType.IN_APP,
                category=Notification.Category.SYSTEM,
                title="Job Closed",
                message=f"Job '{instance.title}' has been closed",
                data={"job_id": str(instance.id)},
            )
        except Exception as exc:
            logger.warning(f"Failed to create job-closed notification: {exc}")
