"""Views for Applicant resource."""
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.viewsets import ModelViewSet

from activities.models import Activity
from activities.services import log_activity_for_request
from common.authentication import JWTRequestAuthentication
from common.mixins import TenantViewSetMixin
from common.pagination import StandardResultsPagination
from common.permissions import require_permission

from .filters import ApplicantFilterSet
from .models import Applicant
from .serializers import ApplicantDetailSerializer, ApplicantListSerializer


class ApplicantViewSet(TenantViewSetMixin, ModelViewSet):
    """CRUD + extra actions for Applicant."""

    queryset = Applicant.objects.all()
    authentication_classes = [JWTRequestAuthentication]
    pagination_class = StandardResultsPagination
    filterset_class = ApplicantFilterSet
    search_fields = ["first_name", "last_name", "email"]
    ordering_fields = ["created_at", "updated_at", "first_name", "last_name"]

    def get_permissions(self):
        action_permission_map = {
            "list": require_permission("smarthrin.applicants.view"),
            "retrieve": require_permission("smarthrin.applicants.view"),
            "create": require_permission("smarthrin.applicants.create"),
            "update": require_permission("smarthrin.applicants.edit"),
            "partial_update": require_permission("smarthrin.applicants.edit"),
            "destroy": require_permission("smarthrin.applicants.delete"),
            "applications": require_permission("smarthrin.applications.view"),
        }
        perm_class = action_permission_map.get(
            self.action, require_permission("smarthrin.applicants.view")
        )
        return [perm_class()]

    def get_serializer_class(self):
        if self.action == "list":
            return ApplicantListSerializer
        return ApplicantDetailSerializer

    def perform_create(self, serializer):
        super().perform_create(serializer)
        log_activity_for_request(
            self.request,
            verb=Activity.Verb.CREATED,
            resource=serializer.instance,
            metadata={"email": serializer.instance.email},
        )

    def perform_update(self, serializer):
        super().perform_update(serializer)
        log_activity_for_request(
            self.request,
            verb=Activity.Verb.UPDATED,
            resource=serializer.instance,
            metadata={"email": serializer.instance.email},
        )

    # ------------------------------------------------------------------
    # Extra actions
    # ------------------------------------------------------------------

    @action(detail=True, methods=["get"], url_path="applications", url_name="applications")
    def applications(self, request, pk=None):
        """Return paginated applications for this applicant (tenant-filtered)."""
        from applications.models import Application
        from applications.serializers import ApplicationListSerializer

        applicant = self.get_object()
        qs = (
            Application.objects.filter(applicant=applicant, tenant_id=request.tenant_id)
            .select_related("applicant", "job")
            .order_by("-created_at")
        )

        page = self.paginate_queryset(qs)
        if page is not None:
            serializer = ApplicationListSerializer(
                page, many=True, context={"request": request}
            )
            return self.get_paginated_response(serializer.data)

        serializer = ApplicationListSerializer(
            qs, many=True, context={"request": request}
        )
        return Response(serializer.data)
