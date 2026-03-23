"""SendGrid email delivery for notifications."""
import logging
from typing import Optional

from django.conf import settings
from django.template.loader import render_to_string
from django.utils.html import strip_tags

logger = logging.getLogger(__name__)


def send_email(
    *,
    to_email: str,
    subject: str,
    template_name: str,
    context: dict,
    sendgrid_template_id: str = "",
) -> bool:
    """
    Send an email via SendGrid.

    If sendgrid_template_id is provided, uses SendGrid dynamic templates.
    Otherwise renders a Django template and sends as HTML.

    Returns True on success, False on failure.
    """
    api_key = getattr(settings, "SENDGRID_API_KEY", "")
    if not api_key:
        logger.warning("SENDGRID_API_KEY not configured — skipping email to %s", to_email)
        return False

    try:
        import sendgrid
        from sendgrid.helpers.mail import Mail, Email, To, Content, HtmlContent
    except ImportError:
        logger.error("sendgrid package not installed — run: pip install sendgrid")
        return False

    from_email = Email(
        getattr(settings, "SENDGRID_FROM_EMAIL", "notifications@smarthr.in"),
        getattr(settings, "SENDGRID_FROM_NAME", "SmartHR-In"),
    )

    try:
        sg = sendgrid.SendGridAPIClient(api_key=api_key)

        if sendgrid_template_id:
            # Use SendGrid dynamic template
            message = Mail(
                from_email=from_email,
                to_emails=To(to_email),
            )
            message.template_id = sendgrid_template_id
            message.dynamic_template_data = context
        else:
            # Render Django template
            html_content = render_to_string(template_name, context)
            plain_content = strip_tags(html_content)

            message = Mail(
                from_email=from_email,
                to_emails=To(to_email),
                subject=subject,
                plain_text_content=plain_content,
                html_content=html_content,
            )

        response = sg.send(message)
        logger.info(
            "Email sent to %s (subject=%s, status=%s)",
            to_email, subject, response.status_code,
        )
        return 200 <= response.status_code < 300

    except Exception as exc:
        logger.exception("Failed to send email to %s: %s", to_email, exc)
        return False


def send_new_application_email(
    *,
    to_email: str,
    applicant_name: str,
    job_title: str,
    application_id: str,
    dashboard_url: str = "",
) -> bool:
    """Send 'New Application Received' email to recruiter."""
    context = {
        "applicant_name": applicant_name,
        "job_title": job_title,
        "application_id": application_id,
        "dashboard_url": dashboard_url,
    }
    return send_email(
        to_email=to_email,
        subject=f"New Application: {applicant_name} applied for {job_title}",
        template_name="notifications/email/new_application.html",
        context=context,
        sendgrid_template_id=getattr(settings, "SENDGRID_TEMPLATE_NEW_APPLICATION", ""),
    )


def send_ai_screening_complete_email(
    *,
    to_email: str,
    applicant_name: str,
    job_title: str,
    score: Optional[str] = None,
    application_id: str,
    dashboard_url: str = "",
) -> bool:
    """Send 'AI Screening Complete' email to recruiter."""
    context = {
        "applicant_name": applicant_name,
        "job_title": job_title,
        "score": score,
        "application_id": application_id,
        "dashboard_url": dashboard_url,
    }
    return send_email(
        to_email=to_email,
        subject=f"AI Screening Complete: {applicant_name} for {job_title}",
        template_name="notifications/email/ai_screening_complete.html",
        context=context,
        sendgrid_template_id=getattr(settings, "SENDGRID_TEMPLATE_AI_SCREENING_COMPLETE", ""),
    )


def send_interview_scheduled_email(
    *,
    to_email: str,
    applicant_name: str,
    job_title: str,
    interview_type: str,
    scheduled_at: str,
    interviewer_name: str = "",
    meeting_link: str = "",
    interview_id: str,
    dashboard_url: str = "",
) -> bool:
    """Send 'Interview Scheduled' email to recruiter/interviewer."""
    context = {
        "applicant_name": applicant_name,
        "job_title": job_title,
        "interview_type": interview_type,
        "scheduled_at": scheduled_at,
        "interviewer_name": interviewer_name,
        "meeting_link": meeting_link,
        "interview_id": interview_id,
        "dashboard_url": dashboard_url,
    }
    return send_email(
        to_email=to_email,
        subject=f"Interview Scheduled: {applicant_name} — {interview_type}",
        template_name="notifications/email/interview_scheduled.html",
        context=context,
        sendgrid_template_id=getattr(settings, "SENDGRID_TEMPLATE_INTERVIEW_SCHEDULED", ""),
    )


def send_interview_reminder_email(
    *,
    to_email: str,
    applicant_name: str,
    job_title: str,
    interview_type: str,
    scheduled_at: str,
    interviewer_name: str = "",
    meeting_link: str = "",
    interview_id: str,
    dashboard_url: str = "",
) -> bool:
    """Send '24h Interview Reminder' email to recruiter/interviewer."""
    context = {
        "applicant_name": applicant_name,
        "job_title": job_title,
        "interview_type": interview_type,
        "scheduled_at": scheduled_at,
        "interviewer_name": interviewer_name,
        "meeting_link": meeting_link,
        "interview_id": interview_id,
        "dashboard_url": dashboard_url,
    }
    return send_email(
        to_email=to_email,
        subject=f"Reminder: Interview with {applicant_name} tomorrow",
        template_name="notifications/email/interview_reminder.html",
        context=context,
        sendgrid_template_id=getattr(settings, "SENDGRID_TEMPLATE_INTERVIEW_REMINDER", ""),
    )
