"""CallRecord and Scorecard model signals."""
import logging

from django.conf import settings
from django.db.models.signals import post_save
from django.dispatch import receiver

logger = logging.getLogger(__name__)


@receiver(post_save, sender="calls.CallRecord")
def on_call_record_saved(sender, instance, created, **kwargs):
    """Handle CallRecord status changes."""
    if created:
        return

    original_status = getattr(instance, "_original_status", None)
    if original_status is None or original_status == instance.status:
        return

    status = instance.status

    if status == "COMPLETED" and instance.transcript:
        # Queue scorecard generation
        try:
            from calls.tasks import generate_scorecard
            generate_scorecard.delay(str(instance.id), str(instance.tenant_id))
        except Exception as exc:
            logger.error(f"Failed to queue scorecard generation for call {instance.id}: {exc}")

    elif status == "FAILED":
        _notify_call_failed(instance)
        # Reset application status to APPLIED if it was AI_SCREENING
        try:
            app = instance.application
            if app.status == "AI_SCREENING":
                app.status = "APPLIED"
                app.save(update_fields=["status", "updated_at"])
        except Exception as exc:
            logger.warning(f"Failed to reset application status after call failure: {exc}")


@receiver(post_save, sender="calls.Scorecard")
def on_scorecard_saved(sender, instance, created, **kwargs):
    """When a Scorecard is created, update Application score and auto-route."""
    if not created:
        return

    try:
        application = instance.application
        overall = float(instance.overall_score or 0)

        auto_shortlist = float(getattr(settings, "AUTO_SHORTLIST_THRESHOLD", 7.0))
        auto_reject = float(getattr(settings, "AUTO_REJECT_THRESHOLD", 4.0))

        # Check per-job config for thresholds
        job = application.job
        job_config = job.voice_agent_config or {}
        auto_shortlist = float(job_config.get("auto_shortlist_threshold", auto_shortlist))
        auto_reject = float(job_config.get("auto_reject_threshold", auto_reject))

        application.score = instance.overall_score

        if overall >= auto_shortlist:
            application.status = "SHORTLISTED"
        elif overall < auto_reject:
            application.status = "REJECTED"
            application.rejection_reason = "Below AI screening threshold"
        else:
            application.status = "AI_COMPLETED"

        application.save(update_fields=["score", "status", "rejection_reason", "updated_at"])

        logger.info(
            f"Scorecard auto-routing: application={application.id}, "
            f"score={overall}, new_status={application.status}"
        )

    except Exception as exc:
        logger.exception(f"Error in scorecard post-save signal for scorecard {instance.id}: {exc}")


def _notify_call_failed(instance) -> None:
    from notifications.models import Notification
    from notifications.services import create_notification
    try:
        applicant = instance.application.applicant
        create_notification(
            tenant_id=str(instance.tenant_id),
            owner_user_id=str(instance.owner_user_id),
            recipient_user_id=str(instance.owner_user_id),
            notification_type=Notification.NotificationType.IN_APP,
            category=Notification.Category.CALL,
            title="AI Call Failed",
            message=f"AI screening call failed for {applicant.first_name} {applicant.last_name}",
            data={"call_record_id": str(instance.id), "application_id": str(instance.application_id)},
        )
    except Exception as exc:
        logger.warning(f"Failed to create call-failed notification: {exc}")
