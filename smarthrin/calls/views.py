"""Views for CallRecord and Scorecard resources."""
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.viewsets import ReadOnlyModelViewSet

from common.authentication import JWTRequestAuthentication
from common.mixins import TenantViewSetMixin
from common.pagination import StandardResultsPagination
from common.permissions import require_permission

from .filters import CallRecordFilterSet, ScorecardFilterSet
from .models import CallRecord, Scorecard
from .serializers import (
    CallRecordDetailSerializer,
    CallRecordListSerializer,
    ScorecardListSerializer,
    ScorecardSerializer,
)


class CallRecordViewSet(TenantViewSetMixin, ReadOnlyModelViewSet):
    """Read-only viewset for CallRecord — list + retrieve + transcript action."""

    queryset = CallRecord.objects.select_related("application").prefetch_related("scorecard").all()
    authentication_classes = [JWTRequestAuthentication]
    pagination_class = StandardResultsPagination
    filterset_class = CallRecordFilterSet
    ordering_fields = ["created_at", "started_at"]

    def get_permissions(self):
        return [require_permission("smarthrin.calls.view")()]

    def get_serializer_class(self):
        if self.action == "retrieve" or self.action == "transcript":
            return CallRecordDetailSerializer
        return CallRecordListSerializer

    @action(detail=True, methods=["get"], url_path="transcript")
    def transcript(self, request, pk=None):
        """Return only the transcript field for a call record."""
        call = self.get_object()
        return Response({"transcript": call.transcript})


class ScorecardViewSet(TenantViewSetMixin, ReadOnlyModelViewSet):
    """Read-only viewset for Scorecard — list + retrieve."""

    queryset = Scorecard.objects.select_related("application", "call_record").all()
    authentication_classes = [JWTRequestAuthentication]
    pagination_class = StandardResultsPagination
    filterset_class = ScorecardFilterSet
    ordering_fields = ["created_at", "overall_score"]

    def get_permissions(self):
        return [require_permission("smarthrin.calls.view")()]

    def get_serializer_class(self):
        if self.action == "list":
            return ScorecardListSerializer
        return ScorecardSerializer
