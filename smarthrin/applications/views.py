"""Views for Application resource."""
import logging
import uuid
from django.db import transaction
from drf_spectacular.utils import extend_schema, extend_schema_view, OpenApiParameter, inline_serializer
from drf_spectacular.types import OpenApiTypes
from rest_framework import serializers as drf_serializers, status
from rest_framework.decorators import action, api_view, authentication_classes, permission_classes
from rest_framework.exceptions import ValidationError
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.viewsets import ModelViewSet

logger = logging.getLogger(__name__)

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


# ------------------------------------------------------------------
# Standalone export view (explicit path avoids DefaultRouter issues)
# ------------------------------------------------------------------

@extend_schema(
    tags=["Applications"],
    summary="Export applications",
    description=(
        "Export filtered applications as CSV or Excel. "
        "Supports the same query params as the list endpoint (status, job_id, applicant_id, etc.). "
        "Use `export_format=xlsx` for Excel or `export_format=csv` (default) for CSV."
    ),
    parameters=[
        OpenApiParameter("export_format", OpenApiTypes.STR, enum=["csv", "xlsx"], description="Export format (default: csv)"),
        OpenApiParameter("status", OpenApiTypes.STR, description="Filter by status"),
        OpenApiParameter("job_id", OpenApiTypes.UUID, description="Filter by job ID"),
        OpenApiParameter("applicant_id", OpenApiTypes.UUID, description="Filter by applicant ID"),
        OpenApiParameter("score_gte", OpenApiTypes.NUMBER, description="Minimum score"),
        OpenApiParameter("score_lte", OpenApiTypes.NUMBER, description="Maximum score"),
        OpenApiParameter("created_at_gte", OpenApiTypes.DATE, description="Created after date"),
        OpenApiParameter("created_at_lte", OpenApiTypes.DATE, description="Created before date"),
    ],
    responses={200: None},
)
@api_view(["GET"])
@authentication_classes([JWTRequestAuthentication])
@permission_classes([require_permission("smarthrin.applications.view")])
def export_applications(request: Request):
    """Export filtered applications to CSV or Excel."""
    import datetime
    from common.export import build_csv_response, build_excel_response

    qs = Application.objects.select_related("applicant", "job").filter(
        tenant_id=request.tenant_id,
    )

    # Honour permission_scope set by HasSmartHRPermission
    scope = getattr(request, "permission_scope", None)
    if scope == "own":
        qs = qs.filter(owner_user_id=request.user_id)

    # Apply filters from query params
    filterset = ApplicationFilterSet(request.query_params, queryset=qs, request=request)
    if not filterset.is_valid():
        from rest_framework.exceptions import ValidationError
        raise ValidationError(filterset.errors)
    qs = filterset.qs

    export_format = request.query_params.get("export_format", "csv").lower()

    columns = [
        ("applicant_name", "Applicant Name"),
        ("applicant_email", "Applicant Email"),
        ("applicant_phone", "Applicant Phone"),
        ("job_title", "Job Title"),
        ("status", "Status"),
        ("score", "Score"),
        ("rejection_reason", "Rejection Reason"),
        ("notes", "Notes"),
        ("created_at", "Applied At"),
        ("updated_at", "Last Updated"),
    ]

    rows = []
    for app in qs.iterator():
        rows.append({
            "applicant_name": f"{app.applicant.first_name} {app.applicant.last_name}",
            "applicant_email": app.applicant.email,
            "applicant_phone": app.applicant.phone,
            "job_title": app.job.title,
            "status": app.status,
            "score": str(app.score) if app.score is not None else "",
            "rejection_reason": app.rejection_reason,
            "notes": app.notes,
            "created_at": app.created_at,
            "updated_at": app.updated_at,
        })

    timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")

    if export_format == "xlsx":
        return build_excel_response(
            rows=rows,
            columns=columns,
            filename=f"applications_{timestamp}.xlsx",
            sheet_name="Applications",
        )
    return build_csv_response(
        rows=rows,
        columns=columns,
        filename=f"applications_{timestamp}.csv",
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
            "destroy": require_permission("smarthrin.applications.delete"),
        }

        if self.action == "bulk_action":
            # Resolve permission based on the action param in the request body
            bulk_perm_map = {
                "change_status": "smarthrin.applications.edit",
                "delete": "smarthrin.applications.delete",
                "trigger_ai_call": "smarthrin.calls.create",
                "add_to_queue": "smarthrin.calls.create",
            }
            bulk_action_type = self.request.data.get("action", "")
            perm = bulk_perm_map.get(bulk_action_type, "smarthrin.applications.edit")
            return [require_permission(perm)()]

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
        # NOTE: job.application_count is incremented by the Application
        # post_save signal in applications/signals.py — do NOT duplicate here.

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

        # NOTE: AI call dispatch is handled by the on_application_saved signal
        # when status changes to AI_SCREENING. Do NOT dispatch here to avoid
        # double dispatch.

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

        # Extract JWT token from request to forward to Voice AI Orchestrator,
        # since both services share the same JWT secret.
        auth_token = None
        auth_header = request.META.get("HTTP_AUTHORIZATION", "")
        if auth_header.startswith("Bearer "):
            auth_token = auth_header[7:]

        try:
            call_record = trigger_ai_screening_call(
                application_id=str(application.pk),
                tenant_id=str(request.tenant_id),
                owner_user_id=str(request.user_id),
                auth_token=auth_token,
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
        except Exception as exc:
            logger.exception("Unexpected error triggering AI call for application %s", pk)
            return Response(
                {
                    "error": str(exc) or "An unexpected error occurred while triggering the AI call.",
                    "code": "INTERNAL_ERROR",
                    "details": {},
                },
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
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
        description=(
            "Apply an action to multiple applications at once.\n\n"
            "Supported actions:\n"
            "- `change_status`: requires `status` field\n"
            "- `delete`: permanently deletes the applications\n"
            "- `trigger_ai_call`: dispatches AI screening calls (async via Celery)\n"
            "- `add_to_queue`: adds applications to a call queue; requires `queue_id`"
        ),
        request=BulkActionSerializer,
        responses={200: inline_serializer("BulkActionResponse", fields={
            "affected": drf_serializers.IntegerField(),
            "action": drf_serializers.CharField(),
            "errors": drf_serializers.ListField(child=drf_serializers.DictField(), required=False),
        })},
    )
    @action(detail=False, methods=["post"], url_path="bulk-action", url_name="bulk-action")
    def bulk_action(self, request):
        """
        Bulk operations on applications.
        Body: { application_ids: [...], action: "...", status?: "...", queue_id?: "..." }
        """
        serializer = BulkActionSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data

        application_ids = data["application_ids"]
        bulk_action_type = data["action"]

        qs = Application.objects.filter(
            pk__in=application_ids,
            tenant_id=request.tenant_id,
        )

        if bulk_action_type == "change_status":
            result = self._bulk_change_status(qs, data)
        elif bulk_action_type == "delete":
            result = self._bulk_delete(qs)
        elif bulk_action_type == "trigger_ai_call":
            result = self._bulk_trigger_ai_call(qs, request)
        elif bulk_action_type == "add_to_queue":
            result = self._bulk_add_to_queue(qs, data, request)
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
                **result,
            },
        )

        return Response(
            {"action": bulk_action_type, **result},
            status=status.HTTP_200_OK,
        )

    # -- Bulk action handlers ------------------------------------------------

    @staticmethod
    def _bulk_change_status(qs, data):
        new_status = data.get("status")
        valid_statuses = [choice[0] for choice in Application.Status.choices]
        if not new_status or new_status not in valid_statuses:
            raise ValidationError(
                {"status": f"Invalid status. Must be one of: {', '.join(valid_statuses)}"}
            )
        affected = qs.update(status=new_status)
        return {"affected": affected}

    @staticmethod
    def _bulk_delete(qs):
        affected, _ = qs.delete()
        return {"affected": affected}

    @staticmethod
    def _bulk_trigger_ai_call(qs, request):
        dispatched = 0
        errors = []
        for app in qs.select_related("job", "applicant"):
            # Skip applications that already have an active call or aren't suitable
            if app.status in (Application.Status.AI_SCREENING, Application.Status.REJECTED, Application.Status.WITHDRAWN):
                errors.append({"application_id": str(app.pk), "error": f"Cannot call — status is {app.status}"})
                continue
            if not app.job.voice_agent_id:
                errors.append({"application_id": str(app.pk), "error": "Job has no voice_agent_id configured"})
                continue
            if not app.applicant.phone:
                errors.append({"application_id": str(app.pk), "error": "Applicant has no phone number"})
                continue

            # Setting status to AI_SCREENING and saving triggers the
            # on_application_saved signal, which dispatches the AI call.
            # Do NOT also call dispatch_ai_call here (double dispatch bug).
            app.status = Application.Status.AI_SCREENING
            app.save(update_fields=["status", "updated_at"])
            dispatched += 1

        result = {"affected": dispatched}
        if errors:
            result["errors"] = errors
        return result

    @staticmethod
    def _bulk_add_to_queue(qs, data, request):
        from call_queue.models import CallQueue, CallQueueItem

        queue_id = data.get("queue_id")
        if not queue_id:
            raise ValidationError({"queue_id": "This field is required for add_to_queue action."})

        try:
            queue = CallQueue.objects.get(
                id=queue_id,
                tenant_id=request.tenant_id,
            )
        except CallQueue.DoesNotExist:
            raise ValidationError({"queue_id": "Call queue not found."})

        if queue.status not in (CallQueue.Status.DRAFT, CallQueue.Status.PAUSED):
            raise ValidationError(
                {"queue_id": f"Queue is '{queue.status}'. Must be DRAFT or PAUSED to add items."}
            )

        # Get existing queue application IDs to skip duplicates
        existing_app_ids = set(
            CallQueueItem.objects.filter(queue=queue).values_list("application_id", flat=True)
        )

        # Determine next position
        last_position = (
            CallQueueItem.objects.filter(queue=queue)
            .order_by("-position")
            .values_list("position", flat=True)
            .first()
            or 0
        )

        items_to_create = []
        skipped = 0
        for app in qs:
            if app.pk in existing_app_ids:
                skipped += 1
                continue
            last_position += 1
            items_to_create.append(
                CallQueueItem(
                    queue=queue,
                    application=app,
                    position=last_position,
                    status=CallQueueItem.Status.PENDING,
                    tenant_id=str(request.tenant_id),
                    owner_user_id=str(request.user_id),
                )
            )

        if items_to_create:
            CallQueueItem.objects.bulk_create(items_to_create)
            total_queued = CallQueueItem.objects.filter(queue=queue).count()
            queue.total_queued = total_queued
            queue.save(update_fields=["total_queued", "updated_at"])

        added = len(items_to_create)
        return {"affected": added, "skipped": skipped, "queue_id": str(queue_id)}
