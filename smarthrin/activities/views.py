from drf_spectacular.utils import extend_schema, extend_schema_view, OpenApiParameter
from drf_spectacular.types import OpenApiTypes
from rest_framework import mixins
from rest_framework.viewsets import GenericViewSet
from rest_framework.filters import OrderingFilter, SearchFilter
from django_filters.rest_framework import DjangoFilterBackend
import django_filters

from common.authentication import JWTRequestAuthentication
from common.mixins import TenantViewSetMixin
from common.pagination import StandardResultsPagination
from common.permissions import require_permission

from .models import Activity
from .serializers import ActivitySerializer


class ActivityFilterSet(django_filters.FilterSet):
    verb = django_filters.CharFilter(lookup_expr="exact")
    resource_type = django_filters.CharFilter(lookup_expr="exact")
    resource_id = django_filters.UUIDFilter(lookup_expr="exact")
    actor_user_id = django_filters.UUIDFilter(lookup_expr="exact")
    created_after = django_filters.DateFilter(field_name="created_at", lookup_expr="date")
    created_at_gte = django_filters.DateTimeFilter(field_name="created_at", lookup_expr="gte")
    created_at_lte = django_filters.DateTimeFilter(field_name="created_at", lookup_expr="lte")

    class Meta:
        model = Activity
        fields = ["verb", "resource_type", "resource_id", "actor_user_id"]


@extend_schema_view(
    list=extend_schema(
        tags=["Activities"],
        summary="List activity feed",
        description="Returns paginated audit activity log for the current tenant. Filterable by resource, verb, and actor.",
        parameters=[
            OpenApiParameter("verb", OpenApiTypes.STR, description="Filter by activity verb (e.g. CREATED, STATUS_CHANGED)"),
            OpenApiParameter("resource_type", OpenApiTypes.STR, description="Filter by resource type (e.g. Job, Application)"),
            OpenApiParameter("resource_id", OpenApiTypes.UUID, description="Filter by specific resource ID"),
            OpenApiParameter("actor_user_id", OpenApiTypes.UUID, description="Filter by actor user ID"),
            OpenApiParameter("created_after", OpenApiTypes.DATE, description="Filter: return activities from this exact date (YYYY-MM-DD)"),
            OpenApiParameter("created_at_gte", OpenApiTypes.DATETIME, description="Filter: created at or after this datetime"),
            OpenApiParameter("created_at_lte", OpenApiTypes.DATETIME, description="Filter: created at or before this datetime"),
        ],
        responses={200: ActivitySerializer(many=True)},
    ),
    retrieve=extend_schema(
        tags=["Activities"],
        summary="Get activity entry",
        responses={200: ActivitySerializer},
    ),
)
class ActivityViewSet(TenantViewSetMixin, mixins.ListModelMixin, mixins.RetrieveModelMixin, GenericViewSet):
    """
    Read-only activity feed. Filterable by resource_type, resource_id, verb, actor.
    Permission: smarthrin.activities.view (or just authenticated for self).
    """
    serializer_class = ActivitySerializer
    authentication_classes = [JWTRequestAuthentication]
    pagination_class = StandardResultsPagination
    filter_backends = [DjangoFilterBackend, OrderingFilter, SearchFilter]
    filterset_class = ActivityFilterSet
    search_fields = ["verb", "resource_type", "resource_label", "actor_email"]
    ordering_fields = ["created_at"]
    ordering = ["-created_at"]

    def get_queryset(self):
        return Activity.objects.filter(tenant_id=self.request.tenant_id)
