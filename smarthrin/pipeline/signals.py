"""Pipeline model signals."""
import logging

from django.db.models.signals import post_save
from django.dispatch import receiver

logger = logging.getLogger(__name__)


@receiver(post_save, sender="pipeline.PipelineStage")
def on_pipeline_stage_saved(sender, instance, created, **kwargs):
    """If this is the first stage for a tenant, mark it as default."""
    if not created:
        return
    count = sender.objects.filter(tenant_id=instance.tenant_id).count()
    if count == 1 and not instance.is_default:
        sender.objects.filter(id=instance.id).update(is_default=True)
