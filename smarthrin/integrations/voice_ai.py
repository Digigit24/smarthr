"""Voice AI Orchestrator API client."""
import logging
from typing import Any

import requests

logger = logging.getLogger(__name__)


class VoiceAIService:
    """Client for the Voice AI Orchestrator API."""

    def __init__(self, api_url: str, api_key: str) -> None:
        self.api_url = api_url.rstrip("/")
        self.api_key = api_key
        self.session = requests.Session()
        self.session.headers.update({
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        })

    def dispatch_call(self, agent_id: str, phone: str, metadata: dict[str, Any]) -> dict[str, Any]:
        """
        Start an AI voice screening call.
        POST {api_url}/api/v1/calls/start
        Returns: { call_id, status }
        """
        tenant_id = metadata.get("tenantId", "")
        headers = {"x-tenant-id": tenant_id} if tenant_id else {}
        payload = {"agentId": agent_id, "phone": phone, "metadata": metadata}
        resp = self.session.post(
            f"{self.api_url}/api/v1/calls/start",
            json=payload,
            headers=headers,
            timeout=30,
        )
        resp.raise_for_status()
        return resp.json()

    def get_call_status(self, call_id: str) -> dict[str, Any]:
        """GET {api_url}/api/v1/calls/{call_id}"""
        resp = self.session.get(f"{self.api_url}/api/v1/calls/{call_id}", timeout=30)
        resp.raise_for_status()
        return resp.json()

    def end_call(self, call_id: str) -> None:
        """POST {api_url}/api/v1/calls/{call_id}/end"""
        resp = self.session.post(f"{self.api_url}/api/v1/calls/{call_id}/end", timeout=30)
        resp.raise_for_status()


def get_voice_ai_service() -> VoiceAIService:
    """Return a configured VoiceAIService instance from Django settings."""
    from django.conf import settings
    return VoiceAIService(
        api_url=settings.VOICE_AI_API_URL,
        api_key=settings.VOICE_AI_API_KEY,
    )
