"""DRF permission classes for SmartHR permission system."""
from typing import Any, Type

from rest_framework.permissions import BasePermission
from rest_framework.request import Request
from rest_framework.views import APIView

from .tenant_user import TenantUser


class HasSmartHRPermission(BasePermission):
    """
    Base DRF permission class that checks SmartHR permission keys.

    Use require_permission() factory to create scoped permission classes.
    """

    permission_key: str = ""

    def has_permission(self, request: Request, view: APIView) -> bool:
        user: TenantUser = request.user

        if not hasattr(user, "is_super_admin"):
            return False

        if user.is_super_admin:
            request.permission_scope = "all"
            return True

        value = user.get_permission(self.permission_key)
        if not value:
            return False

        # Attach scope to request so get_queryset can filter appropriately
        request.permission_scope = value
        return True


def require_permission(key: str) -> Type[HasSmartHRPermission]:
    """
    Factory that returns a permission class bound to a specific permission key.

    Usage:
        permission_classes = [require_permission("smarthrin.jobs.view")]
    """

    class DynamicPermission(HasSmartHRPermission):
        permission_key = key

        # Give the class a readable name for DRF introspection
        __name__ = f"HasPermission[{key}]"

    DynamicPermission.__name__ = f"HasPermission_{key.replace('.', '_')}"
    DynamicPermission.__qualname__ = DynamicPermission.__name__
    return DynamicPermission
