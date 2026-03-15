"""Analytics views — dashboard metrics, funnel, scores, timeline."""
from drf_spectacular.utils import extend_schema, OpenApiParameter, inline_serializer
from drf_spectacular.types import OpenApiTypes
from rest_framework import serializers as drf_serializers
from rest_framework.decorators import api_view, authentication_classes, permission_classes
from rest_framework.response import Response
from rest_framework.request import Request

from common.authentication import JWTRequestAuthentication
from common.permissions import require_permission

from .services import get_dashboard_metrics, get_funnel_data, get_score_distribution, get_timeline_data


@extend_schema(
    tags=["Analytics"],
    summary="Dashboard metrics",
    description="Returns high-level recruitment metrics for the current tenant.",
    responses={200: inline_serializer("DashboardMetrics", fields={
        "total_jobs_open": drf_serializers.IntegerField(),
        "total_applications": drf_serializers.IntegerField(),
        "total_calls_completed": drf_serializers.IntegerField(),
        "avg_candidate_score": drf_serializers.FloatField(allow_null=True),
        "applications_today": drf_serializers.IntegerField(),
        "calls_today": drf_serializers.IntegerField(),
        "shortlisted_count": drf_serializers.IntegerField(),
        "offers_count": drf_serializers.IntegerField(),
        "hiring_conversion_rate": drf_serializers.FloatField(),
    })},
)
@api_view(["GET"])
@authentication_classes([JWTRequestAuthentication])
@permission_classes([require_permission("smarthrin.analytics.view")])
def dashboard(request: Request) -> Response:
    data = get_dashboard_metrics(str(request.tenant_id))
    return Response(data)


@extend_schema(
    tags=["Analytics"],
    summary="Application funnel",
    description="Returns application counts grouped by status — shows the recruitment funnel.",
    responses={200: inline_serializer("FunnelItem", fields={
        "status": drf_serializers.CharField(),
        "count": drf_serializers.IntegerField(),
    }, many=True)},
)
@api_view(["GET"])
@authentication_classes([JWTRequestAuthentication])
@permission_classes([require_permission("smarthrin.analytics.view")])
def funnel(request: Request) -> Response:
    data = get_funnel_data(str(request.tenant_id))
    return Response(data)


@extend_schema(
    tags=["Analytics"],
    summary="Score distribution",
    description="Returns candidate score distribution in 10-point buckets (0-10, 10-20, ..., 90-100).",
    responses={200: inline_serializer("ScoreBucket", fields={
        "range": drf_serializers.CharField(),
        "count": drf_serializers.IntegerField(),
    }, many=True)},
)
@api_view(["GET"])
@authentication_classes([JWTRequestAuthentication])
@permission_classes([require_permission("smarthrin.analytics.view")])
def scores(request: Request) -> Response:
    data = get_score_distribution(str(request.tenant_id))
    return Response(data)


@extend_schema(
    tags=["Analytics"],
    summary="Activity timeline",
    description="Returns daily counts of applications, completed calls, and hires over a time period.",
    parameters=[
        OpenApiParameter("period", OpenApiTypes.STR, enum=["7d", "30d", "90d"],
            description="Time period to include (default: 30d)"),
    ],
    responses={200: inline_serializer("TimelinePoint", fields={
        "date": drf_serializers.DateField(),
        "applications": drf_serializers.IntegerField(),
        "calls": drf_serializers.IntegerField(),
        "hires": drf_serializers.IntegerField(),
    }, many=True)},
)
@api_view(["GET"])
@authentication_classes([JWTRequestAuthentication])
@permission_classes([require_permission("smarthrin.analytics.view")])
def timeline(request: Request) -> Response:
    period = request.query_params.get("period", "30d")
    data = get_timeline_data(str(request.tenant_id), period)
    return Response(data)
