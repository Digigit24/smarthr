"""Views for Applicant resource."""
from drf_spectacular.utils import (
    OpenApiExample,
    OpenApiParameter,
    OpenApiResponse,
    extend_schema,
    extend_schema_view,
    inline_serializer,
)
from drf_spectacular.types import OpenApiTypes
from rest_framework import serializers
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
from .serializers import ApplicantCreateSerializer, ApplicantDetailSerializer, ApplicantListSerializer


@extend_schema_view(
    list=extend_schema(
        tags=["Applicants"],
        summary="List applicants",
        description="Returns paginated list of applicants for the current tenant.",
        parameters=[
            OpenApiParameter("source", OpenApiTypes.STR, enum=["MANUAL", "WEBSITE", "LINKEDIN", "REFERRAL", "IMPORT"],
                description="Filter by source"),
            OpenApiParameter("search", OpenApiTypes.STR, description="Search in first_name, last_name, email"),
        ],
        responses={200: ApplicantListSerializer(many=True)},
    ),
    create=extend_schema(
        tags=["Applicants"],
        summary="Create an applicant",
        request=ApplicantCreateSerializer,
        responses={201: ApplicantDetailSerializer},
        examples=[
            OpenApiExample(
                "New applicant",
                value={
                    "first_name": "Alice", "last_name": "Johnson",
                    "email": "alice@example.com", "phone": "+14155550001",
                    "skills": ["Python", "Django"], "experience_years": 5,
                    "source": "LINKEDIN",
                },
            ),
        ],
    ),
    retrieve=extend_schema(
        tags=["Applicants"],
        summary="Get applicant details",
        responses={200: ApplicantDetailSerializer},
    ),
    update=extend_schema(
        tags=["Applicants"],
        summary="Update an applicant",
        request=ApplicantCreateSerializer,
        responses={200: ApplicantDetailSerializer},
    ),
    partial_update=extend_schema(
        tags=["Applicants"],
        summary="Partial update an applicant",
        request=ApplicantCreateSerializer,
        responses={200: ApplicantDetailSerializer},
    ),
    destroy=extend_schema(
        tags=["Applicants"],
        summary="Delete an applicant",
        responses={204: None},
    ),
)
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
        if self.action in ("create", "update", "partial_update"):
            return ApplicantCreateSerializer
        return ApplicantDetailSerializer

    def perform_create(self, serializer):
        instance = serializer.save(
            tenant_id=self.request.tenant_id,
            owner_user_id=self.request.user_id,
        )
        log_activity_for_request(
            self.request,
            verb=Activity.Verb.CREATED,
            resource=instance,
            after={"email": instance.email},
        )

    def perform_update(self, serializer):
        instance = serializer.save(tenant_id=self.request.tenant_id)
        log_activity_for_request(
            self.request,
            verb=Activity.Verb.UPDATED,
            resource=instance,
        )

    @extend_schema(
        tags=["Applicants"],
        summary="List applicant's applications",
        description="Returns all job applications made by this applicant for the current tenant.",
        responses={200: inline_serializer("ApplicantApplicationsList", fields={
            "id": serializers.UUIDField(),
            "job_title": serializers.CharField(),
            "status": serializers.CharField(),
            "score": serializers.DecimalField(max_digits=5, decimal_places=2, allow_null=True),
            "created_at": serializers.DateTimeField(),
        }, many=True)},
    )
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
