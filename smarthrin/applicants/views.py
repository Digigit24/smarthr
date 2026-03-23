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
from rest_framework.decorators import action, api_view, authentication_classes, permission_classes
from rest_framework.request import Request
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


# ------------------------------------------------------------------
# Standalone export view (explicit path avoids DefaultRouter issues)
# ------------------------------------------------------------------

@extend_schema(
    tags=["Applicants"],
    summary="Export applicants",
    description=(
        "Export filtered applicants as CSV or Excel. "
        "Supports the same query params as the list endpoint (source, email, skills, etc.). "
        "Use `export_format=xlsx` for Excel or `export_format=csv` (default) for CSV."
    ),
    parameters=[
        OpenApiParameter("export_format", OpenApiTypes.STR, enum=["csv", "xlsx"], description="Export format (default: csv)"),
        OpenApiParameter("source", OpenApiTypes.STR, description="Filter by source"),
        OpenApiParameter("search", OpenApiTypes.STR, description="Search in name/email"),
        OpenApiParameter("experience_years_gte", OpenApiTypes.NUMBER, description="Min experience years"),
        OpenApiParameter("experience_years_lte", OpenApiTypes.NUMBER, description="Max experience years"),
        OpenApiParameter("skills", OpenApiTypes.STR, description="Filter by skill"),
    ],
    responses={200: None},
)
@api_view(["GET"])
@authentication_classes([JWTRequestAuthentication])
@permission_classes([require_permission("smarthrin.applicants.view")])
def export_applicants(request: Request):
    """Export filtered applicants to CSV or Excel."""
    import datetime
    import json
    from common.export import build_csv_response, build_excel_response

    qs = Applicant.objects.filter(tenant_id=request.tenant_id)

    # Honour permission_scope set by HasSmartHRPermission
    scope = getattr(request, "permission_scope", None)
    if scope == "own":
        qs = qs.filter(owner_user_id=request.user_id)

    filterset = ApplicantFilterSet(request.query_params, queryset=qs, request=request)
    if not filterset.is_valid():
        from rest_framework.exceptions import ValidationError
        raise ValidationError(filterset.errors)
    qs = filterset.qs

    export_format = request.query_params.get("export_format", "csv").lower()

    columns = [
        ("first_name", "First Name"),
        ("last_name", "Last Name"),
        ("email", "Email"),
        ("phone", "Phone"),
        ("source", "Source"),
        ("experience_years", "Experience (Years)"),
        ("current_company", "Current Company"),
        ("current_role", "Current Role"),
        ("skills", "Skills"),
        ("tags", "Tags"),
        ("linkedin_url", "LinkedIn URL"),
        ("portfolio_url", "Portfolio URL"),
        ("notes", "Notes"),
        ("created_at", "Created At"),
    ]

    rows = []
    for applicant in qs.iterator():
        rows.append({
            "first_name": applicant.first_name,
            "last_name": applicant.last_name,
            "email": applicant.email,
            "phone": applicant.phone,
            "source": applicant.source,
            "experience_years": str(applicant.experience_years) if applicant.experience_years is not None else "",
            "current_company": applicant.current_company,
            "current_role": applicant.current_role,
            "skills": ", ".join(applicant.skills or []),
            "tags": ", ".join(applicant.tags or []),
            "linkedin_url": applicant.linkedin_url,
            "portfolio_url": applicant.portfolio_url,
            "notes": applicant.notes,
            "created_at": applicant.created_at,
        })

    timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")

    if export_format == "xlsx":
        return build_excel_response(
            rows=rows,
            columns=columns,
            filename=f"applicants_{timestamp}.xlsx",
            sheet_name="Applicants",
        )
    return build_csv_response(
        rows=rows,
        columns=columns,
        filename=f"applicants_{timestamp}.csv",
    )


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
