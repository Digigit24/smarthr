"""Views for the Interview resource."""
import logging

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

logger = logging.getLogger(__name__)


def _sync_calendar_create(interview: Interview) -> dict:
    """
    Try to create a Google Calendar event for the interview.

    Returns {"calendar_event_id": str, "meeting_link": str} on success,
    or an empty dict if calendar is not configured or the API call fails.
    """
    from integrations.google_calendar import (
        CalendarNotConfigured,
        CalendarAPIError,
        create_event,
        is_configured,
    )

    if not is_configured():
        return {}

    applicant_email = ""
    applicant_name = ""
    job_title = ""
    try:
        applicant_email = interview.application.applicant.email
        applicant_name = interview.application.applicant.full_name
        job_title = interview.application.job.title
    except AttributeError:
        pass

    attendees = [email for email in [interview.interviewer_email, applicant_email] if email]
    title = f"Interview: {applicant_name}" + (f" — {job_title}" if job_title else "")
    description = (
        f"Interview Type: {interview.get_interview_type_display()}\n"
        f"Candidate: {applicant_name} ({applicant_email})\n"
        f"Interviewer: {interview.interviewer_name}"
    )

    try:
        result = create_event(
            interviewer_email=interview.interviewer_email,
            attendees=attendees,
            start_time=interview.scheduled_at,
            duration_minutes=interview.duration_minutes,
            title=title,
            description=description,
        )
        return {
            "calendar_event_id": result["event_id"],
            "meeting_link": result["meeting_link"],
        }
    except CalendarNotConfigured:
        return {}
    except CalendarAPIError:
        logger.exception("Failed to create Google Calendar event for interview %s", interview.pk)
        return {}


def _sync_calendar_update(interview: Interview) -> None:
    """Try to update the Google Calendar event when interview is rescheduled."""
    from integrations.google_calendar import (
        CalendarNotConfigured,
        CalendarAPIError,
        update_event,
    )

    if not interview.calendar_event_id:
        return

    applicant_email = ""
    try:
        applicant_email = interview.application.applicant.email
    except AttributeError:
        pass

    attendees = [email for email in [interview.interviewer_email, applicant_email] if email]

    try:
        update_event(
            event_id=interview.calendar_event_id,
            start_time=interview.scheduled_at,
            duration_minutes=interview.duration_minutes,
            attendees=attendees,
        )
    except (CalendarNotConfigured, CalendarAPIError):
        logger.exception("Failed to update Google Calendar event %s", interview.calendar_event_id)


def _sync_calendar_cancel(interview: Interview) -> None:
    """Try to cancel the Google Calendar event."""
    from integrations.google_calendar import (
        CalendarNotConfigured,
        CalendarAPIError,
        cancel_event,
    )

    if not interview.calendar_event_id:
        return

    try:
        cancel_event(interview.calendar_event_id)
    except (CalendarNotConfigured, CalendarAPIError):
        logger.exception("Failed to cancel Google Calendar event %s", interview.calendar_event_id)


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
        description=(
            "Schedule a new interview. If Google Calendar is configured, a calendar event "
            "with a Google Meet link is automatically created and returned in the response."
        ),
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
        description="Update interview details. Calendar event is automatically updated if rescheduled.",
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

    queryset = Interview.objects.select_related("application", "application__applicant", "application__job").all()
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

        interview = serializer.instance

        # Sync to Google Calendar (creates event + Meet link)
        calendar_data = _sync_calendar_create(interview)
        if calendar_data:
            update_fields = ["updated_at"]
            if calendar_data.get("calendar_event_id"):
                interview.calendar_event_id = calendar_data["calendar_event_id"]
                update_fields.append("calendar_event_id")
            if calendar_data.get("meeting_link"):
                interview.meeting_link = calendar_data["meeting_link"]
                update_fields.append("meeting_link")
            if len(update_fields) > 1:
                interview.save(update_fields=update_fields)

        response_serializer = InterviewDetailSerializer(interview)
        data = response_serializer.data
        if not calendar_data and not interview.meeting_link:
            data["_calendar_sync"] = "skipped"
        return Response(data, status=status.HTTP_201_CREATED)

    def update(self, request, *args, **kwargs):
        partial = kwargs.pop("partial", False)
        instance = self.get_object()
        old_scheduled_at = instance.scheduled_at
        old_duration = instance.duration_minutes

        serializer = self.get_serializer(instance, data=request.data, partial=partial)
        serializer.is_valid(raise_exception=True)
        self.perform_update(serializer)

        interview = serializer.instance

        # If rescheduled, update the calendar event
        rescheduled = (
            interview.scheduled_at != old_scheduled_at
            or interview.duration_minutes != old_duration
        )
        if rescheduled and interview.calendar_event_id:
            _sync_calendar_update(interview)

        response_serializer = InterviewDetailSerializer(interview)
        return Response(response_serializer.data)

    def perform_destroy(self, instance):
        # Cancel calendar event before deleting
        _sync_calendar_cancel(instance)
        super().perform_destroy(instance)

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
        description="Sets the interview status to CANCELLED and cancels the Google Calendar event if present.",
        request=None,
        responses={200: InterviewDetailSerializer},
    )
    @action(detail=True, methods=["post"], url_path="cancel")
    def cancel(self, request, pk=None):
        """Cancel an interview — sets status to CANCELLED and cancels calendar event."""
        interview = self.get_object()
        interview.status = Interview.Status.CANCELLED
        interview.save(update_fields=["status", "updated_at"])

        # Cancel the Google Calendar event
        _sync_calendar_cancel(interview)

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
