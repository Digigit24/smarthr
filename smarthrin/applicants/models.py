"""Applicant model."""
from django.contrib.postgres.indexes import GinIndex
from django.db import models

from common.models import TenantBaseModel


class Applicant(TenantBaseModel):
    class Source(models.TextChoices):
        MANUAL = "MANUAL", "Manual"
        WEBSITE = "WEBSITE", "Website"
        LINKEDIN = "LINKEDIN", "LinkedIn"
        REFERRAL = "REFERRAL", "Referral"
        IMPORT = "IMPORT", "Import"

    first_name = models.CharField(max_length=255)
    last_name = models.CharField(max_length=255)
    email = models.EmailField(blank=True, default="")
    phone = models.CharField(max_length=50, blank=True, default="")
    resume_url = models.CharField(max_length=500, blank=True, default="")
    resume_file = models.FileField(
        upload_to="resumes/%Y/%m/",
        max_length=500,
        null=True,
        blank=True,
        help_text="Optional uploaded resume file (PDF/DOC/DOCX). Coexists with resume_url for legacy/external links.",
    )
    linkedin_url = models.CharField(max_length=500, blank=True, default="")
    portfolio_url = models.CharField(max_length=500, blank=True, default="")
    skills = models.JSONField(default=list, blank=True)
    experience_years = models.IntegerField(null=True, blank=True)
    current_company = models.CharField(max_length=255, blank=True, default="")
    current_role = models.CharField(max_length=255, blank=True, default="")
    notes = models.TextField(blank=True, default="")
    source = models.CharField(max_length=20, choices=Source.choices, default=Source.MANUAL)
    tags = models.JSONField(default=list, blank=True)
    custom_fields = models.JSONField(
        default=dict,
        blank=True,
        help_text="Arbitrary key-value data from import or manual entry (e.g. salary expectation, notice period).",
    )

    class Meta:
        db_table = "applicants"
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["tenant_id", "email"]),
            GinIndex(fields=["first_name"], name="applicant_first_name_trgm", opclasses=["gin_trgm_ops"]),
            GinIndex(fields=["last_name"], name="applicant_last_name_trgm", opclasses=["gin_trgm_ops"]),
            GinIndex(fields=["email"], name="applicant_email_trgm", opclasses=["gin_trgm_ops"]),
        ]
        constraints = [
            models.UniqueConstraint(
                fields=["tenant_id", "email"],
                name="unique_tenant_applicant_email",
                condition=models.Q(email__gt=""),
            )
        ]

    def __str__(self) -> str:
        return f"{self.first_name} {self.last_name} <{self.email}>"

    @property
    def full_name(self) -> str:
        return f"{self.first_name} {self.last_name}"
