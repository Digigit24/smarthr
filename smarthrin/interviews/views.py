"""Views for the Interview resource."""
from drf_spectacular.utils import extend_schema, extend_schema_view, OpenApiParameter
from drf_spectacular.types import OpenApiTypes
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

from .filters import InterviewFilterSet
from .models import Interview
from .serializers import InterviewDetailSerializer, InterviewListSerializer, InterviewCreateSerializer, CompleteInterviewSerializer


@extend_schema_view(
    list=extend_schema(
        tags=["Interviews"],
        summary="List interviews",
        description="Returns paginated list of interviews for the tenant.",
        parameters=[
            OpenApiParameter("status", OpenApiTypes.STR,
                enum=["SCHEDULED", "CONFIRMED", "IN_PROGRESS", "COMPLETED", "CANCELLED", "NO_SHOW"],
                description="Filter by interview status"),
            OpenApiParameter("application_id", OpenApiTypes.UUID, description="Filter by application ID"),
            OpenApiParameter("interview_type", OpenApiTypes.STR, description="Filter by interview type"),
        ],
        responses={200: InterviewListSerializer(many=True)},
    ),
    create=extend_schema(
        tags=["Interviews"],
        summary="Schedule an interview",
        request=InterviewCreateSerializer,
        responses={201: InterviewDetailSerializer},
    ),
    retrieve=extend_schema(
        tags=["Interviews"],
        summary="Get interview details",
        responses={200: InterviewDetailSerializer},
    ),
    update=extend_schema(
        tags=["Interviews"],
        summary="Update interview",
        request=InterviewCreateSerializer,
        responses={200: InterviewDetailSerializer},
    ),
    partial_update=extend_schema(
        tags=["Interviews"],
        summary="Partial update interview",
        request=InterviewCreateSerializer,
        responses={200: InterviewDetailSerializer},
    ),
    destroy=extend_schema(
        tags=["Interviews"],
        summary="Delete interview",
        responses={204: None},
    ),
)
class InterviewViewSet(TenantViewSetMixin, ModelViewSet):
    """CRUD + cancel/complete extra actions for Interview."""

    queryset = Interview.objects.select_related("application", "application__applicant").all()
    authentication_classes = [JWTRequestAuthentication]
    pagination_class = StandardResultsPagination
    filterset_class = InterviewFilterSet
    search_fields = ["interviewer_name", "interviewer_email"]
    ordering_fields = ["scheduled_at", "created_at"]

    def get_permissions(self):
        action_permission_map = {
            "list": require_permission("smarthrin.interviews.view"),
            "retrieve": require_permission("smarthrin.interviews.view"),
            "create": require_permission("smarthrin.interviews.create"),
            "update": require_permission("smarthrin.interviews.edit"),
            "partial_update": require_permission("smarthrin.interviews.edit"),
            "destroy": require_permission("smarthrin.interviews.edit"),
            "cancel": require_permission("smarthrin.interviews.edit"),
            "complete": require_permission("smarthrin.interviews.edit"),
        }
        perm_class = action_permission_map.get(
            self.action, require_permission("smarthrin.interviews.view")
        )
        return [perm_class()]

    def get_serializer_class(self):
        if self.action == "list":
            return InterviewListSerializer
        if self.action in ("create", "update", "partial_update"):
            return InterviewCreateSerializer
        return InterviewDetailSerializer

    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        self.perform_create(serializer)
        response_serializer = InterviewDetailSerializer(serializer.instance)
        return Response(response_serializer.data, status=status.HTTP_201_CREATED)

    def update(self, request, *args, **kwargs):
        partial = kwargs.pop("partial", False)
        instance = self.get_object()
        serializer = self.get_serializer(instance, data=request.data, partial=partial)
        serializer.is_valid(raise_exception=True)
        self.perform_update(serializer)
        response_serializer = InterviewDetailSerializer(serializer.instance)
        return Response(response_serializer.data)

    def perform_create(self, serializer):
        super().perform_create(serializer)
        interview = serializer.instance
        log_activity_for_request(
            self.request,
            verb=Activity.Verb.INTERVIEW_SCHEDULED,
            resource=interview,
            metadata={
                "interview_type": interview.interview_type,
                "scheduled_at": interview.scheduled_at.isoformat()
                if interview.scheduled_at
                else None,
                "interviewer_name": interview.interviewer_name,
            },
        )

    @extend_schema(
        tags=["Interviews"],
        summary="Cancel interview",
        description="Sets the interview status to CANCELLED.",
        request=None,
        responses={200: InterviewDetailSerializer},
    )
    @action(detail=True, methods=["post"], url_path="cancel")
    def cancel(self, request, pk=None):
        """Cancel an interview — sets status to CANCELLED."""
        interview = self.get_object()
        interview.status = Interview.Status.CANCELLED
        interview.save(update_fields=["status", "updated_at"])
        log_activity_for_request(
            request,
            verb=Activity.Verb.INTERVIEW_CANCELLED,
            resource=interview,
            metadata={
                "interview_type": interview.interview_type,
                "scheduled_at": interview.scheduled_at.isoformat()
                if interview.scheduled_at
                else None,
            },
        )
        serializer = self.get_serializer(interview)
        return Response(serializer.data)

    @extend_schema(
        tags=["Interviews"],
        summary="Complete interview",
        description="Marks the interview as COMPLETED. Optionally records feedback and rating (1-5).",
        request=CompleteInterviewSerializer,
        responses={200: InterviewDetailSerializer},
    )
    @action(detail=True, methods=["post"], url_path="complete")
    def complete(self, request, pk=None):
        """
        Mark an interview as COMPLETED.

        Optional body fields: feedback (str), rating (int 1-5).
        """
        interview = self.get_object()

        feedback = request.data.get("feedback")
        rating = request.data.get("rating")

        update_fields = ["status", "updated_at"]

        interview.status = Interview.Status.COMPLETED

        if feedback is not None:
            interview.feedback = feedback
            update_fields.append("feedback")

        if rating is not None:
            interview.rating = rating
            update_fields.append("rating")

        interview.save(update_fields=update_fields)

        log_activity_for_request(
            request,
            verb=Activity.Verb.INTERVIEW_COMPLETED,
            resource=interview,
            metadata={
                "interview_type": interview.interview_type,
                "rating": interview.rating,
            },
        )

        serializer = self.get_serializer(interview)
        return Response(serializer.data)
