"""Interview model signals."""
import logging

from django.db.models.signals import post_save
from django.dispatch import receiver

logger = logging.getLogger(__name__)


@receiver(post_save, sender="interviews.Interview")
def on_interview_saved(sender, instance, created, **kwargs):
    """Handle Interview create and status changes."""
    from notifications.models import Notification
    from notifications.services import create_notification

    if created:
        try:
            applicant = instance.application.applicant
            create_notification(
                tenant_id=str(instance.tenant_id),
                owner_user_id=str(instance.owner_user_id),
                recipient_user_id=str(instance.owner_user_id),
                notification_type=Notification.NotificationType.IN_APP,
                category=Notification.Category.INTERVIEW,
                title="Interview Scheduled",
                message=(
                    f"{instance.interview_type} interview for "
                    f"{applicant.first_name} {applicant.last_name} "
                    f"on {instance.scheduled_at.strftime('%Y-%m-%d %H:%M UTC')}"
                ),
                data={"interview_id": str(instance.id), "application_id": str(instance.application_id)},
            )
        except Exception as exc:
            logger.warning(f"Failed to create interview-scheduled notification: {exc}")

        # Queue email notification stub
        try:
            from calls.tasks import send_interview_notification_email
            send_interview_notification_email.delay(str(instance.id))
        except Exception as exc:
            logger.warning(f"Failed to queue interview email task: {exc}")
        return

    # Status change detection
    original_status = getattr(instance, "_original_status", None)
    if original_status is None or original_status == instance.status:
        return

    if instance.status == "CANCELLED":
        try:
            applicant = instance.application.applicant
            from notifications.models import Notification
            from notifications.services import create_notification
            create_notification(
                tenant_id=str(instance.tenant_id),
                owner_user_id=str(instance.owner_user_id),
                recipient_user_id=str(instance.owner_user_id),
                notification_type=Notification.NotificationType.IN_APP,
                category=Notification.Category.INTERVIEW,
                title="Interview Cancelled",
                message=f"Interview cancelled for {applicant.first_name} {applicant.last_name}",
                data={"interview_id": str(instance.id), "application_id": str(instance.application_id)},
            )
        except Exception as exc:
            logger.warning(f"Failed to create interview-cancelled notification: {exc}")
