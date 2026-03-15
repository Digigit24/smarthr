"""Views for the Interview resource."""
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
from .serializers import InterviewDetailSerializer, InterviewListSerializer


class InterviewViewSet(TenantViewSetMixin, ModelViewSet):
    """CRUD + cancel/complete extra actions for Interview."""

    queryset = Interview.objects.select_related("application").all()
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
        return InterviewDetailSerializer

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
