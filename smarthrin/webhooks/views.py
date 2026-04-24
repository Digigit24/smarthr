"""Webhook endpoints — no JWT auth required."""
import hashlib
import hmac
import json
import logging
import time

from django.conf import settings
from django.http import JsonResponse
from django.utils.decorators import method_decorator
from django.views import View
from django.views.decorators.csrf import csrf_exempt
from drf_spectacular.utils import extend_schema

from .handlers import handle_call_completed, handle_call_status

logger = logging.getLogger(__name__)

# Maximum age of a webhook payload before it's considered a replay (seconds)
WEBHOOK_TIMESTAMP_TOLERANCE = 300  # 5 minutes
# Small clock-skew allowance for future timestamps
WEBHOOK_FUTURE_TOLERANCE = 30  # 30 seconds


def _get_webhook_secret() -> str:
    """Read webhook secret from settings at call time (not module import time)."""
    secret = getattr(settings, "WEBHOOK_SECRET", "")
    if not secret:
        logger.warning("WEBHOOK_SECRET not set, no fallback used")
    return secret


def _verify_signature(request) -> tuple[bool, str]:
    """
    Verify X-Webhook-Signature header using HMAC-SHA256.

    In production (DEBUG=False), signature and timestamp are mandatory.
    In development (DEBUG=True), requests without signature/secret are allowed.

    Returns (is_valid, error_message).
    """
    sig = request.headers.get("X-Webhook-Signature", "")
    timestamp_header = request.headers.get("X-Webhook-Timestamp", "")
    is_debug = getattr(settings, "DEBUG", False)
    webhook_secret = _get_webhook_secret()

    # In production, require both secret and signature
    if not is_debug:
        if not webhook_secret:
            logger.error("WEBHOOK_SECRET not configured in production")
            return False, "Unauthorized"
        if not sig:
            return False, "Unauthorized"

    # In development, skip verification if no secret/signature configured
    if not sig or not webhook_secret:
        return True, ""

    # Verify timestamp to prevent replay attacks
    if timestamp_header:
        try:
            ts = int(timestamp_header)
            now = time.time()
            # Reject timestamps too far in the past
            if (now - ts) > WEBHOOK_TIMESTAMP_TOLERANCE:
                logger.warning(f"Webhook timestamp too old: age={int(now - ts)}s")
                return False, "Unauthorized"
            # Reject timestamps too far in the future (small clock-skew allowed)
            if ts > now + WEBHOOK_FUTURE_TOLERANCE:
                logger.warning(f"Webhook timestamp in the future: delta={int(ts - now)}s")
                return False, "Unauthorized"
        except (ValueError, TypeError):
            return False, "Unauthorized"
    elif not is_debug:
        return False, "Unauthorized"

    # Verify HMAC signature
    # Include timestamp in signed payload to bind signature to timestamp
    body = request.body
    if timestamp_header:
        signed_payload = f"{timestamp_header}.".encode() + body
    else:
        signed_payload = body
    expected = hmac.new(webhook_secret.encode(), signed_payload, hashlib.sha256).hexdigest()
    if not hmac.compare_digest(sig, expected):
        logger.warning("Webhook signature mismatch")
        return False, "Unauthorized"

    return True, ""


@method_decorator(csrf_exempt, name="dispatch")
class CallCompletedWebhookView(View):
    """
    POST /api/webhooks/call-completed/

    Called by the Voice AI Orchestrator when a call finishes. Updates the
    CallRecord, creates/updates a Scorecard, and updates the Application status.
    Authentication: HMAC-SHA256 signature via X-Webhook-Signature header.
    """

    def post(self, request):
        is_valid, error = _verify_signature(request)
        if not is_valid:
            logger.warning(f"Webhook signature verification failed: {error}")
            return JsonResponse({"error": "Unauthorized"}, status=401)
        try:
            payload = json.loads(request.body)
        except json.JSONDecodeError:
            return JsonResponse({"error": "Invalid JSON"}, status=400)
        try:
            result = handle_call_completed(payload)
            status_code = 404 if isinstance(result, dict) and result.get("error") == "CallRecord not found" else 200
            return JsonResponse(result, status=status_code)
        except Exception as exc:
            logger.exception(f"Error processing call-completed webhook: {exc}")
            return JsonResponse({"error": "Internal server error"}, status=500)


@method_decorator(csrf_exempt, name="dispatch")
class CallStatusWebhookView(View):
    """
    POST /api/webhooks/call-status/

    Called by the Voice AI Orchestrator for real-time call status updates.
    Authentication: HMAC-SHA256 signature via X-Webhook-Signature header.
    """

    def post(self, request):
        is_valid, error = _verify_signature(request)
        if not is_valid:
            logger.warning(f"Webhook signature verification failed: {error}")
            return JsonResponse({"error": "Unauthorized"}, status=401)
        try:
            payload = json.loads(request.body)
        except json.JSONDecodeError:
            return JsonResponse({"error": "Invalid JSON"}, status=400)
        try:
            result = handle_call_status(payload)
            status_code = 404 if isinstance(result, dict) and result.get("error") == "CallRecord not found" else 200
            return JsonResponse(result, status=status_code)
        except Exception as exc:
            logger.exception(f"Error processing call-status webhook: {exc}")
            return JsonResponse({"error": "Internal server error"}, status=500)
