"""Application model signals."""
import logging

from django.db.models import F
from django.db.models.signals import post_delete, post_save
from django.dispatch import receiver

logger = logging.getLogger(__name__)


@receiver(post_save, sender="applications.Application")
def on_application_saved(sender, instance, created, **kwargs):
    """Handle Application create and status changes."""
    from jobs.models import Job
    from notifications.models import Notification
    from notifications.services import create_notification

    if created:
        # Increment job application_count
        Job.objects.filter(
            id=instance.job_id,
            tenant_id=instance.tenant_id,
        ).update(application_count=F("application_count") + 1)

        # Notify job owner
        try:
            job = instance.job
            applicant = instance.applicant
            create_notification(
                tenant_id=str(instance.tenant_id),
                owner_user_id=str(instance.owner_user_id),
                recipient_user_id=str(instance.owner_user_id),
                notification_type=Notification.NotificationType.IN_APP,
                category=Notification.Category.APPLICATION,
                title="New Application Received",
                message=f"{applicant.first_name} {applicant.last_name} applied for {job.title}",
                data={
                    "application_id": str(instance.id),
                    "job_id": str(instance.job_id),
                    "applicant_id": str(instance.applicant_id),
                },
            )
        except Exception as exc:
            logger.warning(f"Failed to create new-application notification: {exc}")
        return

    # Status change detection
    original_status = getattr(instance, "_original_status", None)
    if original_status is None or original_status == instance.status:
        return

    status = instance.status

    if status == "AI_SCREENING":
        # Dispatch AI call via Celery
        try:
            from calls.tasks import dispatch_ai_call
            dispatch_ai_call.apply_async(
                args=[str(instance.id), str(instance.tenant_id), str(instance.owner_user_id)],
                retry=False,
                broker_connection_timeout=3,
                broker_connection_retry=False,
            )
        except Exception as exc:
            logger.error(f"Failed to queue AI call dispatch for application {instance.id}: {exc}")

    elif status == "SHORTLISTED":
        _notify(instance, "Candidate Shortlisted",
                f"{instance.applicant.first_name} {instance.applicant.last_name} has been shortlisted")

    elif status == "REJECTED":
        _notify(instance, "Candidate Rejected",
                f"{instance.applicant.first_name} {instance.applicant.last_name} was rejected")

    elif status == "HIRED":
        _notify(instance, "Candidate Hired!",
                f"{instance.applicant.first_name} {instance.applicant.last_name} has been hired!")

    elif status == "AI_COMPLETED":
        score_str = f" — Score: {instance.score}" if instance.score else ""
        _notify(instance, "AI Screening Complete",
                f"AI screening complete for {instance.applicant.first_name} {instance.applicant.last_name}{score_str}")


@receiver(post_delete, sender="applications.Application")
def on_application_deleted(sender, instance, **kwargs):
    """Decrement job application_count on deletion."""
    from jobs.models import Job
    from django.db.models import F, Value
    from django.db.models.functions import Greatest
    Job.objects.filter(
        id=instance.job_id,
        tenant_id=instance.tenant_id,
    ).update(application_count=Greatest(F("application_count") - 1, Value(0)))


def _notify(instance, title: str, message: str) -> None:
    """Helper to create an in-app notification for the application owner."""
    from notifications.models import Notification
    from notifications.services import create_notification
    try:
        create_notification(
            tenant_id=str(instance.tenant_id),
            owner_user_id=str(instance.owner_user_id),
            recipient_user_id=str(instance.owner_user_id),
            notification_type=Notification.NotificationType.IN_APP,
            category=Notification.Category.APPLICATION,
            title=title,
            message=message,
            data={"application_id": str(instance.id)},
        )
    except Exception as exc:
        logger.warning(f"Failed to create notification '{title}': {exc}")
