"""Applicant model."""
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
    email = models.EmailField()
    phone = models.CharField(max_length=20, blank=True, default="")
    resume_url = models.URLField(blank=True, default="")
    linkedin_url = models.URLField(blank=True, default="")
    portfolio_url = models.URLField(blank=True, default="")
    skills = models.JSONField(default=list, blank=True)
    experience_years = models.IntegerField(null=True, blank=True)
    current_company = models.CharField(max_length=255, blank=True, default="")
    current_role = models.CharField(max_length=255, blank=True, default="")
    notes = models.TextField(blank=True, default="")
    source = models.CharField(max_length=20, choices=Source.choices, default=Source.MANUAL)
    tags = models.JSONField(default=list, blank=True)

    class Meta:
        db_table = "applicants"
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["tenant_id", "email"]),
        ]
        constraints = [
            models.UniqueConstraint(
                fields=["tenant_id", "email"],
                name="unique_tenant_applicant_email",
            )
        ]

    def __str__(self) -> str:
        return f"{self.first_name} {self.last_name} <{self.email}>"

    @property
    def full_name(self) -> str:
        return f"{self.first_name} {self.last_name}"
