"""Celery tasks for the calls app."""
from celery import shared_task
from celery.utils.log import get_task_logger

logger = get_task_logger(__name__)


@shared_task(bind=True, max_retries=3, default_retry_delay=60)
def dispatch_ai_call(self, application_id: str, tenant_id: str, owner_user_id: str) -> dict:
    """Dispatch an AI screening call. Retries up to 3 times with exponential backoff."""
    try:
        from .services import trigger_ai_screening_call

        call_record = trigger_ai_screening_call(application_id, tenant_id, owner_user_id)
        return {"call_record_id": str(call_record.id), "status": call_record.status}
    except Exception as exc:
        logger.error(f"dispatch_ai_call failed for application {application_id}: {exc}")
        countdown = 60 * (2 ** self.request.retries)
        raise self.retry(exc=exc, countdown=countdown)
