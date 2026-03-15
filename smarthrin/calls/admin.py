"""Django admin registration for CallRecord and Scorecard models."""
from django.contrib import admin

from .models import CallRecord, Scorecard


@admin.register(CallRecord)
class CallRecordAdmin(admin.ModelAdmin):
    list_display = [
        "id",
        "application_id",
        "provider",
        "status",
        "phone",
        "duration",
        "tenant_id",
    ]
    list_filter = ["status", "provider"]
    search_fields = ["provider_call_id", "phone"]


@admin.register(Scorecard)
class ScorecardAdmin(admin.ModelAdmin):
    list_display = [
        "id",
        "application_id",
        "overall_score",
        "recommendation",
        "tenant_id",
    ]
    list_filter = ["recommendation"]
