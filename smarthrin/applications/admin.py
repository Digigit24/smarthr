"""Django admin registration for Application model."""
from django.contrib import admin

from .models import Application


@admin.register(Application)
class ApplicationAdmin(admin.ModelAdmin):
    list_display = ["id", "job", "applicant", "status", "score", "tenant_id"]
    list_filter = ["status"]
    search_fields = ["applicant__email", "job__title"]
