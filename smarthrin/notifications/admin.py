from django.contrib import admin

from .models import Notification


@admin.register(Notification)
class NotificationAdmin(admin.ModelAdmin):
    list_display = ["id", "title", "recipient_user_id", "category", "notification_type", "is_read", "tenant_id"]
    list_filter = ["notification_type", "category", "is_read"]
    search_fields = ["title", "message"]
