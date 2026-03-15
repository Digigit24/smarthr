from rest_framework.decorators import api_view, authentication_classes, permission_classes
from rest_framework.response import Response
from rest_framework.request import Request
from common.authentication import JWTRequestAuthentication
from common.permissions import require_permission
from .services import get_dashboard_metrics, get_funnel_data, get_score_distribution, get_timeline_data

@api_view(["GET"])
@authentication_classes([JWTRequestAuthentication])
@permission_classes([require_permission("smarthrin.analytics.view")])
def dashboard(request: Request) -> Response:
    data = get_dashboard_metrics(str(request.tenant_id))
    return Response(data)

@api_view(["GET"])
@authentication_classes([JWTRequestAuthentication])
@permission_classes([require_permission("smarthrin.analytics.view")])
def funnel(request: Request) -> Response:
    data = get_funnel_data(str(request.tenant_id))
    return Response(data)

@api_view(["GET"])
@authentication_classes([JWTRequestAuthentication])
@permission_classes([require_permission("smarthrin.analytics.view")])
def scores(request: Request) -> Response:
    data = get_score_distribution(str(request.tenant_id))
    return Response(data)

@api_view(["GET"])
@authentication_classes([JWTRequestAuthentication])
@permission_classes([require_permission("smarthrin.analytics.view")])
def timeline(request: Request) -> Response:
    period = request.query_params.get("period", "30d")
    data = get_timeline_data(str(request.tenant_id), period)
    return Response(data)
