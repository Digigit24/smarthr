"""Process incoming Voice AI webhook payloads."""
import logging
from typing import Any

from django.utils.dateparse import parse_datetime

logger = logging.getLogger(__name__)


# Per voiceb contract, incoming status values are lowercase snake_case and
# must be one of: ringing, in_progress, completed, failed, no_answer, busy.
# `initiated` is set only by SmartHR at dispatch time; keep it in the map so
# an echo from voiceb wouldn't corrupt state.
def _status_map():
    from calls.models import CallRecord
    return {
        "initiated": CallRecord.Status.INITIATED,
        "ringing": CallRecord.Status.RINGING,
        "in_progress": CallRecord.Status.IN_PROGRESS,
        "completed": CallRecord.Status.COMPLETED,
        "failed": CallRecord.Status.FAILED,
        "no_answer": CallRecord.Status.NO_ANSWER,
        "busy": CallRecord.Status.BUSY,
    }


def _map_incoming_status(raw: Any, *, endpoint: str, call_id: str):
    """
    Resolve an incoming status string to a CallRecord.Status.

    Unknown values (or a missing status) are logged and treated as FAILED per
    voiceb's safe-fallback contract — we'd rather false-fail than auto-
    shortlist a call we don't know completed successfully.
    """
    from calls.models import CallRecord

    normalized = (raw or "").strip().lower() if isinstance(raw, str) else ""
    mapped = _status_map().get(normalized)
    if mapped is not None:
        return mapped

    logger.warning(
        "%s webhook: unknown status=%r for call_id=%r — falling back to FAILED",
        endpoint, raw, call_id,
    )
    return CallRecord.Status.FAILED


def _apply_common_fields(call_record, payload: dict[str, Any]) -> None:
    """
    Apply payload fields that can appear on any webhook (status, duration,
    started_at, ended_at, error_message, transcript, recording_url, summary).
    Does NOT save — caller is responsible for call_record.save().
    """
    # Duration: respect what voiceb sends, including an explicit 0 for
    # no_answer / busy (means the candidate never talked — must NOT be
    # overwritten by a backfill from the ringing window).
    duration_in_payload = payload.get("duration")
    if duration_in_payload is not None:
        call_record.duration = duration_in_payload

    # Timestamps (ISO-8601). Only overwrite started_at if not already set;
    # ended_at is always overwritten with the latest terminal value.
    started_at_raw = payload.get("started_at")
    if started_at_raw:
        parsed = parse_datetime(started_at_raw)
        if parsed and not call_record.started_at:
            call_record.started_at = parsed

    ended_at_raw = payload.get("ended_at")
    if ended_at_raw:
        parsed = parse_datetime(ended_at_raw)
        if parsed:
            call_record.ended_at = parsed

    # Backfill duration ONLY when:
    #   - voiceb didn't send any duration field (None, not 0)
    #   - status is COMPLETED — for no_answer/busy/failed, the ringing window
    #     between started_at and ended_at is NOT talk time and must stay 0
    #   - we have both timestamps to subtract
    from calls.models import CallRecord
    if (
        duration_in_payload is None
        and call_record.status == CallRecord.Status.COMPLETED
        and call_record.started_at
        and call_record.ended_at
    ):
        delta = (call_record.ended_at - call_record.started_at).total_seconds()
        if delta > 0:
            call_record.duration = int(delta)

    # For non-completed terminals (no_answer / busy / failed), if voiceb
    # omitted duration entirely, default to 0 so the UI shows "0s" instead
    # of blank. The candidate didn't talk — there is no talk time.
    non_completed_terminals = (
        CallRecord.Status.NO_ANSWER,
        CallRecord.Status.BUSY,
        CallRecord.Status.FAILED,
    )
    if (
        duration_in_payload is None
        and call_record.duration is None
        and call_record.status in non_completed_terminals
    ):
        call_record.duration = 0

    # Error message for non-completed terminals
    error_message = payload.get("error_message")
    if error_message:
        call_record.error_message = error_message

    # Content fields (completed payloads carry these)
    transcript = payload.get("transcript")
    if transcript:
        call_record.transcript = transcript

    recording_url = payload.get("recording_url")
    if recording_url:
        call_record.recording_url = recording_url

    summary = payload.get("summary")
    if summary:
        call_record.summary = summary


def handle_call_completed(payload: dict[str, Any]) -> dict:
    """
    Process a terminal-status webhook from Voice AI Orchestrator.

    Handles every terminal status — completed / failed / no_answer / busy —
    not just completed. Scorecard/notification/queue side effects only fire
    on COMPLETED; the other terminal statuses just update fields and rely on
    the CallRecord post_save signal for downstream notification.

    Expected payload keys: call_id (required), status, duration, started_at,
    ended_at, transcript, recording_url, summary, score, error_message.
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

    if not provider_call_id:
        logger.warning(
            "call-completed webhook: missing call_id in payload (payload keys=%s, payload=%r)",
            sorted(payload.keys()), payload,
        )
        return {"error": "CallRecord not found"}

    # Use filter().first() rather than get() so we never crash with
    # MultipleObjectsReturned — empty-string matches can hit unrelated rows.
    call_record = CallRecord.objects.filter(provider_call_id=provider_call_id).first()
    if call_record is None:
        logger.warning(
            "call-completed webhook: CallRecord not found for provider_call_id=%r "
            "(payload keys=%s)",
            provider_call_id, sorted(payload.keys()),
        )
        return {"error": "CallRecord not found"}

    # Resolve final status from payload. Unknown / missing → FAILED.
    new_status = _map_incoming_status(
        payload.get("status"),
        endpoint="call-completed",
        call_id=provider_call_id,
    )
    call_record.status = new_status

    _apply_common_fields(call_record, payload)
    call_record.raw_response = payload
    call_record.save()

    # Downstream side effects (scorecard / notification / activity / queue
    # update) only make sense on a successful COMPLETED call. For
    # FAILED / NO_ANSWER / BUSY the CallRecord post_save signal fires the
    # appropriate failure notification; we're done here.
    if new_status != CallRecord.Status.COMPLETED:
        return {
            "status": "processed",
            "call_record_id": str(call_record.id),
            "final_status": new_status,
        }

    # 2. Create / update Scorecard from voiceb's score block.
    # Use update_or_create so a follow-up enrichment webhook for the same call
    # (e.g. voiceb's two-stage forwarding) refreshes the row instead of being
    # silently dropped.
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

        # Prefer voiceb's explicit recommendation (the AI's own judgment) when
        # present; fall back to a threshold-derived label if missing.
        detailed_feedback = score_data.get("detailed_feedback", {}) or {}
        provided_rec = (detailed_feedback.get("recommendation") or "").upper().replace(" ", "_")
        if provided_rec in Scorecard.Recommendation.values:
            recommendation = provided_rec
        else:
            computed_rec = compute_recommendation(overall)
            recommendation = computed_rec if computed_rec in Scorecard.Recommendation.values else "MAYBE"

        # detailed_feedback may carry a more meaningful evaluation summary;
        # fall back to the call-level summary if that's all we have.
        scorecard_summary = (
            detailed_feedback.get("summary")
            or payload.get("summary")
            or ""
        )

        # Race-safe upsert. Two voiceb webhooks for the same call (e.g. their
        # two-stage forwarding) can arrive in parallel; without this, both
        # transactions would pass the existence check and INSERT, producing
        # duplicate Scorecards. Wrap in atomic + catch IntegrityError so the
        # losing transaction falls through to an UPDATE on the row the winner
        # just created. The DB-level UniqueConstraint on Scorecard.call_record
        # is what makes this race-safe.
        from django.db import IntegrityError, transaction

        scorecard_defaults = {
            "application": call_record.application,
            "tenant_id": call_record.tenant_id,
            "owner_user_id": call_record.owner_user_id,
            "communication_score": comm,
            "knowledge_score": know,
            "confidence_score": conf,
            "relevance_score": rel,
            "overall_score": overall,
            "summary": scorecard_summary,
            "strengths": score_data.get("strengths", []),
            "weaknesses": score_data.get("weaknesses", []),
            "detailed_feedback": detailed_feedback,
            "recommendation": recommendation,
        }
        try:
            with transaction.atomic():
                scorecard, _created = Scorecard.objects.update_or_create(
                    call_record=call_record,
                    defaults=scorecard_defaults,
                )
        except IntegrityError:
            scorecard = Scorecard.objects.get(call_record=call_record)
            for field, value in scorecard_defaults.items():
                setattr(scorecard, field, value)
            scorecard.save()
        # on_scorecard_saved signal will set application status via thresholds
        # (only fires on initial create; updates re-use the existing routing).

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
    """
    Process a real-time call-status webhook (ringing / in_progress / etc.).

    Persists status changes plus any of the shared fields (started_at,
    ended_at, duration, error_message, transcript, recording_url, summary)
    that voiceb includes on the event. This matters because voiceb's
    webhookWorker routes some ERROR events here rather than to
    /call-completed/ — we still want the timestamps and failure reason saved.
    """
    from calls.models import CallRecord

    call_id = (
        payload.get("call_id")
        or payload.get("provider_call_id")
        or payload.get("id", "")
    )
    status = payload.get("status", "")

    if not call_id:
        logger.warning(
            "call-status webhook: missing call_id in payload status=%r "
            "(payload keys=%s, payload=%r)",
            status, sorted(payload.keys()), payload,
        )
        return {"error": "CallRecord not found"}

    call_record = CallRecord.objects.filter(provider_call_id=call_id).first()
    if call_record is None:
        logger.warning(
            "call-status webhook: CallRecord not found for call_id=%r status=%r "
            "(payload keys=%s)",
            call_id, status, sorted(payload.keys()),
        )
        return {"error": "CallRecord not found"}

    call_record.status = _map_incoming_status(
        status, endpoint="call-status", call_id=call_id,
    )

    _apply_common_fields(call_record, payload)
    call_record.save()

    return {"status": "updated", "call_record_id": str(call_record.id)}
