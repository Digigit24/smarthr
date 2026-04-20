"""Celery tasks for AI call dispatch, scorecard generation, and status sync."""
import logging
from typing import Optional

from celery import shared_task
from celery.utils.log import get_task_logger

logger = get_task_logger(__name__)


def _mark_call_failed(application_id: str, tenant_id: str, error_message: str) -> None:
    """Mark any queued/initiated calls as FAILED and reset application to APPLIED."""
    from applications.models import Application
    from .models import CallRecord

    CallRecord.objects.filter(
        application_id=application_id,
        tenant_id=tenant_id,
        status__in=["QUEUED", "INITIATED", "RINGING"],
    ).update(status="FAILED", error_message=error_message)

    Application.objects.filter(
        id=application_id,
        tenant_id=tenant_id,
        status="AI_SCREENING",
    ).update(status="APPLIED")


@shared_task(bind=True, max_retries=3, default_retry_delay=10)
def dispatch_ai_call(self, application_id: str, tenant_id: str, owner_user_id: str) -> str:
    """
    Dispatch an AI screening call via the Voice AI Orchestrator.
    Called when Application.status changes to AI_SCREENING (via signal or API).
    Retries up to 3 times with exponential backoff on transient failures.
    """
    from integrations.exceptions import VoiceAICredentialsMissing, VoiceAIProviderError
    from .services import AIScreeningService

    logger.info(f"Dispatching AI call for application={application_id}, tenant={tenant_id}")

    try:
        service = AIScreeningService()
        call_record = service.trigger_screening_call(application_id, tenant_id, owner_user_id)
        logger.info(
            f"AI call dispatched: call_record={call_record.id}, "
            f"provider_call_id={call_record.provider_call_id}"
        )
        return str(call_record.id)

    except VoiceAIProviderError as exc:
        logger.warning(f"Provider error for application {application_id}: {exc}")
        countdown = 2 ** self.request.retries * 10
        raise self.retry(exc=exc, countdown=countdown)

    except VoiceAICredentialsMissing as exc:
        logger.error(f"Credentials missing for tenant {tenant_id}: {exc}")
        _mark_call_failed(application_id, tenant_id, str(exc))
        raise  # Do NOT retry — credentials must be configured manually

    except ValueError as exc:
        # Validation error (no phone, no agent, etc.) — don't retry
        logger.error(f"Validation error for application {application_id}: {exc}")
        _mark_call_failed(application_id, tenant_id, str(exc))
        raise

    except Exception as exc:
        logger.exception(f"Unexpected error dispatching AI call for application {application_id}")
        _mark_call_failed(application_id, tenant_id, str(exc))
        raise


@shared_task(bind=True, max_retries=2, default_retry_delay=30)
def generate_scorecard(self, call_record_id: str, tenant_id: str) -> Optional[str]:
    """
    Generate a Scorecard from a completed call's raw response data.
    Called when CallRecord.status changes to COMPLETED (via signal).
    """
    from .models import CallRecord, Scorecard

    logger.info(f"Generating scorecard for call_record={call_record_id}")

    try:
        call_record = CallRecord.objects.select_related("application").get(
            id=call_record_id,
            tenant_id=tenant_id,
        )
    except CallRecord.DoesNotExist:
        logger.error(f"CallRecord {call_record_id} not found")
        return None

    # Avoid duplicate scorecards (idempotent)
    if Scorecard.objects.filter(call_record=call_record).exists():
        logger.info(f"Scorecard already exists for call_record={call_record_id}")
        return None

    # Extract scores from raw_response (Voice AI may send structured scores)
    from .scoring import normalize_score, compute_overall_score, compute_recommendation

    raw = call_record.raw_response or {}
    scores = raw.get("scores", raw.get("score", {})) or {}

    comm_score = normalize_score(float(scores.get("communication", scores.get("communicationScore", 0)) or 0))
    know_score = normalize_score(float(scores.get("knowledge", scores.get("knowledgeScore", 0)) or 0))
    conf_score = normalize_score(float(scores.get("confidence", scores.get("confidenceScore", 0)) or 0))
    rel_score = normalize_score(float(scores.get("relevance", scores.get("relevanceScore", 0)) or 0))

    fallback_overall = normalize_score(float(scores.get("overall", scores.get("overallScore", 0)) or 0))
    overall = compute_overall_score(comm_score, know_score, conf_score, rel_score, fallback_overall)

    recommendation = getattr(Scorecard.Recommendation, compute_recommendation(overall))

    try:
        scorecard = Scorecard.objects.create(
            application=call_record.application,
            call_record=call_record,
            tenant_id=call_record.tenant_id,
            owner_user_id=call_record.owner_user_id,
            communication_score=comm_score,
            knowledge_score=know_score,
            confidence_score=conf_score,
            relevance_score=rel_score,
            overall_score=overall,
            summary=raw.get("summary", call_record.summary) or "",
            strengths=scores.get("strengths", []) or [],
            weaknesses=scores.get("weaknesses", []) or [],
            recommendation=recommendation,
            detailed_feedback=scores.get("detailed_feedback", {}) or {},
        )
        logger.info(f"Scorecard {scorecard.id} created for call_record={call_record_id}, score={overall}")
        return str(scorecard.id)

    except Exception as exc:
        logger.exception(f"Failed to create scorecard for call_record={call_record_id}")
        raise self.retry(exc=exc)


@shared_task
def sync_call_status(call_record_id: str, tenant_id: str) -> None:
    """
    Poll Voice AI for current call status and update local record.
    Used as a fallback when webhooks don't arrive within expected time.
    """
    from .services import AIScreeningService
    from integrations.exceptions import VoiceAIError

    try:
        service = AIScreeningService()
        service.get_call_status(call_record_id, tenant_id)
        logger.info(f"Synced call status for call_record={call_record_id}")
    except VoiceAIError as exc:
        logger.warning(f"Could not sync call status for {call_record_id}: {exc}")
    except Exception as exc:
        logger.exception(f"Unexpected error syncing call status for {call_record_id}")


@shared_task
def mark_stale_calls_failed() -> int:
    """
    Periodic task: auto-fail any in-flight CallRecord whose created_at is older
    than CALL_STALE_THRESHOLD_MINUTES. This guarantees that the frontend stale
    timer ("INITIATED → FAILED after 5 minutes") is honored by the backend even
    when no new call is dispatched to trigger on-demand reaping, and when the
    provider fails to deliver a terminal webhook.

    Returns the number of records reaped.
    """
    from .services import reap_stale_calls

    reaped = reap_stale_calls()
    if reaped:
        logger.info(f"mark_stale_calls_failed: reaped {len(reaped)} stale call(s)")
    return len(reaped)


@shared_task
def send_interview_notification_email(interview_id: str) -> None:
    """
    STUB: Logs interview notification intent.
    Phase 2: Implement actual email via SendGrid/SMTP with proper templates.
    """
    from interviews.models import Interview

    try:
        interview = Interview.objects.select_related("application__applicant", "application__job").get(
            id=interview_id
        )
        applicant = interview.application.applicant
        job = interview.application.job
        logger.info(
            f"[STUB] Would send interview notification email: "
            f"interview={interview_id}, type={interview.interview_type}, "
            f"applicant={applicant.first_name} {applicant.last_name}, "
            f"job={job.title}, scheduled={interview.scheduled_at}, "
            f"interviewer_email={interview.interviewer_email}"
        )
    except Interview.DoesNotExist:
        logger.warning(f"Interview {interview_id} not found for email notification stub")
    except Exception as exc:
        logger.exception(f"Error in send_interview_notification_email stub for {interview_id}")
