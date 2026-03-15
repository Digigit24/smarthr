"""Call Queue models for batch AI screening."""
from django.db import models

from calls.models import CallRecord
from applications.models import Application
from common.models import TenantBaseModel
from jobs.models import Job


class CallQueue(TenantBaseModel):
    """Manages a batch of AI screening calls for a set of applicants."""

    class Status(models.TextChoices):
        DRAFT = "DRAFT", "Draft"
        RUNNING = "RUNNING", "Running"
        PAUSED = "PAUSED", "Paused"
        COMPLETED = "COMPLETED", "Completed"
        CANCELLED = "CANCELLED", "Cancelled"

    name = models.CharField(max_length=255)
    job = models.ForeignKey(Job, on_delete=models.CASCADE, related_name="call_queues")
    voice_agent_id = models.CharField(max_length=255)
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.DRAFT)
    config = models.JSONField(
        default=dict,
        blank=True,
        help_text=(
            "Queue configuration: max_concurrent_calls, delay_between_calls_seconds, "
            "max_retries, call_window_start, call_window_end, timezone, "
            "auto_shortlist_threshold, auto_reject_threshold, filter_statuses."
        ),
    )
    total_queued = models.IntegerField(default=0)
    total_called = models.IntegerField(default=0)
    total_completed = models.IntegerField(default=0)
    total_failed = models.IntegerField(default=0)
    started_at = models.DateTimeField(null=True, blank=True)
    completed_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        db_table = "call_queues"
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["tenant_id", "status"]),
            models.Index(fields=["tenant_id", "job_id"]),
        ]

    def get_config(self) -> dict:
        """Return config with defaults filled in."""
        from django.conf import settings

        defaults = {
            "max_concurrent_calls": 1,
            "delay_between_calls_seconds": 30,
            "max_retries": 2,
            "call_window_start": "09:00",
            "call_window_end": "18:00",
            "timezone": "Asia/Kolkata",
            "auto_shortlist_threshold": getattr(settings, "AUTO_SHORTLIST_THRESHOLD", 7.0),
            "auto_reject_threshold": getattr(settings, "AUTO_REJECT_THRESHOLD", 4.0),
            "filter_statuses": ["APPLIED"],
        }
        defaults.update(self.config or {})
        return defaults

    def __str__(self) -> str:
        return f"CallQueue '{self.name}' [{self.status}]"


class CallQueueItem(TenantBaseModel):
    """A single applicant entry in a CallQueue."""

    class Status(models.TextChoices):
        PENDING = "PENDING", "Pending"
        CALLING = "CALLING", "Calling"
        COMPLETED = "COMPLETED", "Completed"
        FAILED = "FAILED", "Failed"
        SKIPPED = "SKIPPED", "Skipped"
        CANCELLED = "CANCELLED", "Cancelled"

    queue = models.ForeignKey(CallQueue, on_delete=models.CASCADE, related_name="items")
    application = models.ForeignKey(
        Application, on_delete=models.CASCADE, related_name="queue_items"
    )
    position = models.IntegerField()
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.PENDING)
    call_record = models.ForeignKey(
        CallRecord,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="queue_items",
    )
    attempts = models.IntegerField(default=0)
    last_attempt_at = models.DateTimeField(null=True, blank=True)
    error_message = models.TextField(blank=True, default="")
    score = models.DecimalField(max_digits=5, decimal_places=2, null=True, blank=True)
    completed_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        db_table = "call_queue_items"
        ordering = ["position"]
        indexes = [
            models.Index(fields=["queue_id", "status"]),
            models.Index(fields=["tenant_id", "application_id"]),
            models.Index(fields=["queue_id", "position"]),
        ]
        unique_together = [("queue", "application")]

    def __str__(self) -> str:
        return f"QueueItem #{self.position} [{self.status}] in {self.queue}"
