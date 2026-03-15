"""Django admin registration for Job model."""
from django.contrib import admin

from .models import Job


@admin.register(Job)
class JobAdmin(admin.ModelAdmin):
    list_display = [
        "id",
        "title",
        "department",
        "status",
        "job_type",
        "application_count",
        "tenant_id",
    ]
    list_filter = ["status", "job_type", "experience_level"]
    search_fields = ["title", "department", "location"]
