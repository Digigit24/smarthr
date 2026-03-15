"""Application model — links an Applicant to a Job."""
from django.db import models

from applicants.models import Applicant
from common.models import TenantBaseModel
from jobs.models import Job


class Application(TenantBaseModel):
    class Status(models.TextChoices):
        APPLIED = "APPLIED", "Applied"
        AI_SCREENING = "AI_SCREENING", "AI Screening"
        AI_COMPLETED = "AI_COMPLETED", "AI Completed"
        SHORTLISTED = "SHORTLISTED", "Shortlisted"
        INTERVIEW_SCHEDULED = "INTERVIEW_SCHEDULED", "Interview Scheduled"
        INTERVIEWED = "INTERVIEWED", "Interviewed"
        OFFER = "OFFER", "Offer"
        HIRED = "HIRED", "Hired"
        REJECTED = "REJECTED", "Rejected"
        WITHDRAWN = "WITHDRAWN", "Withdrawn"

    job = models.ForeignKey(Job, on_delete=models.CASCADE, related_name="applications")
    applicant = models.ForeignKey(Applicant, on_delete=models.CASCADE, related_name="applications")
    status = models.CharField(max_length=30, choices=Status.choices, default=Status.APPLIED)
    score = models.DecimalField(max_digits=5, decimal_places=2, null=True, blank=True)
    rejection_reason = models.TextField(blank=True, default="")
    notes = models.TextField(blank=True, default="")
    metadata = models.JSONField(default=dict, blank=True)

    class Meta:
        db_table = "applications"
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["tenant_id", "job_id", "status"]),
            models.Index(fields=["tenant_id", "applicant_id"]),
            models.Index(fields=["tenant_id", "status"]),
        ]
        constraints = [
            models.UniqueConstraint(
                fields=["tenant_id", "job_id", "applicant_id"],
                name="unique_tenant_job_applicant",
            )
        ]

    def __str__(self) -> str:
        return f"{self.applicant} → {self.job} [{self.status}]"
