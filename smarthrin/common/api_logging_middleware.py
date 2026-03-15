"""API Request/Response Logging Middleware.

Logs every API call (payload + response) as JSON to alogs/<date>.log.
"""
import json
import logging
import time
import uuid
from pathlib import Path

from django.conf import settings
from django.http import HttpRequest, HttpResponse

logger = logging.getLogger("api_logger")


def _try_parse_json(body: bytes) -> object:
    if not body:
        return None
    try:
        return json.loads(body.decode("utf-8", errors="replace"))
    except (json.JSONDecodeError, ValueError):
        return body.decode("utf-8", errors="replace")


def _try_parse_response_body(response: HttpResponse) -> object:
    content_type = response.get("Content-Type", "")
    if "application/json" not in content_type:
        return None
    try:
        return json.loads(response.content.decode("utf-8", errors="replace"))
    except (json.JSONDecodeError, ValueError):
        return response.content.decode("utf-8", errors="replace")


class APILoggingMiddleware:
    """Logs every request payload and response to alogs/<YYYY-MM-DD>.log."""

    def __init__(self, get_response) -> None:
        self.get_response = get_response
        self._configure_logger()

    def _configure_logger(self) -> None:
        if logger.handlers:
            return

        log_dir: Path = getattr(settings, "API_LOG_DIR", Path(settings.BASE_DIR) / "alogs")
        log_dir.mkdir(parents=True, exist_ok=True)

        import logging.handlers

        handler = logging.handlers.TimedRotatingFileHandler(
            filename=str(log_dir / "api.log"),
            when="midnight",
            backupCount=30,
            encoding="utf-8",
            utc=True,
        )
        handler.suffix = "%Y-%m-%d"
        handler.setFormatter(logging.Formatter("%(message)s"))
        logger.addHandler(handler)
        logger.setLevel(logging.DEBUG)
        logger.propagate = False

    def __call__(self, request: HttpRequest) -> HttpResponse:
        request_id = str(uuid.uuid4())
        started_at = time.monotonic()

        request_body = b""
        if request.method in ("POST", "PUT", "PATCH"):
            try:
                request_body = request.body
            except Exception:
                pass

        response = self.get_response(request)

        duration_ms = round((time.monotonic() - started_at) * 1000, 2)

        entry = {
            "request_id": request_id,
            "method": request.method,
            "path": request.path,
            "query": dict(request.GET),
            "status": response.status_code,
            "duration_ms": duration_ms,
            "request_body": _try_parse_json(request_body),
            "response_body": _try_parse_response_body(response),
        }

        # Attach user/tenant if set by JWT middleware
        if hasattr(request, "tenant_id"):
            entry["tenant_id"] = str(request.tenant_id)
        if hasattr(request, "user_id"):
            entry["user_id"] = str(request.user_id)

        try:
            logger.debug(json.dumps(entry, default=str))
        except Exception:
            pass

        return response
