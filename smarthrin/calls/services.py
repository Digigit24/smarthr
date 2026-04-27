"""AI Screening Call service — bridges SmartHR-In models with Voice AI Orchestrator."""
import logging
from datetime import timedelta
from typing import Any, Optional

from django.conf import settings
from django.db import transaction
from django.utils import timezone

from common.phone import normalize_phone as _normalize_phone
from integrations.exceptions import VoiceAIError
from integrations.voice_ai import VoiceAIClient

logger = logging.getLogger(__name__)


def get_call_stale_threshold_minutes() -> int:
    """Returns the configured stale-call cutoff in minutes."""
    return getattr(settings, "CALL_STALE_THRESHOLD_MINUTES", 5)


def compute_call_stale_at(call_record) -> Optional[Any]:
    """
    Returns the datetime at which an in-flight CallRecord becomes stale.
    Returns None for terminal-status calls (the field is meaningless for them).
    """
    from .models import CallRecord

    in_flight_statuses = {
        CallRecord.Status.QUEUED,
        CallRecord.Status.INITIATED,
        CallRecord.Status.RINGING,
        CallRecord.Status.IN_PROGRESS,
    }
    if call_record.status not in in_flight_statuses:
        return None
    return call_record.created_at + timedelta(minutes=get_call_stale_threshold_minutes())


def compute_seconds_until_stale(call_record) -> Optional[int]:
    """
    Returns whole seconds until the call is auto-failed.
    Negative if already past the threshold (i.e. immediately reapable).
    Returns None for terminal-status calls.
    """
    stale_at = compute_call_stale_at(call_record)
    if stale_at is None:
        return None
    return int((stale_at - timezone.now()).total_seconds())


def reap_stale_calls(
    tenant_id: Optional[str] = None,
    application_id: Optional[str] = None,
) -> list:
    """
    Mark in-flight CallRecords older than CALL_STALE_THRESHOLD_MINUTES as FAILED.

    Only reaps records that have received NO webhook activity (raw_response is
    empty). Once any webhook lands — even a non-terminal one like ringing or
    in_progress — voiceb is in charge of the lifecycle and we shouldn't race
    its terminal webhook with our own auto-fail.

    Invoked both on-demand (before dispatching a new call) and by a periodic
    Celery beat task. Uses per-instance save() so the CallRecord post_save
    signal fires — that signal resets the Application status from AI_SCREENING
    back to APPLIED and creates a user notification.

    Returns the list of reaped CallRecord IDs.
    """
    from .models import CallRecord

    active_statuses = [
        CallRecord.Status.QUEUED,
        CallRecord.Status.INITIATED,
        CallRecord.Status.RINGING,
        CallRecord.Status.IN_PROGRESS,
    ]
    stale_threshold_minutes = get_call_stale_threshold_minutes()
    stale_cutoff = timezone.now() - timedelta(minutes=stale_threshold_minutes)

    qs = CallRecord.objects.filter(
        status__in=active_statuses,
        created_at__lt=stale_cutoff,
        raw_response={},
    )
    if tenant_id is not None:
        qs = qs.filter(tenant_id=tenant_id)
    if application_id is not None:
        qs = qs.filter(application_id=application_id)

    error_message = (
        f"Auto-failed: no terminal status received within "
        f"{stale_threshold_minutes} minutes (likely missed provider webhook)."
    )

    reaped_ids = []
    for record in qs.iterator():
        record.status = CallRecord.Status.FAILED
        record.error_message = error_message
        record.save(update_fields=["status", "error_message", "updated_at"])
        reaped_ids.append(str(record.id))

    if reaped_ids:
        logger.warning(
            "Auto-failed %d stale call record(s): %s",
            len(reaped_ids), reaped_ids,
        )
    return reaped_ids


class ActiveCallExistsError(Exception):
    """
    Raised when a new screening call cannot be dispatched because an active
    (non-stale) CallRecord already exists for the application. Carries
    structured info so the API can return a useful 400 payload to the frontend.
    """

    def __init__(self, call_record) -> None:
        self.call_record = call_record
        self.stale_at = compute_call_stale_at(call_record)
        self.seconds_until_stale = compute_seconds_until_stale(call_record)
        self.threshold_minutes = get_call_stale_threshold_minutes()
        super().__init__(
            f"An active call (id={call_record.id}, status={call_record.status}) "
            f"already exists for this application."
        )


class AIScreeningService:
    """
    Orchestrates AI voice screening calls for job applications.
    Bridges between SmartHR-In data models and the Voice AI Orchestrator.
    """

    def __init__(self) -> None:
        self.voice_client = VoiceAIClient()

    def trigger_screening_call(
        self,
        application_id: str,
        tenant_id: str,
        owner_user_id: str,
        auth_token: Optional[str] = None,
    ) -> "CallRecord":  # noqa: F821
        """
        Full screening call dispatch flow:
        1. Fetch Application with related Job and Applicant
        2. Validate all prerequisites
        3. Create CallRecord with QUEUED status
        4. Dispatch to Voice AI Orchestrator
        5. Update CallRecord with provider call ID and INITIATED status
        """
        from applications.models import Application
        from .models import CallRecord

        # 1. Fetch with related objects
        try:
            application = Application.objects.select_related("job", "applicant").get(
                id=application_id,
                tenant_id=tenant_id,
            )
        except Application.DoesNotExist:
            raise ValueError(f"Application {application_id} not found for tenant {tenant_id}")

        job = application.job
        applicant = application.applicant

        # 2. Validate prerequisites
        if not job.voice_agent_id:
            raise ValueError(
                f"Job '{job.title}' has no voice_agent_id configured. "
                "Set it in the job settings before triggering AI screening."
            )

        if not applicant.phone:
            raise ValueError(
                f"Applicant {applicant.first_name} {applicant.last_name} has no phone number. "
                "A phone number is required to dispatch an AI screening call."
            )

        # Validate/normalize phone
        try:
            phone = _normalize_phone(applicant.phone)
        except ValueError as exc:
            raise ValueError(str(exc)) from exc

        # Reap any stale in-flight records for this application before evaluating
        # the active-call guard. Records older than CALL_STALE_THRESHOLD_MINUTES
        # are treated as abandoned (missed webhook from the provider).
        reap_stale_calls(tenant_id=tenant_id, application_id=str(application.id))

        active_statuses = [
            CallRecord.Status.QUEUED,
            CallRecord.Status.INITIATED,
            CallRecord.Status.RINGING,
            CallRecord.Status.IN_PROGRESS,
        ]
        stale_cutoff = timezone.now() - timedelta(minutes=get_call_stale_threshold_minutes())

        existing_call = (
            CallRecord.objects.filter(
                application=application,
                tenant_id=tenant_id,
                status__in=active_statuses,
                created_at__gte=stale_cutoff,
            )
            .order_by("-created_at")
            .first()
        )
        if existing_call:
            raise ActiveCallExistsError(existing_call)

        # 3. Build call context and metadata
        call_context = {
            "candidateName": f"{applicant.first_name} {applicant.last_name}",
            "jobTitle": job.title,
            "jobDescription": (job.description or "")[:500],
            "requirements": (job.requirements or "")[:500],
            "candidateSkills": ", ".join(applicant.skills or []),
            "candidateExperience": f"{applicant.experience_years} years" if applicant.experience_years else "Not specified",
        }
        # Merge any voice_agent_config overrides
        if job.voice_agent_config:
            call_context.update(job.voice_agent_config.get("call_context_overrides", {}))

        metadata = {
            "applicationId": str(application.id),
            "jobId": str(job.id),
            "applicantId": str(applicant.id),
            "tenantId": str(tenant_id),
            "source": "smarthrin",
        }

        # 4. Create CallRecord with QUEUED status
        call_record = CallRecord.objects.create(
            application=application,
            tenant_id=tenant_id,
            owner_user_id=owner_user_id,
            voice_agent_id=str(job.voice_agent_id),
            phone=phone,
            status=CallRecord.Status.QUEUED,
            provider=CallRecord.Provider.OMNIDIM,
        )

        # 5. Dispatch to Voice AI Orchestrator
        try:
            response = self.voice_client.start_call(
                tenant_id=str(tenant_id),
                agent_id=str(job.voice_agent_id),
                phone=phone,
                call_context=call_context,
                metadata=metadata,
                auth_token=auth_token,
            )
            # response = { id, status, agentId, phone, provider, createdAt }
            call_record.provider_call_id = response.get("id", "")
            provider_str = response.get("provider", "OMNIDIM")
            call_record.provider = provider_str if provider_str in ["OMNIDIM", "BOLNA"] else "OMNIDIM"
            call_record.status = CallRecord.Status.INITIATED
            call_record.save(update_fields=["provider_call_id", "provider", "status", "updated_at"])

            logger.info(
                f"AI screening call dispatched: application={application_id}, "
                f"call_record={call_record.id}, provider_call_id={call_record.provider_call_id}"
            )

        except VoiceAIError as exc:
            call_record.status = CallRecord.Status.FAILED
            call_record.error_message = str(exc)
            call_record.save(update_fields=["status", "error_message", "updated_at"])
            logger.error(f"VoiceAI call dispatch failed for application {application_id}: {exc}")
            raise

        except Exception as exc:
            call_record.status = CallRecord.Status.FAILED
            call_record.error_message = str(exc)
            call_record.save(update_fields=["status", "error_message", "updated_at"])
            logger.exception(f"Unexpected error dispatching call for application {application_id}")
            raise

        return call_record

    def get_call_status(self, call_record_id: str, tenant_id: str) -> "CallRecord":  # noqa: F821
        """Fetches latest call status from Voice AI and updates local CallRecord."""
        from .models import CallRecord

        call_record = CallRecord.objects.get(id=call_record_id, tenant_id=tenant_id)
        if not call_record.provider_call_id:
            return call_record

        try:
            remote = self.voice_client.get_call(
                tenant_id=str(tenant_id),
                call_id=call_record.provider_call_id,
            )
            status_map = {
                "QUEUED": CallRecord.Status.QUEUED,
                "RINGING": CallRecord.Status.RINGING,
                "IN_PROGRESS": CallRecord.Status.IN_PROGRESS,
                "COMPLETED": CallRecord.Status.COMPLETED,
                "FAILED": CallRecord.Status.FAILED,
                "CANCELLED": CallRecord.Status.FAILED,
            }
            new_status = status_map.get(remote.get("status", ""), call_record.status)
            call_record.status = new_status
            call_record.duration = remote.get("duration") or call_record.duration
            call_record.transcript = remote.get("transcript") or call_record.transcript
            call_record.summary = remote.get("summary") or call_record.summary
            call_record.recording_url = remote.get("recordingUrl") or call_record.recording_url
            call_record.save()
        except VoiceAIError as exc:
            logger.warning(f"Could not fetch remote call status for {call_record_id}: {exc}")

        return call_record

    def retry_failed_call(
        self,
        call_record_id: str,
        tenant_id: str,
        owner_user_id: str,
    ) -> "CallRecord":  # noqa: F821
        """For a FAILED call: creates a new CallRecord and re-triggers the screening call."""
        from .models import CallRecord

        original = CallRecord.objects.get(id=call_record_id, tenant_id=tenant_id)
        if original.status not in [CallRecord.Status.FAILED, CallRecord.Status.NO_ANSWER, CallRecord.Status.BUSY]:
            raise ValueError(f"Cannot retry call with status '{original.status}'")

        return self.trigger_screening_call(
            application_id=str(original.application_id),
            tenant_id=tenant_id,
            owner_user_id=owner_user_id,
        )

    def list_available_agents(self, tenant_id: str) -> Any:
        """Fetches active agents from Voice AI Orchestrator for the agent selector."""
        return self.voice_client.list_agents(tenant_id=str(tenant_id), is_active=True)


# Module-level shortcut for backward compatibility
def trigger_ai_screening_call(
    application_id: str,
    tenant_id: str,
    owner_user_id: str,
    auth_token: Optional[str] = None,
) -> Any:
    """Thin wrapper around AIScreeningService.trigger_screening_call."""
    service = AIScreeningService()
    return service.trigger_screening_call(application_id, tenant_id, owner_user_id, auth_token=auth_token)
