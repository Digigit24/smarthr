from django.contrib import admin
from .models import Activity

@admin.register(Activity)
class ActivityAdmin(admin.ModelAdmin):
    list_display = ["id", "actor_email", "verb", "resource_type", "resource_id", "resource_label", "tenant_id", "created_at"]
    list_filter = ["verb", "resource_type"]
    search_fields = ["actor_email", "resource_label", "resource_id"]
    readonly_fields = ["id", "tenant_id", "owner_user_id", "created_at", "updated_at"]
