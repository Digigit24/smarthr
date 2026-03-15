"""Views for Job resource."""
from django.db.models import Avg, Count
from django.utils import timezone
from drf_spectacular.utils import (
    OpenApiExample,
    OpenApiParameter,
    OpenApiResponse,
    extend_schema,
    extend_schema_view,
    inline_serializer,
)
from drf_spectacular.types import OpenApiTypes
from rest_framework import serializers, status
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.viewsets import ModelViewSet

from activities.models import Activity
from activities.services import log_activity_for_request
from common.authentication import JWTRequestAuthentication
from common.mixins import TenantViewSetMixin
from common.pagination import StandardResultsPagination
from common.permissions import require_permission

from .filters import JobFilterSet
from .models import Job
from .serializers import JobCreateSerializer, JobDetailSerializer, JobListSerializer, JobVoiceConfigSerializer


@extend_schema_view(
    list=extend_schema(
        tags=["Jobs"],
        summary="List jobs",
        description="Returns paginated list of jobs for the current tenant.",
        parameters=[
            OpenApiParameter("status", OpenApiTypes.STR, enum=["DRAFT", "OPEN", "PAUSED", "CLOSED"],
                description="Filter by job status"),
            OpenApiParameter("department", OpenApiTypes.STR, description="Filter by department (contains)"),
            OpenApiParameter("location", OpenApiTypes.STR, description="Filter by location (contains)"),
            OpenApiParameter("search", OpenApiTypes.STR, description="Search in title, department, location"),
        ],
        responses={200: JobListSerializer(many=True)},
    ),
    create=extend_schema(
        tags=["Jobs"],
        summary="Create a job",
        description="Creates a new job posting. tenant_id and owner_user_id are injected from JWT.",
        request=JobCreateSerializer,
        responses={201: JobDetailSerializer},
        examples=[
            OpenApiExample(
                "Senior Python Developer",
                value={
                    "title": "Senior Python Developer",
                    "department": "Engineering",
                    "location": "Remote",
                    "job_type": "FULL_TIME",
                    "experience_level": "SENIOR",
                    "description": "We are looking for an experienced Python developer.",
                    "requirements": "5+ years Python, Django, PostgreSQL",
                    "voice_agent_id": "agent-uuid",
                },
            ),
        ],
    ),
    retrieve=extend_schema(
        tags=["Jobs"],
        summary="Get job details",
        responses={200: JobDetailSerializer},
    ),
    update=extend_schema(
        tags=["Jobs"],
        summary="Update a job",
        request=JobCreateSerializer,
        responses={200: JobDetailSerializer},
    ),
    partial_update=extend_schema(
        tags=["Jobs"],
        summary="Partial update a job",
        request=JobCreateSerializer,
        responses={200: JobDetailSerializer},
    ),
    destroy=extend_schema(
        tags=["Jobs"],
        summary="Delete a job",
        responses={204: None},
    ),
)
class JobViewSet(TenantViewSetMixin, ModelViewSet):
    """CRUD + extra actions for Job."""

    queryset = Job.objects.all()
    authentication_classes = [JWTRequestAuthentication]
    pagination_class = StandardResultsPagination
    filterset_class = JobFilterSet
    search_fields = ["title", "department", "location"]
    ordering_fields = ["created_at", "updated_at", "title", "application_count", "published_at"]

    def get_permissions(self):
        action_permission_map = {
            "list": require_permission("smarthrin.jobs.view"),
            "retrieve": require_permission("smarthrin.jobs.view"),
            "create": require_permission("smarthrin.jobs.create"),
            "update": require_permission("smarthrin.jobs.edit"),
            "partial_update": require_permission("smarthrin.jobs.edit"),
            "destroy": require_permission("smarthrin.jobs.delete"),
            "publish": require_permission("smarthrin.jobs.edit"),
            "close": require_permission("smarthrin.jobs.edit"),
            "applications": require_permission("smarthrin.applications.view"),
            "stats": require_permission("smarthrin.jobs.view"),
            "voice_config": require_permission("smarthrin.jobs.edit"),
        }
        perm_class = action_permission_map.get(
            self.action, require_permission("smarthrin.jobs.view")
        )
        return [perm_class()]

    def get_serializer_class(self):
        if self.action == "list":
            return JobListSerializer
        if self.action in ("create", "update", "partial_update"):
            return JobCreateSerializer
        return JobDetailSerializer

    @extend_schema(
        tags=["Jobs"],
        summary="Publish a job",
        description="Sets job status to OPEN and records published_at timestamp.",
        request=None,
        responses={200: JobDetailSerializer},
    )
    @action(detail=True, methods=["post"], url_path="publish")
    def publish(self, request, pk=None):
        """Set job status to OPEN and record published_at timestamp."""
        job = self.get_object()
        before = {"status": job.status}
        job.status = Job.Status.OPEN
        if not job.published_at:
            job.published_at = timezone.now()
        job.save(update_fields=["status", "published_at", "updated_at"])
        log_activity_for_request(
            request,
            verb=Activity.Verb.PUBLISHED,
            resource=job,
            before=before,
            after={"status": job.status},
        )
        return Response(JobDetailSerializer(job).data)

    @extend_schema(
        tags=["Jobs"],
        summary="Close a job",
        description="Sets job status to CLOSED.",
        request=None,
        responses={200: JobDetailSerializer},
    )
    @action(detail=True, methods=["post"], url_path="close")
    def close(self, request, pk=None):
        """Set job status to CLOSED."""
        job = self.get_object()
        before = {"status": job.status}
        job.status = Job.Status.CLOSED
        job.save(update_fields=["status", "updated_at"])
        log_activity_for_request(
            request,
            verb=Activity.Verb.CLOSED,
            resource=job,
            before=before,
            after={"status": job.status},
        )
        return Response(JobDetailSerializer(job).data)

    @extend_schema(
        tags=["Jobs"],
        summary="List job applications",
        description="Returns paginated list of applications for this job.",
        responses={200: inline_serializer("JobApplicationsList", fields={
            "id": serializers.UUIDField(),
            "applicant_name": serializers.CharField(),
            "status": serializers.CharField(),
            "score": serializers.DecimalField(max_digits=5, decimal_places=2, allow_null=True),
            "created_at": serializers.DateTimeField(),
        }, many=True)},
    )
    @action(detail=True, methods=["get"], url_path="applications", url_name="applications")
    def applications(self, request, pk=None):
        """Return a paginated list of applications for this job."""
        from applications.models import Application
        from applications.serializers import ApplicationListSerializer

        job = self.get_object()
        qs = (
            Application.objects.filter(job=job, tenant_id=request.tenant_id)
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

    @extend_schema(
        tags=["Jobs"],
        summary="Get job statistics",
        description="Returns application count by status, average score, and total applications.",
        responses={200: inline_serializer("JobStats", fields={
            "total_applications": serializers.IntegerField(),
            "avg_score": serializers.FloatField(allow_null=True),
            "by_status": serializers.DictField(child=serializers.IntegerField()),
        })},
    )
    @action(detail=False, methods=["get"], url_path="stats")
    def stats(self, request):
        """Return aggregate application statistics across all jobs for this tenant."""
        from applications.models import Application

        tenant_id = request.tenant_id

        status_counts = dict(
            Application.objects.filter(tenant_id=tenant_id)
            .values("status")
            .annotate(count=Count("id"))
            .values_list("status", "count")
        )

        aggregates = Application.objects.filter(tenant_id=tenant_id).aggregate(
            avg_score=Avg("score"),
            total=Count("id"),
        )

        return Response(
            {
                "by_status": status_counts,
                "avg_score": aggregates["avg_score"],
                "total_applications": aggregates["total"],
            }
        )

    @extend_schema(
        tags=["Jobs"],
        summary="Update job voice config",
        description=(
            "Update the voice_agent_id and voice_agent_config for a job. "
            "Used by the frontend to assign a CeliyoVoice agent to a job."
        ),
        request=JobVoiceConfigSerializer,
        responses={200: JobDetailSerializer},
    )
    @action(detail=True, methods=["patch"], url_path="voice-config", url_name="voice-config")
    def voice_config(self, request, pk=None):
        """Update voice agent ID and config for a job."""
        job = self.get_object()
        serializer = JobVoiceConfigSerializer(data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)

        before = {
            "voice_agent_id": job.voice_agent_id,
            "voice_agent_config": job.voice_agent_config,
        }

        update_fields = ["updated_at"]
        if "voice_agent_id" in serializer.validated_data:
            job.voice_agent_id = serializer.validated_data["voice_agent_id"]
            update_fields.append("voice_agent_id")
        if "voice_agent_config" in serializer.validated_data:
            job.voice_agent_config = serializer.validated_data["voice_agent_config"]
            update_fields.append("voice_agent_config")

        job.save(update_fields=update_fields)

        log_activity_for_request(
            request,
            verb=Activity.Verb.UPDATED,
            resource=job,
            before=before,
            after={
                "voice_agent_id": job.voice_agent_id,
                "voice_agent_config": job.voice_agent_config,
            },
            metadata={"field": "voice_config"},
        )
        return Response(JobDetailSerializer(job).data)
