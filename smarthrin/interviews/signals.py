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
            job = instance.application.job

            # In-app notification for the owner/recruiter
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

        # Send email to interviewer (if email available)
        try:
            from notifications.tasks import send_notification
            applicant = instance.application.applicant
            job = instance.application.job

            email_recipient = instance.interviewer_email
            if email_recipient:
                email_data = {
                    "email_type": "interview_scheduled",
                    "recipient_email": email_recipient,
                    "applicant_name": f"{applicant.first_name} {applicant.last_name}",
                    "job_title": job.title,
                    "interview_type": instance.interview_type,
                    "scheduled_at": instance.scheduled_at.strftime("%Y-%m-%d %H:%M UTC"),
                    "interviewer_name": instance.interviewer_name,
                    "meeting_link": instance.meeting_link,
                    "interview_id": str(instance.id),
                    "application_id": str(instance.application_id),
                }
                send_notification.apply_async(
                    kwargs={
                        "tenant_id": str(instance.tenant_id),
                        "recipient_user_id": str(instance.interviewer_user_id or instance.owner_user_id),
                        "notification_type": "EMAIL",
                        "title": f"Interview Scheduled: {applicant.first_name} {applicant.last_name} — {instance.interview_type}",
                        "message": (
                            f"{instance.interview_type} interview with "
                            f"{applicant.first_name} {applicant.last_name} for {job.title} "
                            f"on {instance.scheduled_at.strftime('%Y-%m-%d %H:%M UTC')}"
                        ),
                        "data": email_data,
                        "category": "INTERVIEW",
                        "owner_user_id": str(instance.owner_user_id),
                    },
                    retry=False,
                    broker_connection_timeout=3,
                    broker_connection_retry=False,
                )
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
