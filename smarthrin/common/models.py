"""Abstract base models for tenant isolation."""
import uuid

from django.db import models


class TenantBaseModel(models.Model):
    """
    Abstract base model providing UUID primary key, tenant isolation fields,
    and automatic timestamps. All SmartHR models inherit from this.
    """

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    tenant_id = models.UUIDField(db_index=True)
    owner_user_id = models.UUIDField(db_index=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        abstract = True
