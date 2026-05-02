"""CallRecord and Scorecard models."""
from django.db import models

from applications.models import Application
from common.models import TenantBaseModel


class CallRecord(TenantBaseModel):
    class Provider(models.TextChoices):
        OMNIDIM = "OMNIDIM", "Omnidim"
        BOLNA = "BOLNA", "Bolna"

    class Status(models.TextChoices):
        QUEUED = "QUEUED", "Queued"
        INITIATED = "INITIATED", "Initiated"
        RINGING = "RINGING", "Ringing"
        IN_PROGRESS = "IN_PROGRESS", "In Progress"
        COMPLETED = "COMPLETED", "Completed"
        FAILED = "FAILED", "Failed"
        NO_ANSWER = "NO_ANSWER", "No Answer"
        BUSY = "BUSY", "Busy"

    application = models.ForeignKey(Application, on_delete=models.CASCADE, related_name="call_records")
    provider = models.CharField(max_length=20, choices=Provider.choices, default=Provider.OMNIDIM)
    voice_agent_id = models.CharField(max_length=255)
    provider_call_id = models.CharField(max_length=255, blank=True, default="")
    phone = models.CharField(max_length=20)
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.QUEUED)
    duration = models.IntegerField(null=True, blank=True)  # seconds
    transcript = models.TextField(blank=True, default="")
    recording_url = models.URLField(blank=True, default="")
    summary = models.TextField(blank=True, default="")
    raw_response = models.JSONField(default=dict, blank=True)
    started_at = models.DateTimeField(null=True, blank=True)
    ended_at = models.DateTimeField(null=True, blank=True)
    error_message = models.TextField(blank=True, default="")

    class Meta:
        db_table = "call_records"
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["tenant_id", "application_id"]),
            models.Index(fields=["tenant_id", "status"]),
            models.Index(fields=["provider_call_id"]),
            models.Index(fields=["tenant_id", "provider_call_id"]),
        ]

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._original_status = self.status if self.pk else None

    def __str__(self) -> str:
        return f"Call {self.provider_call_id or self.id} [{self.status}]"


class Scorecard(TenantBaseModel):
    class Recommendation(models.TextChoices):
        STRONG_YES = "STRONG_YES", "Strong Yes"
        YES = "YES", "Yes"
        MAYBE = "MAYBE", "Maybe"
        NO = "NO", "No"
        STRONG_NO = "STRONG_NO", "Strong No"

    application = models.ForeignKey(Application, on_delete=models.CASCADE, related_name="scorecards")
    call_record = models.ForeignKey(
        CallRecord, on_delete=models.SET_NULL, null=True, blank=True, related_name="scorecard"
    )
    communication_score = models.DecimalField(max_digits=4, decimal_places=2, default=0)
    knowledge_score = models.DecimalField(max_digits=4, decimal_places=2, default=0)
    confidence_score = models.DecimalField(max_digits=4, decimal_places=2, default=0)
    relevance_score = models.DecimalField(max_digits=4, decimal_places=2, default=0)
    overall_score = models.DecimalField(max_digits=4, decimal_places=2, default=0)
    summary = models.TextField(blank=True, default="")
    strengths = models.JSONField(default=list, blank=True)
    weaknesses = models.JSONField(default=list, blank=True)
    recommendation = models.CharField(
        max_length=20, choices=Recommendation.choices, default=Recommendation.MAYBE
    )
    detailed_feedback = models.JSONField(default=dict, blank=True)

    class Meta:
        db_table = "scorecards"
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["tenant_id", "application_id"]),
            models.Index(fields=["tenant_id", "overall_score"]),
        ]
        constraints = [
            # One Scorecard per CallRecord. The upsert path in
            # webhooks/handlers.py turns a duplicate webhook from voiceb (or a
            # race between the webhook handler and the generate_scorecard
            # Celery task) into an UPDATE rather than a duplicate INSERT.
            models.UniqueConstraint(
                fields=["call_record"],
                name="unique_scorecard_per_call_record",
                condition=models.Q(call_record__isnull=False),
            ),
        ]

    def __str__(self) -> str:
        return f"Scorecard for {self.application} — {self.overall_score}"
