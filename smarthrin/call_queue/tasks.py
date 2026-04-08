"""Celery tasks for call queue processing."""
import logging
from typing import Optional

from celery import shared_task
from celery.utils.log import get_task_logger

logger = get_task_logger(__name__)


def _is_within_call_window(config: dict) -> bool:
    """Check if current time is within the configured call window."""
    from datetime import datetime
    try:
        from zoneinfo import ZoneInfo
    except ImportError:
        from backports.zoneinfo import ZoneInfo  # Python 3.8 fallback

    tz_name = config.get("timezone", "Asia/Kolkata")
    window_start = config.get("call_window_start", "09:00")
    window_end = config.get("call_window_end", "18:00")

    try:
        tz = ZoneInfo(tz_name)
        now = datetime.now(tz)
        current_time = now.strftime("%H:%M")
        return window_start <= current_time <= window_end
    except Exception as exc:
        logger.warning(f"Failed to check call window with tz={tz_name}: {exc}")
        return True  # Default to allowing calls if timezone check fails


@shared_task(bind=True, max_retries=3, default_retry_delay=30)
def process_call_queue(self, queue_id: str, tenant_id: str) -> Optional[str]:
    """
    Main queue processor — checks queue state and dispatches next pending call.
    Reschedules itself after delay_between_calls_seconds.
    Marks queue COMPLETED when no more pending/calling items.
    """
    from django.utils import timezone
    from .models import CallQueue, CallQueueItem

    try:
        queue = CallQueue.objects.get(id=queue_id, tenant_id=tenant_id)
    except CallQueue.DoesNotExist:
        logger.error(f"CallQueue {queue_id} not found")
        return None

    if queue.status != CallQueue.Status.RUNNING:
        logger.info(f"Queue {queue_id} is {queue.status}, not processing")
        return None

    config = queue.get_config()

    # Check call window
    if not _is_within_call_window(config):
        logger.info(f"Queue {queue_id}: outside call window, rescheduling in 60s")
        process_call_queue.apply_async(
            args=[queue_id, tenant_id],
            countdown=60,
        )
        return None

    # Count currently active calls for this queue
    active_count = CallQueueItem.objects.filter(
        queue_id=queue_id,
        status=CallQueueItem.Status.CALLING,
    ).count()

    max_concurrent = int(config.get("max_concurrent_calls", 1))

    if active_count < max_concurrent:
        # Pick next PENDING item by position
        next_item = (
            CallQueueItem.objects.filter(
                queue_id=queue_id,
                status=CallQueueItem.Status.PENDING,
            )
            .order_by("position")
            .first()
        )

        if next_item:
            dispatch_queue_item.delay(str(next_item.id), tenant_id)

    # Check if queue is fully completed
    has_pending = CallQueueItem.objects.filter(
        queue_id=queue_id,
        status__in=[CallQueueItem.Status.PENDING, CallQueueItem.Status.CALLING],
    ).exists()

    if not has_pending:
        # All items have been processed
        completed_count = CallQueueItem.objects.filter(
            queue_id=queue_id, status=CallQueueItem.Status.COMPLETED
        ).count()
        failed_count = CallQueueItem.objects.filter(
            queue_id=queue_id, status=CallQueueItem.Status.FAILED
        ).count()

        queue.status = CallQueue.Status.COMPLETED
        queue.completed_at = timezone.now()
        queue.total_completed = completed_count
        queue.total_failed = failed_count
        queue.save(update_fields=["status", "completed_at", "total_completed", "total_failed", "updated_at"])

        logger.info(f"Queue {queue_id} COMPLETED: {completed_count} completed, {failed_count} failed")

        # Log activity and send notification
        try:
            from activities.services import log_activity
            log_activity(
                tenant_id=str(tenant_id),
                actor_user_id=str(queue.owner_user_id),
                actor_email="system",
                verb="completed",
                resource_type="CallQueue",
                resource_id=str(queue.id),
                resource_label=queue.name,
                after={"status": "COMPLETED", "total_completed": completed_count, "total_failed": failed_count},
            )
        except Exception as e:
            logger.error(f"Failed to log queue completion activity: {e}")

        try:
            from notifications.services import create_notification
            from notifications.models import Notification

            # Count shortlisted/rejected based on score thresholds
            shortlist_threshold = float(config.get("auto_shortlist_threshold", 7.0))
            reject_threshold = float(config.get("auto_reject_threshold", 4.0))
            shortlisted = CallQueueItem.objects.filter(
                queue_id=queue_id,
                status=CallQueueItem.Status.COMPLETED,
                score__gte=shortlist_threshold,
            ).count()
            rejected = CallQueueItem.objects.filter(
                queue_id=queue_id,
                status=CallQueueItem.Status.COMPLETED,
                score__lt=reject_threshold,
            ).count()

            create_notification(
                tenant_id=str(tenant_id),
                owner_user_id=str(queue.owner_user_id),
                recipient_user_id=str(queue.owner_user_id),
                notification_type=Notification.NotificationType.IN_APP,
                category=Notification.Category.CALL,
                title=f"Call Queue Completed: {queue.name}",
                message=(
                    f"Queue '{queue.name}' has finished processing. "
                    f"{queue.total_queued} called, {shortlisted} shortlisted, {rejected} rejected."
                ),
                data={"queue_id": str(queue.id), "total_completed": completed_count, "total_failed": failed_count},
            )
        except Exception as e:
            logger.error(f"Failed to send queue completion notification: {e}")

        return str(queue.id)

    # Reschedule to continue processing after delay
    delay_seconds = int(config.get("delay_between_calls_seconds", 30))
    process_call_queue.apply_async(
        args=[queue_id, tenant_id],
        countdown=delay_seconds,
    )
    return None


@shared_task(bind=True, max_retries=3, default_retry_delay=15)
def dispatch_queue_item(self, item_id: str, tenant_id: str) -> Optional[str]:
    """
    Dispatch a single AI screening call for a CallQueueItem.
    Handles retry logic based on queue config max_retries.
    """
    from django.db import transaction
    from django.utils import timezone
    from integrations.exceptions import VoiceAIProviderError, VoiceAICredentialsMissing, VoiceAIError
    from integrations.voice_ai import VoiceAIClient
    from calls.models import CallRecord
    from .models import CallQueueItem

    # Use select_for_update to prevent concurrent dispatch of the same item
    with transaction.atomic():
        try:
            item = (
                CallQueueItem.objects
                .select_for_update(skip_locked=True)
                .select_related("queue", "application__job", "application__applicant")
                .get(id=item_id, tenant_id=tenant_id)
            )
        except CallQueueItem.DoesNotExist:
            logger.error(f"CallQueueItem {item_id} not found (or locked by another task)")
            return None

        if item.status not in [CallQueueItem.Status.PENDING]:
            logger.info(f"QueueItem {item_id} is {item.status}, skipping dispatch")
            return None

        # Check for existing active call records for this application (not just linked items).
        # This catches orphaned CallRecords that weren't linked back to the queue item.
        # Records older than CALL_STALE_THRESHOLD_MINUTES are treated as abandoned
        # (missed provider webhook) and auto-failed so this item can proceed.
        from datetime import timedelta
        from django.conf import settings as django_settings
        from django.utils import timezone

        active_statuses = [
            CallRecord.Status.QUEUED,
            CallRecord.Status.INITIATED,
            CallRecord.Status.RINGING,
            CallRecord.Status.IN_PROGRESS,
        ]
        stale_threshold_minutes = getattr(django_settings, "CALL_STALE_THRESHOLD_MINUTES", 15)
        stale_cutoff = timezone.now() - timedelta(minutes=stale_threshold_minutes)

        stale_ids = list(
            CallRecord.objects.filter(
                application=item.application,
                status__in=active_statuses,
                created_at__lt=stale_cutoff,
            ).values_list("id", flat=True)
        )
        if stale_ids:
            CallRecord.objects.filter(id__in=stale_ids).update(
                status=CallRecord.Status.FAILED,
                error_message=(
                    f"Auto-failed: no terminal status received within "
                    f"{stale_threshold_minutes} minutes (likely missed provider webhook)."
                ),
                updated_at=timezone.now(),
            )
            logger.warning(
                f"Auto-failed {len(stale_ids)} stale call record(s) for application "
                f"{item.application_id}: {stale_ids}"
            )

        if CallRecord.objects.filter(
            application=item.application,
            status__in=active_statuses,
            created_at__gte=stale_cutoff,
        ).exists():
            logger.info(f"QueueItem {item_id} already has an active call record for its application, skipping dispatch")
            return None

        queue = item.queue
        config = queue.get_config()
        application = item.application
        job = application.job
        applicant = application.applicant

        # Validate phone
        if not applicant.phone:
            item.status = CallQueueItem.Status.FAILED
            item.error_message = f"Applicant {applicant.first_name} {applicant.last_name} has no phone number"
            item.save(update_fields=["status", "error_message", "updated_at"])
            _update_queue_failed_count(queue)
            return None

        # Normalize phone — auto-prefixes DEFAULT_PHONE_COUNTRY_CODE if missing
        from calls.services import _normalize_phone
        try:
            phone = _normalize_phone(applicant.phone)
        except ValueError as exc:
            item.status = CallQueueItem.Status.FAILED
            item.error_message = str(exc)
            item.save(update_fields=["status", "error_message", "updated_at"])
            _update_queue_failed_count(queue)
            return None

        # Use queue's voice_agent_id (overrides job's)
        agent_id = queue.voice_agent_id or job.voice_agent_id
        if not agent_id:
            item.status = CallQueueItem.Status.FAILED
            item.error_message = "No voice_agent_id configured on queue or job"
            item.save(update_fields=["status", "error_message", "updated_at"])
            _update_queue_failed_count(queue)
            return None

        # Mark item as CALLING (inside atomic block to prevent race conditions)
        item.status = CallQueueItem.Status.CALLING
        item.attempts += 1
        item.last_attempt_at = timezone.now()
        item.save(update_fields=["status", "attempts", "last_attempt_at", "updated_at"])

        # Create CallRecord INSIDE the atomic block so it's rolled back if the
        # transaction fails, preventing orphaned records.
        call_record = CallRecord.objects.create(
            application=application,
            tenant_id=tenant_id,
            owner_user_id=queue.owner_user_id,
            voice_agent_id=str(agent_id),
            phone=phone,
            status=CallRecord.Status.QUEUED,
            provider=CallRecord.Provider.OMNIDIM,
        )

        # Link CallRecord to queue item immediately (inside the same transaction)
        item.call_record = call_record
        item.save(update_fields=["call_record_id", "updated_at"])

    # Update queue total_called counter
    from .models import CallQueue
    CallQueue.objects.filter(id=queue.id).update(total_called=models_F_increment("total_called"))

    # Build call context
    call_context = {
        "candidateName": f"{applicant.first_name} {applicant.last_name}",
        "jobTitle": job.title,
        "jobDescription": (job.description or "")[:500],
        "requirements": (job.requirements or "")[:500],
        "candidateSkills": ", ".join(applicant.skills or []),
        "candidateExperience": (
            f"{applicant.experience_years} years" if applicant.experience_years else "Not specified"
        ),
        "queueName": queue.name,
    }
    if job.voice_agent_config:
        call_context.update(job.voice_agent_config.get("call_context_overrides", {}))

    metadata = {
        "applicationId": str(application.id),
        "jobId": str(job.id),
        "applicantId": str(applicant.id),
        "tenantId": str(tenant_id),
        "queueId": str(queue.id),
        "queueItemId": str(item.id),
        "source": "smarthrin_queue",
    }

    try:
        voice_client = VoiceAIClient()
        response = voice_client.start_call(
            tenant_id=str(tenant_id),
            agent_id=str(agent_id),
            phone=phone,
            call_context=call_context,
            metadata=metadata,
        )
        call_record.provider_call_id = response.get("id", "")
        provider_str = response.get("provider", "OMNIDIM")
        call_record.provider = provider_str if provider_str in ["OMNIDIM", "BOLNA"] else "OMNIDIM"
        call_record.status = CallRecord.Status.INITIATED
        call_record.save(update_fields=["provider_call_id", "provider", "status", "updated_at"])

        logger.info(
            f"Queue item {item_id} dispatched: call_record={call_record.id}, "
            f"provider_call_id={call_record.provider_call_id}"
        )

        # Log activity
        try:
            from activities.services import log_activity
            log_activity(
                tenant_id=str(tenant_id),
                actor_user_id=str(queue.owner_user_id),
                actor_email="system",
                verb="triggered_call",
                resource_type="CallQueueItem",
                resource_id=str(item.id),
                resource_label=f"Queue call for {applicant.first_name} {applicant.last_name}",
                after={"status": "CALLING", "call_record_id": str(call_record.id)},
                metadata={"queue_id": str(queue.id), "application_id": str(application.id)},
            )
        except Exception as e:
            logger.error(f"Failed to log dispatch activity: {e}")

        # Schedule a status check in 30 seconds
        check_queue_call_status.apply_async(
            args=[str(item.id), tenant_id],
            countdown=30,
        )

        return str(call_record.id)

    except VoiceAIProviderError as exc:
        logger.warning(f"Provider error for queue item {item_id}: {exc}")
        # Refresh item from DB to avoid overwriting concurrent changes
        item.refresh_from_db()
        max_retries = int(config.get("max_retries", 2))
        call_record.status = CallRecord.Status.FAILED
        call_record.error_message = str(exc)
        call_record.save(update_fields=["status", "error_message", "updated_at"])
        if item.attempts < max_retries:
            # Reset to PENDING; let process_call_queue pick it up naturally
            item.status = CallQueueItem.Status.PENDING
            item.error_message = str(exc)
            item.save(update_fields=["status", "error_message", "updated_at"])
        else:
            item.status = CallQueueItem.Status.FAILED
            item.error_message = str(exc)
            item.save(update_fields=["status", "error_message", "updated_at"])
            _update_queue_failed_count(queue)
            _notify_item_failure_if_exhausted(item, queue, tenant_id)
        # Trigger queue processing to pick up the retried item or next item
        process_call_queue.delay(str(queue.id), tenant_id)
        return None

    except VoiceAICredentialsMissing as exc:
        logger.error(f"Credentials missing for queue item {item_id}: {exc}")
        item.refresh_from_db()
        item.status = CallQueueItem.Status.FAILED
        item.error_message = str(exc)
        item.save(update_fields=["status", "error_message", "updated_at"])
        call_record.status = CallRecord.Status.FAILED
        call_record.error_message = str(exc)
        call_record.save(update_fields=["status", "error_message", "updated_at"])
        _update_queue_failed_count(queue)
        _notify_item_failure_if_exhausted(item, queue, tenant_id)
        raise  # Do not retry

    except VoiceAIError as exc:
        logger.error(f"VoiceAI error for queue item {item_id}: {exc}")
        item.refresh_from_db()
        max_retries = int(config.get("max_retries", 2))
        call_record.status = CallRecord.Status.FAILED
        call_record.error_message = str(exc)
        call_record.save(update_fields=["status", "error_message", "updated_at"])
        if item.attempts < max_retries:
            item.status = CallQueueItem.Status.PENDING
            item.error_message = str(exc)
            item.save(update_fields=["status", "error_message", "updated_at"])
        else:
            item.status = CallQueueItem.Status.FAILED
            item.error_message = str(exc)
            item.save(update_fields=["status", "error_message", "updated_at"])
            _update_queue_failed_count(queue)
            _notify_item_failure_if_exhausted(item, queue, tenant_id)
        process_call_queue.delay(str(queue.id), tenant_id)
        return None

    except Exception as exc:
        logger.exception(f"Unexpected error dispatching queue item {item_id}")
        item.refresh_from_db()
        item.status = CallQueueItem.Status.FAILED
        item.error_message = str(exc)
        item.save(update_fields=["status", "error_message", "updated_at"])
        call_record.status = CallRecord.Status.FAILED
        call_record.error_message = str(exc)
        call_record.save(update_fields=["status", "error_message", "updated_at"])
        _update_queue_failed_count(queue)
        _notify_item_failure_if_exhausted(item, queue, tenant_id)
        raise


def models_F_increment(field_name: str):
    """Return an F expression to increment a field by 1."""
    from django.db.models import F
    return F(field_name) + 1


def _update_queue_failed_count(queue) -> None:
    """Increment queue total_failed counter."""
    from django.db.models import F
    from .models import CallQueue
    CallQueue.objects.filter(id=queue.id).update(total_failed=F("total_failed") + 1)


def _notify_item_failure_if_exhausted(item, queue, tenant_id: str) -> None:
    """Send notification when a queue item fails after exhausting retries."""
    try:
        from notifications.services import create_notification
        from notifications.models import Notification
        applicant = item.application.applicant
        create_notification(
            tenant_id=str(tenant_id),
            owner_user_id=str(queue.owner_user_id),
            recipient_user_id=str(queue.owner_user_id),
            notification_type=Notification.NotificationType.IN_APP,
            category=Notification.Category.CALL,
            title="Queue Call Failed",
            message=(
                f"Call for {applicant.first_name} {applicant.last_name} in queue "
                f"'{queue.name}' failed after {item.attempts} attempts: {item.error_message}"
            ),
            data={"queue_id": str(queue.id), "item_id": str(item.id)},
        )
    except Exception as e:
        logger.error(f"Failed to send item failure notification: {e}")


@shared_task(bind=True, max_retries=5, default_retry_delay=30)
def check_queue_call_status(self, item_id: str, tenant_id: str) -> None:
    """
    Periodically check the status of a queue item's call.
    Marks item COMPLETED/FAILED based on call record status.
    Retries every 30s if call still in progress.
    """
    from django.utils import timezone
    from calls.models import CallRecord
    from .models import CallQueueItem

    try:
        item = CallQueueItem.objects.select_related("queue", "call_record").get(
            id=item_id, tenant_id=tenant_id
        )
    except CallQueueItem.DoesNotExist:
        logger.error(f"CallQueueItem {item_id} not found for status check")
        return

    if item.status != CallQueueItem.Status.CALLING:
        logger.info(f"QueueItem {item_id} is now {item.status}, no status check needed")
        return

    if not item.call_record:
        logger.warning(f"QueueItem {item_id} has no call_record, cannot check status")
        return

    call_record = item.call_record

    # Fetch latest status from Voice AI
    try:
        from calls.services import AIScreeningService
        service = AIScreeningService()
        call_record = service.get_call_status(str(call_record.id), tenant_id)
    except Exception as exc:
        logger.warning(f"Could not fetch call status for queue item {item_id}: {exc}")

    terminal_statuses = [
        CallRecord.Status.COMPLETED,
        CallRecord.Status.FAILED,
        CallRecord.Status.NO_ANSWER,
        CallRecord.Status.BUSY,
    ]

    if call_record.status == CallRecord.Status.COMPLETED:
        # Get score from scorecard if available
        scorecard = call_record.scorecard.first()
        score = scorecard.overall_score if scorecard else None

        item.status = CallQueueItem.Status.COMPLETED
        item.score = score
        item.completed_at = timezone.now()
        item.save(update_fields=["status", "score", "completed_at", "updated_at"])

        from .models import CallQueue
        from django.db.models import F
        CallQueue.objects.filter(id=item.queue_id).update(total_completed=F("total_completed") + 1)

        logger.info(f"QueueItem {item_id} COMPLETED with score={score}")

        # Log activity
        try:
            from activities.services import log_activity
            applicant = item.application.applicant
            log_activity(
                tenant_id=str(tenant_id),
                actor_user_id=str(item.queue.owner_user_id),
                actor_email="system",
                verb="call_completed",
                resource_type="CallQueueItem",
                resource_id=str(item.id),
                resource_label=f"Queue call for {applicant.first_name} {applicant.last_name}",
                after={"status": "COMPLETED", "score": str(score) if score else None},
                metadata={"queue_id": str(item.queue_id), "call_record_id": str(call_record.id)},
            )
        except Exception as e:
            logger.error(f"Failed to log call completion activity: {e}")

        # Trigger next item processing
        queue = item.queue
        if queue.status == CallQueue.Status.RUNNING:
            process_call_queue.delay(str(queue.id), tenant_id)

    elif call_record.status in [CallRecord.Status.FAILED, CallRecord.Status.NO_ANSWER, CallRecord.Status.BUSY]:
        config = item.queue.get_config()
        max_retries = int(config.get("max_retries", 2))

        if item.attempts < max_retries:
            item.status = CallQueueItem.Status.PENDING
            item.error_message = f"Call {call_record.status}, will retry"
            item.save(update_fields=["status", "error_message", "updated_at"])
        else:
            item.status = CallQueueItem.Status.FAILED
            item.error_message = f"Call {call_record.status} after {item.attempts} attempts"
            item.save(update_fields=["status", "error_message", "updated_at"])
            _update_queue_failed_count(item.queue)
            _notify_item_failure_if_exhausted(item, item.queue, tenant_id)

        # Trigger next item processing
        process_call_queue.delay(str(item.queue_id), tenant_id)

    elif call_record.status not in terminal_statuses:
        # Still in progress — reschedule check in 30s
        check_queue_call_status.apply_async(
            args=[item_id, tenant_id],
            countdown=30,
        )


@shared_task
def tick_running_queues() -> None:
    """
    Periodic task (every 60s) — ensure all RUNNING queues continue processing.
    Handles worker restarts by re-triggering process_call_queue for stalled queues.
    """
    from .models import CallQueue

    running_queues = CallQueue.objects.filter(status=CallQueue.Status.RUNNING).values("id", "tenant_id")
    for q in running_queues:
        process_call_queue.delay(str(q["id"]), str(q["tenant_id"]))
        logger.debug(f"Ticked queue {q['id']} for tenant {q['tenant_id']}")


# Maximum time a queue item can stay in CALLING status before it's considered stuck
STUCK_CALLING_TIMEOUT_MINUTES = 10


@shared_task
def cleanup_stuck_queue_items() -> None:
    """
    Periodic task (every 5 minutes) — find CallQueueItems stuck in CALLING
    status for longer than STUCK_CALLING_TIMEOUT_MINUTES and either retry
    them or mark as FAILED.
    """
    from datetime import timedelta
    from django.db import transaction
    from django.db.models import Q
    from django.utils import timezone
    from calls.models import CallRecord
    from .models import CallQueue, CallQueueItem

    cutoff = timezone.now() - timedelta(minutes=STUCK_CALLING_TIMEOUT_MINUTES)

    # Include items with NULL last_attempt_at (should never happen but prevents permanent stuckness)
    stuck_items = (
        CallQueueItem.objects
        .select_for_update(skip_locked=True)
        .select_related("queue", "call_record")
        .filter(
            status=CallQueueItem.Status.CALLING,
        )
        .filter(
            Q(last_attempt_at__lt=cutoff) | Q(last_attempt_at__isnull=True)
        )
    )

    cleaned = 0
    retried = 0
    queues_to_retrigger = set()

    # Process each stuck item inside a transaction with row locking
    with transaction.atomic():
        for item in stuck_items:
            config = item.queue.get_config()
            max_retries = int(config.get("max_retries", 2))

            # Mark linked call record as FAILED if still active (use enum, not strings)
            active_call_statuses = [
                CallRecord.Status.QUEUED,
                CallRecord.Status.INITIATED,
                CallRecord.Status.RINGING,
                CallRecord.Status.IN_PROGRESS,
            ]
            if item.call_record and item.call_record.status in active_call_statuses:
                item.call_record.status = CallRecord.Status.FAILED
                item.call_record.error_message = "Call timed out (stuck in CALLING)"
                item.call_record.save(update_fields=["status", "error_message", "updated_at"])

            if item.attempts < max_retries:
                # Reset to PENDING for retry
                item.status = CallQueueItem.Status.PENDING
                item.error_message = f"Reset from stuck CALLING state after {STUCK_CALLING_TIMEOUT_MINUTES}m (attempt {item.attempts}/{max_retries})"
                item.save(update_fields=["status", "error_message", "updated_at"])
                retried += 1
                logger.info(f"Stuck QueueItem {item.id} reset to PENDING for retry (attempt {item.attempts}/{max_retries})")
            else:
                # Exhausted retries — mark as FAILED
                item.status = CallQueueItem.Status.FAILED
                item.error_message = f"Stuck in CALLING for >{STUCK_CALLING_TIMEOUT_MINUTES}m after {item.attempts} attempts"
                item.save(update_fields=["status", "error_message", "updated_at"])
                _update_queue_failed_count(item.queue)
                _notify_item_failure_if_exhausted(item, item.queue, str(item.tenant_id))
                cleaned += 1
                logger.info(f"Stuck QueueItem {item.id} marked FAILED (exhausted {item.attempts} attempts)")

            # Collect unique queues to re-trigger (deduplicated)
            if item.queue.status == CallQueue.Status.RUNNING:
                queues_to_retrigger.add((str(item.queue_id), str(item.tenant_id)))

    # Re-trigger queue processing once per queue (outside the transaction)
    for queue_id, t_id in queues_to_retrigger:
        process_call_queue.delay(queue_id, t_id)

    if cleaned or retried:
        logger.info(f"Stuck queue item cleanup: {retried} retried, {cleaned} failed")
