from rest_framework import mixins
from rest_framework.viewsets import GenericViewSet
from rest_framework.filters import OrderingFilter
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
    created_at_gte = django_filters.DateTimeFilter(field_name="created_at", lookup_expr="gte")
    created_at_lte = django_filters.DateTimeFilter(field_name="created_at", lookup_expr="lte")

    class Meta:
        model = Activity
        fields = ["verb", "resource_type", "resource_id", "actor_user_id"]


class ActivityViewSet(TenantViewSetMixin, mixins.ListModelMixin, mixins.RetrieveModelMixin, GenericViewSet):
    """
    Read-only activity feed. Filterable by resource_type, resource_id, verb, actor.
    Permission: smarthrin.activities.view (or just authenticated for self).
    """
    serializer_class = ActivitySerializer
    authentication_classes = [JWTRequestAuthentication]
    pagination_class = StandardResultsPagination
    filter_backends = [DjangoFilterBackend, OrderingFilter]
    filterset_class = ActivityFilterSet
    ordering_fields = ["created_at"]
    ordering = ["-created_at"]

    def get_queryset(self):
        return Activity.objects.filter(tenant_id=self.request.tenant_id)
