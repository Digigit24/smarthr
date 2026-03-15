"""Interview model."""
import uuid

from django.db import models

from applications.models import Application
from common.models import TenantBaseModel


class Interview(TenantBaseModel):
    class InterviewType(models.TextChoices):
        AI_VOICE = "AI_VOICE", "AI Voice"
        HR_SCREEN = "HR_SCREEN", "HR Screen"
        TECHNICAL = "TECHNICAL", "Technical"
        CULTURE_FIT = "CULTURE_FIT", "Culture Fit"
        FINAL = "FINAL", "Final"

    class Status(models.TextChoices):
        SCHEDULED = "SCHEDULED", "Scheduled"
        CONFIRMED = "CONFIRMED", "Confirmed"
        IN_PROGRESS = "IN_PROGRESS", "In Progress"
        COMPLETED = "COMPLETED", "Completed"
        CANCELLED = "CANCELLED", "Cancelled"
        NO_SHOW = "NO_SHOW", "No Show"

    application = models.ForeignKey(Application, on_delete=models.CASCADE, related_name="interviews")
    interview_type = models.CharField(max_length=20, choices=InterviewType.choices, default=InterviewType.HR_SCREEN)
    scheduled_at = models.DateTimeField()
    duration_minutes = models.IntegerField(default=30)
    interviewer_user_id = models.UUIDField(null=True, blank=True)
    interviewer_name = models.CharField(max_length=255, blank=True, default="")
    interviewer_email = models.EmailField(blank=True, default="")
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.SCHEDULED)
    meeting_link = models.URLField(blank=True, default="")
    calendar_event_id = models.CharField(max_length=255, blank=True, default="")
    feedback = models.TextField(blank=True, default="")
    rating = models.IntegerField(null=True, blank=True)  # 1-5

    class Meta:
        db_table = "interviews"
        ordering = ["-scheduled_at"]
        indexes = [
            models.Index(fields=["tenant_id", "scheduled_at"]),
            models.Index(fields=["tenant_id", "status"]),
            models.Index(fields=["tenant_id", "interviewer_user_id"]),
        ]

    def __str__(self) -> str:
        return f"{self.interview_type} interview on {self.scheduled_at} [{self.status}]"
