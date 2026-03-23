"""Notification Celery tasks — creation + email delivery."""
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
    """Create a notification record and deliver via email if type is EMAIL."""
    from django.utils import timezone

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

        if notification_type == "EMAIL":
            _deliver_email(notif, data or {})

        return str(notif.id)
    except Exception as exc:
        logger.error(f"send_notification task failed: {exc}")
        raise self.retry(exc=exc, countdown=30)


def _deliver_email(notification, data: dict) -> None:
    """Dispatch email based on notification category and data context."""
    from django.utils import timezone

    recipient_email = data.get("recipient_email")
    if not recipient_email:
        logger.warning(
            "No recipient_email in notification data for %s — cannot send email",
            notification.id,
        )
        return

    email_type = data.get("email_type", "")

    try:
        from .email import (
            send_new_application_email,
            send_ai_screening_complete_email,
            send_interview_scheduled_email,
            send_interview_reminder_email,
            send_email,
        )

        sent = False

        if email_type == "new_application":
            sent = send_new_application_email(
                to_email=recipient_email,
                applicant_name=data.get("applicant_name", ""),
                job_title=data.get("job_title", ""),
                application_id=data.get("application_id", ""),
                dashboard_url=data.get("dashboard_url", ""),
            )

        elif email_type == "ai_screening_complete":
            sent = send_ai_screening_complete_email(
                to_email=recipient_email,
                applicant_name=data.get("applicant_name", ""),
                job_title=data.get("job_title", ""),
                score=data.get("score"),
                application_id=data.get("application_id", ""),
                dashboard_url=data.get("dashboard_url", ""),
            )

        elif email_type == "interview_scheduled":
            sent = send_interview_scheduled_email(
                to_email=recipient_email,
                applicant_name=data.get("applicant_name", ""),
                job_title=data.get("job_title", ""),
                interview_type=data.get("interview_type", ""),
                scheduled_at=data.get("scheduled_at", ""),
                interviewer_name=data.get("interviewer_name", ""),
                meeting_link=data.get("meeting_link", ""),
                interview_id=data.get("interview_id", ""),
                dashboard_url=data.get("dashboard_url", ""),
            )

        elif email_type == "interview_reminder":
            sent = send_interview_reminder_email(
                to_email=recipient_email,
                applicant_name=data.get("applicant_name", ""),
                job_title=data.get("job_title", ""),
                interview_type=data.get("interview_type", ""),
                scheduled_at=data.get("scheduled_at", ""),
                interviewer_name=data.get("interviewer_name", ""),
                meeting_link=data.get("meeting_link", ""),
                interview_id=data.get("interview_id", ""),
                dashboard_url=data.get("dashboard_url", ""),
            )

        else:
            # Generic email fallback — render notification message as plain email
            sent = send_email(
                to_email=recipient_email,
                subject=notification.title,
                template_name="notifications/email/base.html",
                context={"content_text": notification.message, **data},
            )

        if sent:
            notification.sent_at = timezone.now()
            notification.save(update_fields=["sent_at", "updated_at"])
            logger.info("Email delivered for notification %s", notification.id)
        else:
            logger.warning("Email delivery returned False for notification %s", notification.id)

    except Exception as exc:
        logger.exception("Email delivery failed for notification %s: %s", notification.id, exc)


@shared_task
def send_interview_reminders() -> int:
    """
    Periodic task: find interviews scheduled ~24h from now and send reminder emails.
    Runs every 15 minutes. Sends reminders for interviews between 23h45m and 24h15m away.
    Only sends if a reminder hasn't already been sent (tracked via interview metadata).
    """
    from datetime import timedelta

    from django.utils import timezone

    from interviews.models import Interview
    from .models import Notification

    now = timezone.now()
    window_start = now + timedelta(hours=23, minutes=45)
    window_end = now + timedelta(hours=24, minutes=15)

    interviews = (
        Interview.objects.filter(
            scheduled_at__gte=window_start,
            scheduled_at__lte=window_end,
            status__in=["SCHEDULED", "CONFIRMED"],
        )
        .select_related("application__applicant", "application__job")
    )

    sent_count = 0
    for interview in interviews:
        # Check if reminder already sent for this interview
        already_sent = Notification.objects.filter(
            tenant_id=interview.tenant_id,
            category=Notification.Category.INTERVIEW,
            data__email_type="interview_reminder",
            data__interview_id=str(interview.id),
        ).exists()
        if already_sent:
            continue

        applicant = interview.application.applicant
        job = interview.application.job

        # Send to the interview owner / recruiter
        data = {
            "email_type": "interview_reminder",
            "recipient_email": interview.interviewer_email or "",
            "applicant_name": f"{applicant.first_name} {applicant.last_name}",
            "job_title": job.title,
            "interview_type": interview.interview_type,
            "scheduled_at": interview.scheduled_at.strftime("%Y-%m-%d %H:%M UTC"),
            "interviewer_name": interview.interviewer_name,
            "meeting_link": interview.meeting_link,
            "interview_id": str(interview.id),
            "application_id": str(interview.application_id),
        }

        if not data["recipient_email"]:
            logger.info(
                "Skipping interview reminder for %s — no interviewer email", interview.id
            )
            continue

        send_notification.delay(
            tenant_id=str(interview.tenant_id),
            recipient_user_id=str(interview.interviewer_user_id or interview.owner_user_id),
            notification_type="EMAIL",
            title=f"Reminder: Interview with {applicant.first_name} {applicant.last_name} tomorrow",
            message=(
                f"You have a {interview.interview_type} interview with "
                f"{applicant.first_name} {applicant.last_name} for {job.title} "
                f"scheduled at {interview.scheduled_at.strftime('%Y-%m-%d %H:%M UTC')}."
            ),
            data=data,
            category="INTERVIEW",
            owner_user_id=str(interview.owner_user_id),
        )
        sent_count += 1

    logger.info("Interview reminder task: %d reminders queued", sent_count)
    return sent_count
