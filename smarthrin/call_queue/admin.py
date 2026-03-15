"""Admin registration for call_queue models."""
from django.contrib import admin

from .models import CallQueue, CallQueueItem


class CallQueueItemInline(admin.TabularInline):
    model = CallQueueItem
    extra = 0
    readonly_fields = ["id", "application", "position", "status", "attempts", "score", "call_record", "last_attempt_at", "error_message", "completed_at"]
    fields = ["position", "application", "status", "attempts", "score", "call_record", "last_attempt_at", "error_message", "completed_at"]
    can_delete = False
    show_change_link = True


@admin.register(CallQueue)
class CallQueueAdmin(admin.ModelAdmin):
    list_display = ["name", "job", "status", "total_queued", "total_called", "total_completed", "total_failed", "started_at", "created_at"]
    list_filter = ["status", "created_at"]
    search_fields = ["name", "job__title"]
    readonly_fields = ["id", "tenant_id", "owner_user_id", "total_queued", "total_called", "total_completed", "total_failed", "started_at", "completed_at", "created_at", "updated_at"]
    inlines = [CallQueueItemInline]
    fieldsets = [
        (None, {"fields": ["id", "name", "job", "voice_agent_id", "status"]}),
        ("Config", {"fields": ["config"]}),
        ("Statistics", {"fields": ["total_queued", "total_called", "total_completed", "total_failed", "started_at", "completed_at"]}),
        ("Metadata", {"fields": ["tenant_id", "owner_user_id", "created_at", "updated_at"]}),
    ]


@admin.register(CallQueueItem)
class CallQueueItemAdmin(admin.ModelAdmin):
    list_display = ["queue", "position", "application", "status", "attempts", "score", "last_attempt_at", "completed_at"]
    list_filter = ["status", "created_at"]
    search_fields = ["queue__name", "application__applicant__first_name", "application__applicant__last_name"]
    readonly_fields = ["id", "tenant_id", "owner_user_id", "created_at", "updated_at"]
    raw_id_fields = ["queue", "application", "call_record"]
