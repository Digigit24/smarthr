"""Tenant-aware mixins for DRF ViewSets and Serializers."""
from typing import Any

from rest_framework import serializers
from rest_framework.request import Request


class TenantViewSetMixin:
    """
    Mixin for DRF ModelViewSet that enforces tenant isolation.

    - get_queryset: always filters by tenant_id; additionally filters
      by owner_user_id when permission_scope == 'own'.
    - perform_create: injects tenant_id and owner_user_id from request.
    - perform_update: prevents tenant_id from being changed.
    """

    def get_queryset(self):
        qs = super().get_queryset()
        request: Request = self.request
        qs = qs.filter(tenant_id=request.tenant_id)

        scope = getattr(request, "permission_scope", None)
        if scope == "own":
            qs = qs.filter(owner_user_id=request.user_id)

        return qs

    def perform_create(self, serializer) -> None:
        request: Request = self.request
        serializer.save(
            tenant_id=request.tenant_id,
            owner_user_id=request.user_id,
        )

    def perform_update(self, serializer) -> None:
        # Never allow tenant_id to change
        serializer.save(tenant_id=self.request.tenant_id)


class TenantSerializerMixin:
    """
    Mixin for DRF Serializers that enforces tenant isolation at
    serializer level. Companion to TenantViewSetMixin.
    """

    def create(self, validated_data: dict[str, Any]) -> Any:
        request = self.context.get("request")
        if request:
            validated_data.setdefault("tenant_id", request.tenant_id)
            validated_data.setdefault("owner_user_id", request.user_id)
        return super().create(validated_data)

    def update(self, instance: Any, validated_data: dict[str, Any]) -> Any:
        # Never change tenant_id on update
        validated_data.pop("tenant_id", None)
        return super().update(instance, validated_data)
