"""
Activity logging service.

Usage from anywhere:
    from activities.services import log_activity

    log_activity(
        request=request,
        verb=Activity.Verb.STATUS_CHANGED,
        resource=application,
        before={"status": "APPLIED"},
        after={"status": "SHORTLISTED"},
        metadata={"job_title": application.job.title},
    )
"""
from typing import Any, Optional

from django.db import models

from .models import Activity


def log_activity(
    *,
    tenant_id: str,
    actor_user_id: str,
    actor_email: str = "",
    verb: str,
    resource_type: str,
    resource_id: str,
    resource_label: str = "",
    before: Optional[dict] = None,
    after: Optional[dict] = None,
    metadata: Optional[dict] = None,
    owner_user_id: Optional[str] = None,
) -> Activity:
    """
    Low-level activity logger. All parameters must be supplied explicitly.
    Prefer log_activity_for_request() when a DRF request is available.
    """
    return Activity.objects.create(
        tenant_id=tenant_id,
        owner_user_id=owner_user_id or actor_user_id,
        actor_user_id=actor_user_id,
        actor_email=actor_email,
        verb=verb,
        resource_type=resource_type,
        resource_id=str(resource_id),
        resource_label=resource_label,
        before=before,
        after=after,
        metadata=metadata or {},
    )


def log_activity_for_request(
    request,
    *,
    verb: str,
    resource: models.Model,
    resource_label: str = "",
    before: Optional[dict] = None,
    after: Optional[dict] = None,
    metadata: Optional[dict] = None,
) -> Activity:
    """
    Convenience wrapper that extracts tenant/user info from a DRF request.
    Accepts any TenantBaseModel instance as `resource`.
    """
    resource_type = resource.__class__.__name__
    resource_label = resource_label or str(resource)

    return log_activity(
        tenant_id=str(request.tenant_id),
        actor_user_id=str(request.user_id),
        actor_email=getattr(request, "email", ""),
        verb=verb,
        resource_type=resource_type,
        resource_id=str(resource.pk),
        resource_label=resource_label,
        before=before,
        after=after,
        metadata=metadata or {},
        owner_user_id=str(getattr(resource, "owner_user_id", request.user_id)),
    )
