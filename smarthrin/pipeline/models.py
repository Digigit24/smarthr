"""Pipeline stage model."""
from django.db import models
from django.utils.text import slugify

from common.models import TenantBaseModel


class PipelineStage(TenantBaseModel):
    name = models.CharField(max_length=255)
    slug = models.SlugField(max_length=255)
    order = models.IntegerField(default=0)
    color = models.CharField(max_length=7, default="#6366f1")
    is_default = models.BooleanField(default=False)
    is_terminal = models.BooleanField(default=False)
    auto_action = models.JSONField(default=dict, blank=True)

    class Meta:
        db_table = "pipeline_stages"
        ordering = ["order"]
        indexes = [
            models.Index(fields=["tenant_id", "order"]),
        ]
        constraints = [
            models.UniqueConstraint(
                fields=["tenant_id", "slug"],
                name="unique_tenant_stage_slug",
            )
        ]

    def save(self, *args, **kwargs):
        if not self.slug:
            self.slug = slugify(self.name)
        super().save(*args, **kwargs)

    def __str__(self) -> str:
        return f"{self.name} (order={self.order})"
