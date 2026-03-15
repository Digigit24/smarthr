"""Django admin registration for PipelineStage model."""
from django.contrib import admin

from .models import PipelineStage


@admin.register(PipelineStage)
class PipelineStageAdmin(admin.ModelAdmin):
    list_display = [
        "id",
        "name",
        "slug",
        "order",
        "is_default",
        "is_terminal",
        "tenant_id",
    ]
