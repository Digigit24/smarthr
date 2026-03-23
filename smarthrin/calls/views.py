"""Views for CallRecord and Scorecard resources."""
from drf_spectacular.utils import extend_schema, extend_schema_view, OpenApiParameter, inline_serializer
from drf_spectacular.types import OpenApiTypes
from rest_framework import serializers as drf_serializers, status
from rest_framework.decorators import action, api_view, authentication_classes, permission_classes
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework.viewsets import ReadOnlyModelViewSet

from common.authentication import JWTRequestAuthentication
from common.mixins import TenantViewSetMixin
from common.pagination import StandardResultsPagination
from common.permissions import require_permission

from .agent_cache import get_cached_agents, set_cached_agents
from .filters import CallRecordFilterSet, ScorecardFilterSet
from .models import CallRecord, Scorecard
from .serializers import (
    AvailableAgentSerializer,
    CallRecordDetailSerializer,
    CallRecordListSerializer,
    CallRecordUpdateStatusSerializer,
    ScorecardListSerializer,
    ScorecardSerializer,
)


# ------------------------------------------------------------------
# Standalone export view for scorecards
# ------------------------------------------------------------------

@extend_schema(
    tags=["Scorecards"],
    summary="Export scorecards",
    description=(
        "Export filtered scorecards as CSV or Excel. "
        "Supports the same query params as the list endpoint. "
        "Use `export_format=xlsx` for Excel or `export_format=csv` (default) for CSV."
    ),
    parameters=[
        OpenApiParameter("export_format", OpenApiTypes.STR, enum=["csv", "xlsx"], description="Export format (default: csv)"),
        OpenApiParameter("application", OpenApiTypes.UUID, description="Filter by application ID"),
        OpenApiParameter("recommendation", OpenApiTypes.STR, description="Filter by recommendation"),
        OpenApiParameter("overall_score_gte", OpenApiTypes.NUMBER, description="Minimum overall score"),
        OpenApiParameter("overall_score_lte", OpenApiTypes.NUMBER, description="Maximum overall score"),
    ],
    responses={200: None},
)
@api_view(["GET"])
@authentication_classes([JWTRequestAuthentication])
@permission_classes([require_permission("smarthrin.calls.view")])
def export_scorecards(request: Request):
    """Export filtered scorecards to CSV or Excel."""
    import datetime
    import json
    from common.export import build_csv_response, build_excel_response

    qs = Scorecard.objects.select_related(
        "application", "application__applicant", "application__job"
    ).filter(tenant_id=request.tenant_id)

    scope = getattr(request, "permission_scope", None)
    if scope == "own":
        qs = qs.filter(owner_user_id=request.user_id)

    filterset = ScorecardFilterSet(request.query_params, queryset=qs, request=request)
    if not filterset.is_valid():
        from rest_framework.exceptions import ValidationError
        raise ValidationError(filterset.errors)
    qs = filterset.qs

    export_format = request.query_params.get("export_format", "csv").lower()

    columns = [
        ("applicant_name", "Applicant Name"),
        ("applicant_email", "Applicant Email"),
        ("job_title", "Job Title"),
        ("overall_score", "Overall Score"),
        ("communication_score", "Communication"),
        ("knowledge_score", "Knowledge"),
        ("confidence_score", "Confidence"),
        ("relevance_score", "Relevance"),
        ("recommendation", "Recommendation"),
        ("summary", "Summary"),
        ("strengths", "Strengths"),
        ("weaknesses", "Weaknesses"),
        ("created_at", "Created At"),
    ]

    rows = []
    for sc in qs.iterator():
        applicant = sc.application.applicant if sc.application else None
        job = sc.application.job if sc.application else None
        rows.append({
            "applicant_name": f"{applicant.first_name} {applicant.last_name}" if applicant else "",
            "applicant_email": applicant.email if applicant else "",
            "job_title": job.title if job else "",
            "overall_score": str(sc.overall_score),
            "communication_score": str(sc.communication_score),
            "knowledge_score": str(sc.knowledge_score),
            "confidence_score": str(sc.confidence_score),
            "relevance_score": str(sc.relevance_score),
            "recommendation": sc.recommendation,
            "summary": sc.summary or "",
            "strengths": ", ".join(sc.strengths) if sc.strengths else "",
            "weaknesses": ", ".join(sc.weaknesses) if sc.weaknesses else "",
            "created_at": sc.created_at,
        })

    timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")

    if export_format == "xlsx":
        return build_excel_response(
            rows=rows,
            columns=columns,
            filename=f"scorecards_{timestamp}.xlsx",
            sheet_name="Scorecards",
        )
    return build_csv_response(
        rows=rows,
        columns=columns,
        filename=f"scorecards_{timestamp}.csv",
    )


@extend_schema_view(
    list=extend_schema(
        tags=["Calls"],
        summary="List call records",
        description="Returns paginated list of AI screening call records for the tenant.",
        parameters=[
            OpenApiParameter("status", OpenApiTypes.STR,
                enum=["QUEUED", "INITIATED", "RINGING", "IN_PROGRESS", "COMPLETED", "FAILED", "NO_ANSWER", "BUSY"],
                description="Filter by call status"),
            OpenApiParameter("application_id", OpenApiTypes.UUID, description="Filter by application ID"),
        ],
        responses={200: CallRecordListSerializer(many=True)},
    ),
    retrieve=extend_schema(
        tags=["Calls"],
        summary="Get call record details",
        description="Returns full call record including transcript, recording URL, and nested scorecard.",
        responses={200: CallRecordDetailSerializer},
    ),
)
class CallRecordViewSet(TenantViewSetMixin, ReadOnlyModelViewSet):
    """Read-only viewset for CallRecord — list + retrieve + transcript + retry actions."""

    queryset = CallRecord.objects.select_related("application").prefetch_related("scorecard", "queue_items__queue").all()
    authentication_classes = [JWTRequestAuthentication]
    pagination_class = StandardResultsPagination
    filterset_class = CallRecordFilterSet
    search_fields = ["phone", "summary", "provider_call_id", "application__applicant__first_name", "application__applicant__last_name", "application__applicant__email"]
    ordering_fields = ["created_at", "started_at"]

    def get_permissions(self):
        if self.action == "retry":
            return [require_permission("smarthrin.calls.create")()]
        if self.action == "update_status":
            return [require_permission("smarthrin.calls.create")()]
        return [require_permission("smarthrin.calls.view")()]

    def get_serializer_class(self):
        if self.action in ("retrieve", "transcript"):
            return CallRecordDetailSerializer
        return CallRecordListSerializer

    @extend_schema(
        tags=["Calls"],
        summary="Get call transcript",
        description="Returns only the transcript text for a specific call record.",
        responses={200: inline_serializer("TranscriptResponse", fields={
            "transcript": drf_serializers.CharField(),
        })},
    )
    @action(detail=True, methods=["get"], url_path="transcript")
    def transcript(self, request, pk=None):
        """Return only the transcript field for a call record."""
        call = self.get_object()
        return Response({"transcript": call.transcript})

    @extend_schema(
        tags=["Calls"],
        summary="Retry failed call",
        description="Re-triggers an AI screening call for a previously failed call record.",
        request=None,
        responses={200: CallRecordDetailSerializer},
    )
    @action(detail=True, methods=["post"], url_path="retry")
    def retry(self, request, pk=None):
        """Retry a failed AI screening call."""
        from .services import AIScreeningService
        call_record = self.get_object()
        if call_record.status != CallRecord.Status.FAILED:
            return Response(
                {"detail": "Only FAILED calls can be retried."},
                status=status.HTTP_400_BAD_REQUEST,
            )
        service = AIScreeningService()
        new_call = service.retry_failed_call(
            call_record_id=str(call_record.pk),
            tenant_id=str(request.tenant_id),
            owner_user_id=str(request.user_id),
        )
        serializer = CallRecordDetailSerializer(new_call, context={"request": request})
        return Response(serializer.data)

    @extend_schema(
        tags=["Calls"],
        summary="Update call record status",
        description="Update the status of a call record.",
        request=CallRecordUpdateStatusSerializer,
        responses={200: CallRecordDetailSerializer},
    )
    @action(detail=True, methods=["patch"], url_path="update-status", url_name="update-status")
    def update_status(self, request, pk=None):
        """Update the status of a call record."""
        call_record = self.get_object()
        serializer = CallRecordUpdateStatusSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        call_record.status = serializer.validated_data["status"]
        call_record.save(update_fields=["status", "updated_at"])
        return Response(CallRecordDetailSerializer(call_record, context={"request": request}).data)


@extend_schema_view(
    list=extend_schema(
        tags=["Scorecards"],
        summary="List scorecards",
        description="Returns paginated list of AI-generated scorecards for the tenant.",
        responses={200: ScorecardListSerializer(many=True)},
    ),
    retrieve=extend_schema(
        tags=["Scorecards"],
        summary="Get scorecard details",
        responses={200: ScorecardSerializer},
    ),
)
class ScorecardViewSet(TenantViewSetMixin, ReadOnlyModelViewSet):
    """Read-only viewset for Scorecard — list + retrieve."""

    queryset = Scorecard.objects.select_related("application", "call_record").all()
    authentication_classes = [JWTRequestAuthentication]
    pagination_class = StandardResultsPagination
    filterset_class = ScorecardFilterSet
    search_fields = ["summary", "recommendation", "application__applicant__first_name", "application__applicant__last_name", "application__applicant__email"]
    ordering_fields = ["created_at", "overall_score"]

    def get_permissions(self):
        return [require_permission("smarthrin.calls.view")()]

    def get_serializer_class(self):
        if self.action == "list":
            return ScorecardListSerializer
        return ScorecardSerializer


class AvailableVoiceAgentsView(APIView):
    """GET /api/calls/available-agents/ — list active voice agents from the Voice AI Orchestrator."""

    authentication_classes = [JWTRequestAuthentication]

    def get_permissions(self):
        return [require_permission("smarthrin.calls.view")()]

    @extend_schema(
        tags=["Calls"],
        summary="List available voice agents",
        description="Returns active voice agents from the Voice AI Orchestrator that can be assigned to jobs.",
        responses={200: AvailableAgentSerializer(many=True)},
    )
    def get(self, request):
        tenant_id = str(request.tenant_id)
        cache_params = dict(is_active=True)

        # Try cache first
        cached = get_cached_agents(tenant_id, **cache_params)
        if cached is not None:
            serializer = AvailableAgentSerializer(cached, many=True)
            return Response(serializer.data)

        from .services import AIScreeningService
        service = AIScreeningService()
        agents = service.list_available_agents(tenant_id)
        # agents is a list from voice_client.list_agents(is_active=True)
        # It may be a dict with items key or a list directly
        if isinstance(agents, dict):
            agents = agents.get("items", agents.get("agents", []))

        set_cached_agents(tenant_id, agents, **cache_params)

        serializer = AvailableAgentSerializer(agents, many=True)
        return Response(serializer.data)
