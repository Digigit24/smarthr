"""Proxy views for CeliyoVoice agent management."""
import logging

from drf_spectacular.utils import extend_schema, OpenApiParameter
from drf_spectacular.types import OpenApiTypes
from rest_framework.response import Response
from rest_framework.views import APIView

from common.authentication import JWTRequestAuthentication
from common.permissions import require_permission
from integrations.exceptions import VoiceAIError
from integrations.voice_ai import VoiceAIClient

from .serializers import AvailableAgentSerializer

logger = logging.getLogger(__name__)


def _extract_auth_token(request) -> str:
    """Extract raw JWT token from the Authorization header."""
    auth_header = request.META.get("HTTP_AUTHORIZATION", "")
    if auth_header.startswith("Bearer "):
        return auth_header[7:]
    return ""


class VoiceAgentListView(APIView):
    """
    GET /api/v1/voice-agents/
    Read-only proxy to CeliyoVoice GET /api/v1/agents.
    Passes the user's JWT to the orchestrator so the same JWT secret is used.
    """

    authentication_classes = [JWTRequestAuthentication]

    def get_permissions(self):
        return [require_permission("smarthrin.calls.view")()]

    @extend_schema(
        tags=["Voice Agents"],
        summary="List voice agents",
        description=(
            "Proxies to CeliyoVoice to list available voice agents for the tenant. "
            "Uses the caller's JWT token for authentication since both services share the same JWT secret."
        ),
        parameters=[
            OpenApiParameter("page", OpenApiTypes.INT, description="Page number"),
            OpenApiParameter("limit", OpenApiTypes.INT, description="Items per page (default 20)"),
            OpenApiParameter("provider", OpenApiTypes.STR, description="Filter by provider"),
            OpenApiParameter("is_active", OpenApiTypes.BOOL, description="Filter by active status"),
            OpenApiParameter("search", OpenApiTypes.STR, description="Search by agent name"),
        ],
        responses={200: AvailableAgentSerializer(many=True)},
    )
    def get(self, request):
        auth_token = _extract_auth_token(request)
        client = VoiceAIClient()

        try:
            data = client.list_agents(
                tenant_id=str(request.tenant_id),
                page=int(request.query_params.get("page", 1)),
                limit=int(request.query_params.get("limit", 20)),
                provider=request.query_params.get("provider"),
                is_active=(
                    request.query_params.get("is_active", "").lower() == "true"
                    if "is_active" in request.query_params
                    else None
                ),
                search=request.query_params.get("search"),
                auth_token=auth_token or None,
            )
        except VoiceAIError as exc:
            logger.error(f"VoiceAI error listing agents: {exc}")
            status_code = getattr(exc, "status_code", 502)
            exc_code = getattr(exc, "code", "VOICE_SERVICE_UNAVAILABLE")
            return Response(
                {"detail": exc.message, "code": exc_code},
                status=status_code,
            )

        # Normalize response — orchestrator may return { items: [...] } or a list
        if isinstance(data, dict):
            agents = data.get("items", data.get("agents", data.get("data", [])))
        elif isinstance(data, list):
            agents = data
        else:
            agents = []

        serializer = AvailableAgentSerializer(agents, many=True)
        return Response(serializer.data)


class VoiceAgentDetailView(APIView):
    """
    GET /api/v1/voice-agents/{id}/
    Read-only proxy to CeliyoVoice GET /api/v1/agents/:id.
    """

    authentication_classes = [JWTRequestAuthentication]

    def get_permissions(self):
        return [require_permission("smarthrin.calls.view")()]

    @extend_schema(
        tags=["Voice Agents"],
        summary="Get voice agent details",
        description="Proxies to CeliyoVoice to retrieve a specific voice agent by ID.",
        responses={200: AvailableAgentSerializer},
    )
    def get(self, request, agent_id: str):
        auth_token = _extract_auth_token(request)
        client = VoiceAIClient()

        try:
            agent = client.get_agent(
                tenant_id=str(request.tenant_id),
                agent_id=agent_id,
                auth_token=auth_token or None,
            )
        except VoiceAIError as exc:
            logger.error(f"VoiceAI error getting agent {agent_id}: {exc}")
            status_code = getattr(exc, "status_code", 502)
            exc_code = getattr(exc, "code", "VOICE_SERVICE_UNAVAILABLE")
            return Response(
                {"detail": exc.message, "code": exc_code},
                status=status_code,
            )

        serializer = AvailableAgentSerializer(agent)
        return Response(serializer.data)
