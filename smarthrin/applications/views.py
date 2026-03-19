"""Views for Application resource."""
import uuid
from django.db import transaction
from django.db.models import F
from drf_spectacular.utils import extend_schema, extend_schema_view, OpenApiParameter, inline_serializer
from drf_spectacular.types import OpenApiTypes
from rest_framework import serializers as drf_serializers, status
from rest_framework.decorators import action
from rest_framework.exceptions import ValidationError
from rest_framework.response import Response
from rest_framework.viewsets import ModelViewSet

from activities.models import Activity
from activities.services import log_activity, log_activity_for_request
from applicants.models import Applicant
from applicants.serializers import ApplicantDetailSerializer
from common.authentication import JWTRequestAuthentication
from common.mixins import TenantViewSetMixin
from common.pagination import StandardResultsPagination
from common.permissions import require_permission

from .filters import ApplicationFilterSet
from .models import Application
from .serializers import (
    ApplicationDetailSerializer,
    ApplicationListSerializer,
    ApplicationCreateSerializer,
    ChangeStatusSerializer,
    BulkActionSerializer,
    TriggerAICallResponseSerializer,
)


@extend_schema_view(
    list=extend_schema(
        tags=["Applications"],
        summary="List applications",
        description="Returns paginated list of applications for the tenant. Supports filtering by status, job, applicant.",
        parameters=[
            OpenApiParameter("status", OpenApiTypes.STR, description="Filter by application status"),
            OpenApiParameter("job_id", OpenApiTypes.UUID, description="Filter by job ID"),
            OpenApiParameter("applicant_id", OpenApiTypes.UUID, description="Filter by applicant ID"),
        ],
        responses={200: ApplicationListSerializer(many=True)},
    ),
    create=extend_schema(
        tags=["Applications"],
        summary="Create an application",
        description="Creates a new application linking an applicant to a job. Supports inline applicant creation.",
        request=ApplicationCreateSerializer,
        responses={201: ApplicationDetailSerializer},
    ),
    retrieve=extend_schema(
        tags=["Applications"],
        summary="Get application details",
        description="Returns full application details including nested call records, scorecards, and interviews.",
        responses={200: ApplicationDetailSerializer},
    ),
    update=extend_schema(
        tags=["Applications"],
        summary="Update application",
        request=ApplicationCreateSerializer,
        responses={200: ApplicationDetailSerializer},
    ),
    partial_update=extend_schema(
        tags=["Applications"],
        summary="Partial update application",
        request=ApplicationCreateSerializer,
        responses={200: ApplicationDetailSerializer},
    ),
    destroy=extend_schema(
        tags=["Applications"],
        summary="Delete application",
        responses={204: None},
    ),
)
class ApplicationViewSet(TenantViewSetMixin, ModelViewSet):
    """CRUD + extra actions for Application."""

    queryset = Application.objects.select_related("applicant", "job").all()
    authentication_classes = [JWTRequestAuthentication]
    pagination_class = StandardResultsPagination
    filterset_class = ApplicationFilterSet
    search_fields = ["applicant__email", "applicant__first_name", "applicant__last_name"]
    ordering_fields = ["created_at", "updated_at", "score", "status"]

    def get_permissions(self):
        action_permission_map = {
            "list": require_permission("smarthrin.applications.view"),
            "retrieve": require_permission("smarthrin.applications.view"),
            "create": require_permission("smarthrin.applications.create"),
            "update": require_permission("smarthrin.applications.edit"),
            "partial_update": require_permission("smarthrin.applications.edit"),
            "change_status": require_permission("smarthrin.applications.edit"),
            "trigger_ai_call": require_permission("smarthrin.calls.create"),
            "bulk_action": require_permission("smarthrin.applications.edit"),
        }
        perm_class = action_permission_map.get(
            self.action, require_permission("smarthrin.applications.view")
        )
        return [perm_class()]

    def get_serializer_class(self):
        if self.action == "list":
            return ApplicationListSerializer
        if self.action in ("create", "update", "partial_update"):
            return ApplicationCreateSerializer
        return ApplicationDetailSerializer

    @transaction.atomic
    def perform_create(self, serializer):
        """
        Validate job and applicant belong to same tenant.
        Support inline applicant creation when 'applicant' dict is provided.
        Increment job.application_count using F() to avoid race conditions.
        """
        request = self.request
        tenant_id = request.tenant_id

        # Inline applicant creation: if 'applicant' key in request data is a dict
        applicant_data = request.data.get("applicant")
        applicant_instance = serializer.validated_data.get("applicant")

        if isinstance(applicant_data, dict) and applicant_instance is None:
            # Create applicant inline
            applicant_serializer = ApplicantDetailSerializer(
                data=applicant_data, context={"request": request}
            )
            applicant_serializer.is_valid(raise_exception=True)
            applicant_instance = applicant_serializer.save(
                tenant_id=tenant_id,
                owner_user_id=request.user_id,
            )
        elif applicant_instance is not None:
            if str(applicant_instance.tenant_id) != str(tenant_id):
                raise ValidationError(
                    {"applicant": "Applicant does not belong to this tenant."}
                )

        job = serializer.validated_data.get("job")
        if job is not None and str(job.tenant_id) != str(tenant_id):
            raise ValidationError({"job": "Job does not belong to this tenant."})

        application = serializer.save(
            tenant_id=tenant_id,
            owner_user_id=request.user_id,
            applicant=applicant_instance,
        )

        # Increment application_count atomically
        if job is not None:
            from jobs.models import Job
            Job.objects.filter(pk=job.pk).update(application_count=F("application_count") + 1)

    def perform_update(self, serializer):
        instance = serializer.save(tenant_id=self.request.tenant_id)
        log_activity_for_request(
            self.request,
            verb=Activity.Verb.UPDATED,
            resource=instance,
        )

    # ------------------------------------------------------------------
    # Extra actions
    # ------------------------------------------------------------------

    @extend_schema(
        tags=["Applications"],
        summary="Change application status",
        description="Update the status of an application. Setting to AI_SCREENING automatically queues an AI call.",
        request=ChangeStatusSerializer,
        responses={200: ApplicationDetailSerializer},
    )
    @action(detail=True, methods=["post"], url_path="change-status", url_name="change-status")
    def change_status(self, request, pk=None):
        """Change application status; triggers AI call task when status=AI_SCREENING."""
        application = self.get_object()

        new_status = request.data.get("status")
        reason = request.data.get("reason", "")

        valid_statuses = [choice[0] for choice in Application.Status.choices]
        if not new_status or new_status not in valid_statuses:
            raise ValidationError(
                {"status": f"Invalid status. Must be one of: {', '.join(valid_statuses)}"}
            )

        before = {"status": application.status}
        application.status = new_status
        if reason:
            application.rejection_reason = reason
        update_fields = ["status", "updated_at"]
        if reason:
            update_fields.append("rejection_reason")
        application.save(update_fields=update_fields)
        after = {"status": application.status}

        log_activity_for_request(
            request,
            verb=Activity.Verb.STATUS_CHANGED,
            resource=application,
            before=before,
            after=after,
            metadata={"reason": reason},
        )

        if new_status == Application.Status.AI_SCREENING:
            from calls.tasks import dispatch_ai_call
            dispatch_ai_call.delay(
                str(application.pk),
                str(request.tenant_id),
                str(request.user_id),
            )

        serializer = ApplicationDetailSerializer(
            application, context={"request": request}
        )
        return Response(serializer.data)

    @extend_schema(
        tags=["Applications"],
        summary="Trigger AI screening call",
        description="Manually initiates an AI voice screening call for this application.",
        request=None,
        responses={201: TriggerAICallResponseSerializer},
    )
    @action(detail=True, methods=["post"], url_path="trigger-ai-call", url_name="trigger-ai-call")
    def trigger_ai_call(self, request, pk=None):
        """Manually trigger an AI screening call for this application."""
        from calls.serializers import CallRecordSerializer
        from calls.services import trigger_ai_screening_call
        from integrations.exceptions import VoiceAIError

        application = self.get_object()

        try:
            call_record = trigger_ai_screening_call(
                application_id=str(application.pk),
                tenant_id=str(request.tenant_id),
                owner_user_id=str(request.user_id),
            )
        except ValueError as exc:
            raise ValidationError({"detail": str(exc)})
        except VoiceAIError as exc:
            return Response(
                {
                    "error": exc.message,
                    "code": exc.code,
                    "details": exc.details,
                },
                status=exc.status_code,
            )

        log_activity_for_request(
            request,
            verb=Activity.Verb.TRIGGERED_CALL,
            resource=application,
            metadata={"call_record_id": str(call_record.pk)},
        )

        serializer = CallRecordSerializer(call_record, context={"request": request})
        return Response(serializer.data, status=status.HTTP_201_CREATED)

    @extend_schema(
        tags=["Applications"],
        summary="Bulk action on applications",
        description="Apply an action (e.g. change_status) to multiple applications at once.",
        request=BulkActionSerializer,
        responses={200: inline_serializer("BulkActionResponse", fields={
            "updated": drf_serializers.IntegerField(),
            "action": drf_serializers.CharField(),
        })},
    )
    @action(detail=False, methods=["post"], url_path="bulk-action", url_name="bulk-action")
    def bulk_action(self, request):
        """
        Bulk update applications.
        Body: { application_ids: [...], action: "change_status", status: "..." }
        """
        application_ids = request.data.get("application_ids", [])
        bulk_action_type = request.data.get("action")
        new_status = request.data.get("status")

        if not application_ids:
            raise ValidationError({"application_ids": "This field is required."})
        if not bulk_action_type:
            raise ValidationError({"action": "This field is required."})

        qs = Application.objects.filter(
            pk__in=application_ids,
            tenant_id=request.tenant_id,
        )

        if bulk_action_type == "change_status":
            valid_statuses = [choice[0] for choice in Application.Status.choices]
            if not new_status or new_status not in valid_statuses:
                raise ValidationError(
                    {"status": f"Invalid status. Must be one of: {', '.join(valid_statuses)}"}
                )
            updated_count = qs.update(status=new_status)
        else:
            raise ValidationError({"action": f"Unsupported bulk action: {bulk_action_type}"})

        log_activity(
            tenant_id=str(request.tenant_id),
            actor_user_id=str(request.user_id),
            actor_email=getattr(request, "email", ""),
            verb=Activity.Verb.BULK_ACTION,
            resource_type="Application",
            resource_id=str(uuid.uuid4()),
            resource_label=f"Bulk {bulk_action_type} on {len(application_ids)} applications",
            metadata={
                "action": bulk_action_type,
                "application_ids": [str(aid) for aid in application_ids],
                "new_status": new_status,
                "updated_count": updated_count,
            },
        )

        return Response(
            {"updated": updated_count, "action": bulk_action_type},
            status=status.HTTP_200_OK,
        )
