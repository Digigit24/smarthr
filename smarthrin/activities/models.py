"""
Activity model — records every significant change across all SmartHR models.

Designed to be flexible: any view or service can log an activity with
arbitrary actor/target/payload information. The activity feed and
notification system can both consume from this model.
"""
import uuid

from django.db import models

from common.models import TenantBaseModel


class Activity(TenantBaseModel):
    """
    A single auditable event in the system.

    actor_user_id  — user_id from JWT (who did it)
    actor_email    — email snapshot at time of action
    verb           — what happened: "created", "updated", "status_changed",
                     "deleted", "triggered_call", "scheduled_interview", etc.
    resource_type  — model class name: "Job", "Application", "Interview", etc.
    resource_id    — UUID of the affected object
    resource_label — human-readable label at time of action (e.g. job title)
    before         — JSON snapshot of relevant fields BEFORE change (nullable)
    after          — JSON snapshot of relevant fields AFTER change (nullable)
    metadata       — any extra context: { job_id, applicant_name, ... }
    """

    class Verb(models.TextChoices):
        CREATED = "created", "Created"
        UPDATED = "updated", "Updated"
        DELETED = "deleted", "Deleted"
        STATUS_CHANGED = "status_changed", "Status Changed"
        PUBLISHED = "published", "Published"
        CLOSED = "closed", "Closed"
        TRIGGERED_CALL = "triggered_call", "Triggered Call"
        CALL_COMPLETED = "call_completed", "Call Completed"
        CALL_FAILED = "call_failed", "Call Failed"
        INTERVIEW_SCHEDULED = "interview_scheduled", "Interview Scheduled"
        INTERVIEW_COMPLETED = "interview_completed", "Interview Completed"
        INTERVIEW_CANCELLED = "interview_cancelled", "Interview Cancelled"
        SCORECARD_CREATED = "scorecard_created", "Scorecard Created"
        NOTE_ADDED = "note_added", "Note Added"
        BULK_ACTION = "bulk_action", "Bulk Action"

    actor_user_id = models.UUIDField(db_index=True)
    actor_email = models.EmailField(blank=True, default="")
    verb = models.CharField(max_length=50, choices=Verb.choices, db_index=True)
    resource_type = models.CharField(max_length=100, db_index=True)
    resource_id = models.UUIDField(db_index=True)
    resource_label = models.CharField(max_length=500, blank=True, default="")
    before = models.JSONField(null=True, blank=True)
    after = models.JSONField(null=True, blank=True)
    metadata = models.JSONField(default=dict, blank=True)

    class Meta:
        db_table = "activities"
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["tenant_id", "resource_type", "resource_id"]),
            models.Index(fields=["tenant_id", "actor_user_id"]),
            models.Index(fields=["tenant_id", "verb"]),
            models.Index(fields=["tenant_id", "created_at"]),
        ]

    def __str__(self) -> str:
        return f"{self.actor_email} {self.verb} {self.resource_type}:{self.resource_id}"
