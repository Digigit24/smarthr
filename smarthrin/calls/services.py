"""Service layer for call-related business logic."""
from .models import CallRecord


def trigger_ai_screening_call(
    application_id: str, tenant_id: str, owner_user_id: str
) -> "CallRecord":
    """
    Trigger an AI screening call for the given application.

    Creates a CallRecord, dispatches the call via VoiceAIService, and updates
    the record with the provider's call ID. On any exception the record is
    marked FAILED and the exception is re-raised.
    """
    from applications.models import Application  # local import to avoid circular dependency

    application = Application.objects.select_related("job", "applicant").get(
        id=application_id,
        tenant_id=tenant_id,
    )

    if not application.job.voice_agent_id:
        raise ValueError(
            f"Job {application.job.id} does not have a voice_agent_id configured."
        )

    if not application.applicant.phone:
        raise ValueError(
            f"Applicant {application.applicant.id} does not have a phone number."
        )

    call_record = CallRecord.objects.create(
        status=CallRecord.Status.QUEUED,
        application=application,
        voice_agent_id=application.job.voice_agent_id,
        phone=application.applicant.phone,
        tenant_id=tenant_id,
        owner_user_id=owner_user_id,
        provider=CallRecord.Provider.OMNIDIM,
    )

    try:
        metadata = {
            "applicationId": str(application.id),
            "jobId": str(application.job.id),
            "applicantId": str(application.applicant.id),
            "tenantId": tenant_id,
        }

        from integrations.voice_ai import VoiceAIService  # noqa: PLC0415

        service = VoiceAIService()
        result = service.dispatch_call(
            agent_id=application.job.voice_agent_id,
            phone=application.applicant.phone,
            metadata=metadata,
        )

        call_record.provider_call_id = result.get("call_id", "")
        call_record.status = CallRecord.Status.INITIATED
        call_record.save(update_fields=["provider_call_id", "status", "updated_at"])

    except Exception:
        call_record.status = CallRecord.Status.FAILED
        call_record.save(update_fields=["status", "updated_at"])
        raise

    return call_record
