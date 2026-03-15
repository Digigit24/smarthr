"""Webhook endpoints — no JWT auth required."""
import hashlib
import hmac
import json
import logging

from django.conf import settings
from django.http import JsonResponse
from django.utils.decorators import method_decorator
from django.views import View
from django.views.decorators.csrf import csrf_exempt

from .handlers import handle_call_completed, handle_call_status

logger = logging.getLogger(__name__)

WEBHOOK_SECRET = getattr(settings, "VOICE_AI_API_KEY", "")


def _verify_signature(request) -> bool:
    """Verify X-Webhook-Signature header if present. Non-blocking if absent."""
    sig = request.headers.get("X-Webhook-Signature", "")
    if not sig or not WEBHOOK_SECRET:
        return True  # Allow in development / if no signature configured
    body = request.body
    expected = hmac.new(WEBHOOK_SECRET.encode(), body, hashlib.sha256).hexdigest()
    return hmac.compare_digest(sig, expected)


@method_decorator(csrf_exempt, name="dispatch")
class CallCompletedWebhookView(View):
    def post(self, request):
        if not _verify_signature(request):
            return JsonResponse({"error": "Invalid signature"}, status=401)
        try:
            payload = json.loads(request.body)
        except json.JSONDecodeError:
            return JsonResponse({"error": "Invalid JSON"}, status=400)
        try:
            result = handle_call_completed(payload)
            return JsonResponse(result)
        except Exception as exc:
            logger.exception(f"Error processing call-completed webhook: {exc}")
            return JsonResponse({"error": str(exc)}, status=500)


@method_decorator(csrf_exempt, name="dispatch")
class CallStatusWebhookView(View):
    def post(self, request):
        if not _verify_signature(request):
            return JsonResponse({"error": "Invalid signature"}, status=401)
        try:
            payload = json.loads(request.body)
        except json.JSONDecodeError:
            return JsonResponse({"error": "Invalid JSON"}, status=400)
        try:
            result = handle_call_status(payload)
            return JsonResponse(result)
        except Exception as exc:
            logger.exception(f"Error processing call-status webhook: {exc}")
            return JsonResponse({"error": str(exc)}, status=500)
