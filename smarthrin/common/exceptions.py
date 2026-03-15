"""Custom exception handler for consistent error response format."""
import logging
from typing import Any, Optional

from rest_framework import status
from rest_framework.response import Response
from rest_framework.views import exception_handler

logger = logging.getLogger(__name__)


def custom_exception_handler(exc: Exception, context: dict[str, Any]) -> Optional[Response]:
    """
    Returns all errors in the format:
    { "error": "message", "code": "ERROR_CODE", "details": {...} }
    """
    response = exception_handler(exc, context)

    if response is None:
        # Unhandled exception — log and return 500
        logger.exception("Unhandled exception in view", exc_info=exc)
        return Response(
            {
                "error": "An internal server error occurred.",
                "code": "INTERNAL_SERVER_ERROR",
                "details": {},
            },
            status=status.HTTP_500_INTERNAL_SERVER_ERROR,
        )

    # Normalise the DRF response data into our standard format
    data = response.data

    if isinstance(data, dict):
        # Extract a human-readable message
        if "detail" in data:
            message = str(data["detail"])
            code = getattr(data["detail"], "code", "ERROR") if hasattr(data["detail"], "code") else "ERROR"
        else:
            message = _flatten_errors(data)
            code = "VALIDATION_ERROR"
        details = {k: v for k, v in data.items() if k != "detail"}
    elif isinstance(data, list):
        message = "; ".join(str(e) for e in data)
        code = "ERROR"
        details = {}
    else:
        message = str(data)
        code = "ERROR"
        details = {}

    response.data = {
        "error": message,
        "code": code,
        "details": details,
    }

    return response


def _flatten_errors(data: dict) -> str:
    """Flatten nested validation errors into a single readable string."""
    messages = []
    for field, errors in data.items():
        if isinstance(errors, list):
            messages.append(f"{field}: {'; '.join(str(e) for e in errors)}")
        elif isinstance(errors, dict):
            messages.append(f"{field}: {_flatten_errors(errors)}")
        else:
            messages.append(f"{field}: {errors}")
    return " | ".join(messages)
