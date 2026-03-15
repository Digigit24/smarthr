"""JWT Authentication Middleware — sets request attributes from JWT payload."""
import json
import logging
from typing import Any, Callable

import jwt
from django.conf import settings
from django.http import HttpRequest, JsonResponse

from .constants import MODULE_NAME, PUBLIC_PATHS

logger = logging.getLogger(__name__)


class JWTAuthenticationMiddleware:
    """
    Process every request before it reaches views.

    - Skips PUBLIC_PATHS without auth check.
    - Decodes Bearer JWT from Authorization header.
    - Validates required fields and module access.
    - Sets request.user_id, request.tenant_id, etc.
    - Super admins can override tenant_id via x-tenant-id header.
    """

    def __init__(self, get_response: Callable) -> None:
        self.get_response = get_response

    def __call__(self, request: HttpRequest) -> Any:
        if self._is_public(request.path):
            return self.get_response(request)

        token = self._extract_token(request)
        if not token:
            return self._error(401, "Authorization header missing or malformed", "NO_AUTH")

        try:
            payload = jwt.decode(
                token,
                settings.JWT_SECRET_KEY,
                algorithms=[settings.JWT_ALGORITHM],
            )
        except jwt.ExpiredSignatureError:
            return self._error(401, "Token has expired", "TOKEN_EXPIRED")
        except jwt.InvalidTokenError as exc:
            return self._error(401, f"Invalid token: {exc}", "INVALID_TOKEN")

        # Validate required fields
        required = ["user_id", "email", "tenant_id", "tenant_slug", "permissions", "enabled_modules"]
        for field in required:
            if field not in payload:
                return self._error(401, f"Token missing required field: {field}", "INVALID_TOKEN")

        # Check module access
        enabled_modules = payload.get("enabled_modules", [])
        if MODULE_NAME not in enabled_modules:
            return self._error(
                403,
                f"Module '{MODULE_NAME}' not enabled for this tenant",
                "MODULE_NOT_ENABLED",
            )

        # Attach payload to request
        request.user_id = payload["user_id"]
        request.email = payload["email"]
        request.tenant_id = payload["tenant_id"]
        request.tenant_slug = payload["tenant_slug"]
        request.is_super_admin = payload.get("is_super_admin", False)
        request.permissions = payload.get("permissions", {})
        request.enabled_modules = enabled_modules
        request.jwt_payload = payload

        # Super admin tenant override
        x_tenant_id = request.headers.get("X-Tenant-Id")
        if x_tenant_id and request.is_super_admin:
            request.tenant_id = x_tenant_id

        return self.get_response(request)

    def _is_public(self, path: str) -> bool:
        for public in PUBLIC_PATHS:
            if path.startswith(public):
                return True
        return False

    def _extract_token(self, request: HttpRequest) -> str | None:
        auth_header = request.headers.get("Authorization", "")
        if auth_header.startswith("Bearer "):
            return auth_header[7:]
        return None

    def _error(self, status: int, message: str, code: str) -> JsonResponse:
        return JsonResponse({"error": message, "code": code}, status=status)
