"""Voice AI Orchestrator API client — full implementation."""
import logging
from typing import Any, Optional

import requests
from django.conf import settings

from .exceptions import (
    VoiceAIAuthError,
    VoiceAICredentialsMissing,
    VoiceAIError,
    VoiceAINotFoundError,
    VoiceAIProviderError,
    VoiceAIValidationError,
)

logger = logging.getLogger(__name__)


class VoiceAIClient:
    """
    HTTP client for the Voice AI Orchestrator API.
    Base URL: settings.VOICE_AI_API_URL (default: http://localhost:4000)
    Auth: Bearer token via settings.VOICE_AI_API_KEY
    Tenant context: passed via x-tenant-id header per request.
    """

    def __init__(self) -> None:
        self.base_url = settings.VOICE_AI_API_URL.rstrip("/")
        self.api_key = settings.VOICE_AI_API_KEY
        self.timeout = 30
        self._session = requests.Session()
        self._session.headers.update({
            "Content-Type": "application/json",
            "Accept": "application/json",
        })

    def _headers(self, tenant_id: Optional[str] = None, auth_token: Optional[str] = None) -> dict[str, str]:
        bearer = auth_token if auth_token else self.api_key
        h = {"Authorization": f"Bearer {bearer}"}
        if tenant_id:
            h["x-tenant-id"] = str(tenant_id)
        return h

    def _request(
        self,
        method: str,
        path: str,
        tenant_id: Optional[str] = None,
        auth_token: Optional[str] = None,
        **kwargs,
    ) -> Any:
        """
        Make an authenticated HTTP request to the Voice AI Orchestrator.
        Parses the { success, data, error } response format.
        Raises typed VoiceAI exceptions on failure.

        Args:
            auth_token: If provided, use this JWT token instead of the service API key.
                        Use when proxying requests on behalf of an authenticated user,
                        since both SmartHR and CeliyoVoice share the same JWT secret.
        """
        url = f"{self.base_url}{path}"
        headers = self._headers(tenant_id, auth_token=auth_token)
        logger.debug(f"VoiceAI {method} {url} tenant={tenant_id}")

        try:
            resp = self._session.request(
                method,
                url,
                headers=headers,
                timeout=self.timeout,
                **kwargs,
            )
        except requests.ConnectionError as exc:
            logger.error("Cannot connect to Voice AI service at %s: %s", self.base_url, exc)
            raise VoiceAIProviderError("Voice AI service is currently unavailable") from exc
        except requests.Timeout as exc:
            logger.error("Voice AI request timed out after %ss", self.timeout)
            raise VoiceAIProviderError("Voice AI service request timed out") from exc

        logger.debug(f"VoiceAI response: {resp.status_code}")

        # Parse JSON safely
        try:
            body = resp.json()
        except Exception:
            body = {}

        # Check for error responses
        if not resp.ok:
            error = body.get("error", {}) if isinstance(body, dict) else {}
            code = error.get("code", "") if isinstance(error, dict) else str(error)
            message = error.get("message", resp.reason) if isinstance(error, dict) else str(error)
            details = error.get("details", {}) if isinstance(error, dict) else {}

            if resp.status_code == 401:
                raise VoiceAIAuthError(message, details=details)
            elif resp.status_code == 404:
                raise VoiceAINotFoundError(message, details=details)
            elif resp.status_code == 400 and code == "CREDENTIALS_MISSING":
                raise VoiceAICredentialsMissing(message, details=details)
            elif resp.status_code in (502, 503, 504):
                raise VoiceAIProviderError(message, details=details)
            elif resp.status_code == 400:
                raise VoiceAIValidationError(message, details=details)
            else:
                raise VoiceAIError(message, code=code or "VOICE_AI_ERROR", status_code=resp.status_code, details=details)

        # Return the data payload
        if isinstance(body, dict) and "data" in body:
            return body["data"]
        return body

    # ------------------------------------------------------------------ #
    # AGENTS
    # ------------------------------------------------------------------ #

    def list_agents(
        self,
        tenant_id: str,
        page: int = 1,
        limit: int = 20,
        provider: Optional[str] = None,
        is_active: Optional[bool] = None,
        search: Optional[str] = None,
        auth_token: Optional[str] = None,
    ) -> dict:
        """GET /api/v1/agents — paginated list of agents."""
        params: dict = {"page": page, "limit": limit}
        if provider:
            params["provider"] = provider
        if is_active is not None:
            params["isActive"] = str(is_active).lower()
        if search:
            params["search"] = search
        return self._request("GET", "/api/v1/agents", tenant_id, auth_token=auth_token, params=params)

    def get_agent(self, tenant_id: str, agent_id: str, auth_token: Optional[str] = None) -> dict:
        """GET /api/v1/agents/:id"""
        return self._request("GET", f"/api/v1/agents/{agent_id}", tenant_id, auth_token=auth_token)

    def create_agent(self, tenant_id: str, payload: dict) -> dict:
        """POST /api/v1/agents"""
        return self._request("POST", "/api/v1/agents", tenant_id, json=payload)

    def update_agent(self, tenant_id: str, agent_id: str, payload: dict) -> dict:
        """PUT /api/v1/agents/:id"""
        return self._request("PUT", f"/api/v1/agents/{agent_id}", tenant_id, json=payload)

    def delete_agent(self, tenant_id: str, agent_id: str) -> dict:
        """DELETE /api/v1/agents/:id"""
        return self._request("DELETE", f"/api/v1/agents/{agent_id}", tenant_id)

    def sync_agent(self, tenant_id: str, agent_id: str) -> dict:
        """POST /api/v1/agents/:id/sync — re-push config to provider."""
        return self._request("POST", f"/api/v1/agents/{agent_id}/sync", tenant_id)

    def import_agent_from_omnidim(self, tenant_id: str, omnidim_agent_id: str) -> dict:
        """POST /api/v1/agents/import/omnidim — import a single agent by provider ID."""
        return self._request(
            "POST", "/api/v1/agents/import/omnidim", tenant_id,
            json={"agentId": str(omnidim_agent_id)},
        )

    def import_all_agents_from_omnidim(self, tenant_id: str) -> dict:
        """POST /api/v1/agents/import/omnidim/all — bulk import all agents."""
        return self._request("POST", "/api/v1/agents/import/omnidim/all", tenant_id)

    def list_remote_omnidim_agents(self, tenant_id: str) -> list:
        """GET /api/v1/agents/remote/omnidim — fetch agents directly from Omnidim."""
        return self._request("GET", "/api/v1/agents/remote/omnidim", tenant_id)

    # ------------------------------------------------------------------ #
    # CALLS
    # ------------------------------------------------------------------ #

    def start_call(
        self,
        tenant_id: str,
        agent_id: str,
        phone: str,
        call_context: Optional[dict] = None,
        metadata: Optional[dict] = None,
        from_number_id: Optional[str] = None,
    ) -> dict:
        """
        POST /api/v1/calls/start
        Returns: { id, status: "QUEUED", agentId, phone, provider, createdAt }
        """
        payload: dict = {
            "agentId": str(agent_id),
            "phone": phone,
        }
        if from_number_id:
            payload["fromNumberId"] = str(from_number_id)
        if call_context:
            payload["callContext"] = call_context
        if metadata:
            payload["metadata"] = metadata
        return self._request("POST", "/api/v1/calls/start", tenant_id, json=payload)

    def end_call(self, tenant_id: str, call_id: str) -> dict:
        """POST /api/v1/calls/:id/end"""
        return self._request("POST", f"/api/v1/calls/{call_id}/end", tenant_id)

    def get_call(self, tenant_id: str, call_id: str) -> dict:
        """GET /api/v1/calls/:id — full call object with transcript, sentiment, tools."""
        return self._request("GET", f"/api/v1/calls/{call_id}", tenant_id)

    def list_calls(
        self,
        tenant_id: str,
        agent_id: Optional[str] = None,
        status: Optional[str] = None,
        page: int = 1,
        limit: int = 20,
        date_from: Optional[str] = None,
        date_to: Optional[str] = None,
    ) -> dict:
        """GET /api/v1/calls"""
        params: dict = {"page": page, "limit": limit}
        if agent_id:
            params["agentId"] = str(agent_id)
        if status:
            params["status"] = status
        if date_from:
            params["dateFrom"] = date_from
        if date_to:
            params["dateTo"] = date_to
        return self._request("GET", "/api/v1/calls", tenant_id, params=params)

    def get_remote_call_logs(
        self,
        tenant_id: str,
        agent_id: Optional[str] = None,
        page: int = 1,
        page_size: int = 20,
        call_status: Optional[str] = None,
    ) -> dict:
        """GET /api/v1/calls/logs/remote — call logs from Omnidim directly."""
        params: dict = {"page": page, "pageSize": page_size}
        if agent_id:
            params["agentId"] = str(agent_id)
        if call_status:
            params["call_status"] = call_status
        return self._request("GET", "/api/v1/calls/logs/remote", tenant_id, params=params)

    # ------------------------------------------------------------------ #
    # DASHBOARD
    # ------------------------------------------------------------------ #

    def get_dashboard_stats(self, tenant_id: str) -> dict:
        """GET /api/v1/dashboard/stats"""
        return self._request("GET", "/api/v1/dashboard/stats", tenant_id)


# Singleton-style factory
def get_voice_ai_client() -> VoiceAIClient:
    """Return a configured VoiceAIClient instance."""
    return VoiceAIClient()
