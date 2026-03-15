"""Views for Job resource."""
from django.db.models import Avg, Count
from django.utils import timezone
from rest_framework import status
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
from .serializers import JobDetailSerializer, JobListSerializer


class JobViewSet(TenantViewSetMixin, ModelViewSet):
    """CRUD + extra actions for Job."""

    queryset = Job.objects.all()
    authentication_classes = [JWTRequestAuthentication]
    pagination_class = StandardResultsPagination
    filterset_class = JobFilterSet
    search_fields = ["title", "department", "location"]
    ordering_fields = [
        "created_at",
        "updated_at",
        "title",
        "application_count",
        "published_at",
    ]

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
        }
        perm_class = action_permission_map.get(
            self.action, require_permission("smarthrin.jobs.view")
        )
        return [perm_class()]

    def get_serializer_class(self):
        if self.action == "list":
            return JobListSerializer
        return JobDetailSerializer

    # ------------------------------------------------------------------
    # Extra actions
    # ------------------------------------------------------------------

    @action(detail=True, methods=["post"], url_path="publish")
    def publish(self, request, pk=None):
        """Set job status to OPEN and record published_at timestamp."""
        job = self.get_object()
        job.status = Job.Status.OPEN
        job.published_at = timezone.now()
        job.save(update_fields=["status", "published_at", "updated_at"])

        log_activity_for_request(
            request,
            verb=Activity.Verb.PUBLISHED,
            resource=job,
            metadata={"title": job.title},
        )

        serializer = JobDetailSerializer(job, context={"request": request})
        return Response(serializer.data)

    @action(detail=True, methods=["post"], url_path="close")
    def close(self, request, pk=None):
        """Set job status to CLOSED."""
        job = self.get_object()
        job.status = Job.Status.CLOSED
        job.save(update_fields=["status", "updated_at"])

        log_activity_for_request(
            request,
            verb=Activity.Verb.CLOSED,
            resource=job,
            metadata={"title": job.title},
        )

        serializer = JobDetailSerializer(job, context={"request": request})
        return Response(serializer.data)

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
