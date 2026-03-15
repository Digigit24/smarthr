"""Django admin registration for the Interview model."""
from django.contrib import admin

from .models import Interview


@admin.register(Interview)
class InterviewAdmin(admin.ModelAdmin):
    list_display = [
        "id",
        "application_id",
        "interview_type",
        "scheduled_at",
        "status",
        "interviewer_name",
        "tenant_id",
    ]
    list_filter = ["interview_type", "status"]
