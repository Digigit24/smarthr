"""JWT Authentication Middleware — sets request attributes from JWT payload."""
import json
import logging
import os
import time
from logging.handlers import TimedRotatingFileHandler
from typing import Any, Callable

from django.conf import settings

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


def _get_api_logger() -> logging.Logger:
    """Return a logger that writes to alogs/api.log with daily rotation."""
    logger_name = "alogs.api"
    api_logger = logging.getLogger(logger_name)
    if api_logger.handlers:
        return api_logger

    logs_dir = os.path.join(settings.BASE_DIR, "alogs")
    os.makedirs(logs_dir, exist_ok=True)

    log_file = os.path.join(logs_dir, "api.log")
    handler = TimedRotatingFileHandler(log_file, when="midnight", backupCount=30, encoding="utf-8")
    handler.setFormatter(logging.Formatter("%(message)s"))
    api_logger.addHandler(handler)
    api_logger.setLevel(logging.DEBUG)
    api_logger.propagate = False
    return api_logger


class APILoggingMiddleware:
    """
    Logs every API request and response to alogs/api.log.

    Each entry is a single JSON line containing:
    - timestamp, method, path, status_code
    - request body (for POST/PUT/PATCH)
    - response body (truncated at 10 KB to avoid huge log entries)
    - duration_ms
    """

    MAX_BODY_BYTES = 10_240  # 10 KB

    def __init__(self, get_response: Callable) -> None:
        self.get_response = get_response

    def __call__(self, request: HttpRequest) -> Any:
        start = time.monotonic()
        req_body = self._read_request_body(request)

        response = self.get_response(request)

        duration_ms = round((time.monotonic() - start) * 1000, 1)
        self._log(request, response, req_body, duration_ms)
        return response

    # ------------------------------------------------------------------ #

    def _read_request_body(self, request: HttpRequest) -> Any:
        if request.method not in ("POST", "PUT", "PATCH"):
            return None
        try:
            raw = request.body
            if not raw:
                return None
            return json.loads(raw.decode("utf-8", errors="replace"))
        except (ValueError, Exception):
            return request.body.decode("utf-8", errors="replace")[:self.MAX_BODY_BYTES]

    def _read_response_body(self, response: Any) -> Any:
        try:
            content = response.content
            if len(content) > self.MAX_BODY_BYTES:
                return content[:self.MAX_BODY_BYTES].decode("utf-8", errors="replace") + " … [truncated]"
            return json.loads(content.decode("utf-8", errors="replace"))
        except (ValueError, Exception):
            return None

    def _log(self, request: HttpRequest, response: Any, req_body: Any, duration_ms: float) -> None:
        try:
            entry = {
                "timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
                "method": request.method,
                "path": request.get_full_path(),
                "status_code": response.status_code,
                "duration_ms": duration_ms,
                "tenant_id": str(getattr(request, "tenant_id", "")),
                "user_id": str(getattr(request, "user_id", "")),
                "request_body": req_body,
                "response_body": self._read_response_body(response),
            }
            _get_api_logger().debug(json.dumps(entry, default=str))
        except Exception:  # never let logging crash the request
            pass
