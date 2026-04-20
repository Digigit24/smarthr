"""Process incoming Voice AI webhook payloads."""
import logging
from typing import Any

logger = logging.getLogger(__name__)


def handle_call_completed(payload: dict[str, Any]) -> dict:
    """
    Process a call-completed webhook from Voice AI Orchestrator.

    payload keys: call_id, provider_call_id, transcript, duration, score,
    status, recording_url, summary, metadata: { applicationId, jobId }
    """
    from calls.models import CallRecord, Scorecard
    from applications.models import Application
    from notifications.services import create_notification
    from notifications.models import Notification

    provider_call_id = (
        payload.get("provider_call_id")
        or payload.get("call_id")
        or payload.get("id", "")
    )

    try:
        call_record = CallRecord.objects.get(provider_call_id=provider_call_id)
    except CallRecord.DoesNotExist:
        logger.warning(
            "call-completed webhook: CallRecord not found for provider_call_id=%r "
            "(payload keys=%s)",
            provider_call_id, sorted(payload.keys()),
        )
        return {"error": "CallRecord not found"}

    # 1. Update CallRecord
    call_record.transcript = payload.get("transcript", "")
    call_record.duration = payload.get("duration")
    call_record.status = CallRecord.Status.COMPLETED
    call_record.recording_url = payload.get("recording_url", "")
    call_record.summary = payload.get("summary", "")
    call_record.raw_response = payload
    call_record.save()

    # 2. Create Scorecard (if not already created by the Celery task).
    # Use normalize_score to ensure consistent 0-10 scale regardless of provider.
    # NOTE: Do NOT set application.status here — the on_scorecard_saved signal
    # handles auto-routing (SHORTLISTED / REJECTED / AI_COMPLETED) based on thresholds.
    score_data = payload.get("score", {})
    if score_data:
        from calls.scoring import normalize_score, compute_overall_score, compute_recommendation

        comm = normalize_score(float(score_data.get("communication", 0) or 0))
        know = normalize_score(float(score_data.get("knowledge", 0) or 0))
        conf = normalize_score(float(score_data.get("confidence", 0) or 0))
        rel = normalize_score(float(score_data.get("relevance", 0) or 0))
        fallback_overall = normalize_score(float(score_data.get("overall", 0) or 0))
        overall = compute_overall_score(comm, know, conf, rel, fallback_overall)
        rec_str = compute_recommendation(overall)

        # Only create if one doesn't already exist (Celery task may have beaten us)
        if not Scorecard.objects.filter(call_record=call_record).exists():
            scorecard = Scorecard.objects.create(
                application=call_record.application,
                call_record=call_record,
                tenant_id=call_record.tenant_id,
                owner_user_id=call_record.owner_user_id,
                communication_score=comm,
                knowledge_score=know,
                confidence_score=conf,
                relevance_score=rel,
                overall_score=overall,
                summary=payload.get("summary", ""),
                strengths=score_data.get("strengths", []),
                weaknesses=score_data.get("weaknesses", []),
                detailed_feedback=score_data.get("detailed_feedback", {}),
                recommendation=rec_str if rec_str in Scorecard.Recommendation.values else "MAYBE",
            )
            # on_scorecard_saved signal will set application status via thresholds
        else:
            scorecard = Scorecard.objects.filter(call_record=call_record).first()

    # 4. Create notification for application owner (in-app + email)
    application = call_record.application
    try:
        applicant = application.applicant
        overall = scorecard.overall_score if score_data else None
        # Try to resolve owner email for email notification
        from notifications.services import notify_with_email
        owner_email = _resolve_owner_email(application)
        if owner_email:
            notify_with_email(
                tenant_id=str(call_record.tenant_id),
                owner_user_id=str(call_record.owner_user_id),
                recipient_user_id=str(application.owner_user_id),
                recipient_email=owner_email,
                category=Notification.Category.CALL,
                title="AI Screening Call Completed",
                message=f"AI screening call completed for {applicant.first_name} {applicant.last_name}.",
                email_type="ai_screening_complete",
                extra_data={
                    "application_id": str(application.id),
                    "call_record_id": str(call_record.id),
                    "applicant_name": f"{applicant.first_name} {applicant.last_name}",
                    "job_title": application.job.title,
                    "score": str(overall) if overall else None,
                },
            )
        else:
            create_notification(
                tenant_id=str(call_record.tenant_id),
                owner_user_id=str(call_record.owner_user_id),
                recipient_user_id=str(application.owner_user_id),
                notification_type=Notification.NotificationType.IN_APP,
                category=Notification.Category.CALL,
                title="AI Screening Call Completed",
                message=f"AI screening call completed for {applicant.first_name} {applicant.last_name}.",
                data={"application_id": str(application.id), "call_record_id": str(call_record.id)},
            )
    except Exception as e:
        logger.error(f"Failed to create notification: {e}")

    # 5. Log activity
    try:
        from activities.services import log_activity
        from activities.models import Activity
        log_activity(
            tenant_id=str(call_record.tenant_id),
            actor_user_id=str(call_record.owner_user_id),
            actor_email="system",
            verb=Activity.Verb.CALL_COMPLETED,
            resource_type="CallRecord",
            resource_id=str(call_record.id),
            resource_label=f"Call for {application.applicant.first_name} {application.applicant.last_name}",
            after={"status": "COMPLETED", "overall_score": str(scorecard.overall_score) if score_data else None},
            metadata={"application_id": str(application.id)},
        )
    except Exception as e:
        logger.error(f"Failed to log activity: {e}")

    # 6. Update CallQueueItem if this call was part of a queue
    try:
        from call_queue.models import CallQueueItem, CallQueue
        from django.db.models import F
        from django.utils import timezone

        queue_item = CallQueueItem.objects.filter(
            call_record=call_record,
        ).select_related("queue").first()

        if not queue_item:
            # Also try to find by application in case call_record FK isn't set
            queue_item = CallQueueItem.objects.filter(
                application=application,
                status=CallQueueItem.Status.CALLING,
            ).select_related("queue").first()

        if queue_item:
            overall_score = scorecard.overall_score if score_data else None
            queue_item.status = CallQueueItem.Status.COMPLETED
            queue_item.score = overall_score
            queue_item.completed_at = timezone.now()
            queue_item.call_record = call_record
            queue_item.save(update_fields=["status", "score", "completed_at", "call_record_id", "updated_at"])

            # Update queue completed counter
            CallQueue.objects.filter(id=queue_item.queue_id).update(
                total_completed=F("total_completed") + 1
            )

            logger.info(
                f"CallQueueItem {queue_item.id} updated to COMPLETED, score={overall_score}"
            )

            # Log activity for queue item completion
            try:
                from activities.services import log_activity as _log
                _log(
                    tenant_id=str(call_record.tenant_id),
                    actor_user_id=str(call_record.owner_user_id),
                    actor_email="system",
                    verb=Activity.Verb.CALL_COMPLETED,
                    resource_type="CallQueueItem",
                    resource_id=str(queue_item.id),
                    resource_label=f"Queue call for {application.applicant.first_name} {application.applicant.last_name}",
                    after={"status": "COMPLETED", "score": str(overall_score) if overall_score else None},
                    metadata={"queue_id": str(queue_item.queue_id), "call_record_id": str(call_record.id)},
                )
            except Exception as e:
                logger.error(f"Failed to log queue item activity: {e}")

            # Trigger next item in the queue
            queue = queue_item.queue
            if queue.status == CallQueue.Status.RUNNING:
                from call_queue.tasks import process_call_queue
                process_call_queue.delay(str(queue.id), str(call_record.tenant_id))

    except Exception as e:
        logger.error(f"Failed to update CallQueueItem on call completion: {e}")

    return {"status": "processed", "call_record_id": str(call_record.id)}


def _resolve_owner_email(application) -> str:
    """Resolve owner email from application metadata or user cache."""
    metadata = getattr(application, "metadata", None) or {}
    if isinstance(metadata, dict) and metadata.get("owner_email"):
        return metadata["owner_email"]
    try:
        from django.core.cache import cache
        cached_email = cache.get(f"user_email:{application.owner_user_id}")
        if cached_email:
            return cached_email
    except Exception:
        pass
    return ""


def handle_call_status(payload: dict[str, Any]) -> dict:
    """Process a call-status webhook (real-time status updates)."""
    from calls.models import CallRecord

    call_id = (
        payload.get("call_id")
        or payload.get("provider_call_id")
        or payload.get("id", "")
    )
    status = payload.get("status", "")

    try:
        call_record = CallRecord.objects.get(provider_call_id=call_id)
    except CallRecord.DoesNotExist:
        logger.warning(
            "call-status webhook: CallRecord not found for call_id=%r status=%r "
            "(payload keys=%s)",
            call_id, status, sorted(payload.keys()),
        )
        return {"error": "CallRecord not found"}

    status_map = {
        "initiated": CallRecord.Status.INITIATED,
        "ringing": CallRecord.Status.RINGING,
        "in_progress": CallRecord.Status.IN_PROGRESS,
        "completed": CallRecord.Status.COMPLETED,
        "failed": CallRecord.Status.FAILED,
        "no_answer": CallRecord.Status.NO_ANSWER,
        "busy": CallRecord.Status.BUSY,
    }
    new_status = status_map.get(status.lower())
    if new_status:
        call_record.status = new_status
        call_record.save(update_fields=["status", "updated_at"])

    return {"status": "updated", "call_record_id": str(call_record.id)}
