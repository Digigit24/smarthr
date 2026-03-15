"""Views for CallQueue management."""
import logging

from django.utils import timezone
from drf_spectacular.utils import extend_schema, extend_schema_view, OpenApiParameter, inline_serializer
from drf_spectacular.types import OpenApiTypes
from rest_framework import serializers as drf_serializers, status
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.viewsets import ModelViewSet

from activities.models import Activity
from activities.services import log_activity_for_request
from common.authentication import JWTRequestAuthentication
from common.mixins import TenantViewSetMixin
from common.pagination import StandardResultsPagination
from common.permissions import require_permission
from notifications.models import Notification
from notifications.services import create_notification

from .filters import CallQueueFilterSet, CallQueueItemFilterSet
from .models import CallQueue, CallQueueItem
from .serializers import (
    CallQueueCreateSerializer,
    CallQueueDetailSerializer,
    CallQueueItemListSerializer,
    CallQueueListSerializer,
    CallQueueUpdateSerializer,
)

logger = logging.getLogger(__name__)


@extend_schema_view(
    list=extend_schema(
        tags=["Call Queues"],
        summary="List call queues",
        description="Returns paginated list of call queues for the tenant.",
        parameters=[
            OpenApiParameter("status", OpenApiTypes.STR, enum=["DRAFT", "RUNNING", "PAUSED", "COMPLETED", "CANCELLED"]),
            OpenApiParameter("job", OpenApiTypes.UUID, description="Filter by job ID"),
        ],
        responses={200: CallQueueListSerializer(many=True)},
    ),
    create=extend_schema(
        tags=["Call Queues"],
        summary="Create a call queue",
        request=CallQueueCreateSerializer,
        responses={201: CallQueueDetailSerializer},
    ),
    retrieve=extend_schema(
        tags=["Call Queues"],
        summary="Get call queue details",
        responses={200: CallQueueDetailSerializer},
    ),
    partial_update=extend_schema(
        tags=["Call Queues"],
        summary="Update call queue config",
        request=CallQueueUpdateSerializer,
        responses={200: CallQueueDetailSerializer},
    ),
    destroy=extend_schema(
        tags=["Call Queues"],
        summary="Delete a call queue",
        description="Only DRAFT or CANCELLED queues can be deleted.",
        responses={204: None},
    ),
)
class CallQueueViewSet(TenantViewSetMixin, ModelViewSet):
    """CRUD + lifecycle actions for CallQueue."""

    queryset = CallQueue.objects.select_related("job").all()
    authentication_classes = [JWTRequestAuthentication]
    pagination_class = StandardResultsPagination
    filterset_class = CallQueueFilterSet
    ordering_fields = ["created_at", "updated_at", "name", "status"]
    http_method_names = ["get", "post", "patch", "delete", "head", "options"]

    def get_permissions(self):
        action_permission_map = {
            "list": require_permission("smarthrin.call_queues.view"),
            "retrieve": require_permission("smarthrin.call_queues.view"),
            "create": require_permission("smarthrin.call_queues.create"),
            "partial_update": require_permission("smarthrin.call_queues.edit"),
            "destroy": require_permission("smarthrin.call_queues.delete"),
            "start": require_permission("smarthrin.call_queues.edit"),
            "pause": require_permission("smarthrin.call_queues.edit"),
            "resume": require_permission("smarthrin.call_queues.edit"),
            "cancel": require_permission("smarthrin.call_queues.edit"),
            "items": require_permission("smarthrin.call_queues.view"),
            "populate": require_permission("smarthrin.call_queues.edit"),
        }
        perm_class = action_permission_map.get(
            self.action, require_permission("smarthrin.call_queues.view")
        )
        return [perm_class()]

    def get_serializer_class(self):
        if self.action == "list":
            return CallQueueListSerializer
        if self.action == "create":
            return CallQueueCreateSerializer
        if self.action == "partial_update":
            return CallQueueUpdateSerializer
        return CallQueueDetailSerializer

    def destroy(self, request, *args, **kwargs):
        queue = self.get_object()
        if queue.status not in [CallQueue.Status.DRAFT, CallQueue.Status.CANCELLED]:
            return Response(
                {"detail": f"Cannot delete a queue with status '{queue.status}'. Only DRAFT or CANCELLED queues can be deleted."},
                status=status.HTTP_400_BAD_REQUEST,
            )
        log_activity_for_request(
            request,
            verb=Activity.Verb.DELETED,
            resource=queue,
            before={"status": queue.status},
        )
        return super().destroy(request, *args, **kwargs)

    @extend_schema(
        tags=["Call Queues"],
        summary="Start queue processing",
        description="Starts the queue: sets status to RUNNING and triggers Celery processing.",
        request=None,
        responses={200: CallQueueDetailSerializer},
    )
    @action(detail=True, methods=["post"], url_path="start")
    def start(self, request, pk=None):
        """Start processing the call queue."""
        from .tasks import process_call_queue

        queue = self.get_object()
        if queue.status not in [CallQueue.Status.DRAFT, CallQueue.Status.PAUSED]:
            return Response(
                {"detail": f"Queue is '{queue.status}', cannot start. Must be DRAFT or PAUSED."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        # Ensure there are items to process
        if not CallQueueItem.objects.filter(queue=queue, status=CallQueueItem.Status.PENDING).exists():
            return Response(
                {"detail": "No PENDING items in queue. Use /populate to add items first."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        queue.status = CallQueue.Status.RUNNING
        if not queue.started_at:
            queue.started_at = timezone.now()
        queue.save(update_fields=["status", "started_at", "updated_at"])

        # Kick off the queue processor
        process_call_queue.delay(str(queue.id), str(request.tenant_id))

        log_activity_for_request(
            request,
            verb=Activity.Verb.STATUS_CHANGED,
            resource=queue,
            before={"status": "DRAFT" if not queue.started_at else "PAUSED"},
            after={"status": "RUNNING"},
            metadata={"queue_name": queue.name},
        )

        try:
            create_notification(
                tenant_id=str(request.tenant_id),
                owner_user_id=str(request.user_id),
                recipient_user_id=str(request.user_id),
                notification_type=Notification.NotificationType.IN_APP,
                category=Notification.Category.CALL,
                title=f"Queue Started: {queue.name}",
                message=f"Call queue '{queue.name}' has started processing {queue.total_queued} applicants.",
                data={"queue_id": str(queue.id)},
            )
        except Exception as e:
            logger.error(f"Failed to send queue start notification: {e}")

        return Response(CallQueueDetailSerializer(queue).data)

    @extend_schema(
        tags=["Call Queues"],
        summary="Pause queue processing",
        request=None,
        responses={200: CallQueueDetailSerializer},
    )
    @action(detail=True, methods=["post"], url_path="pause")
    def pause(self, request, pk=None):
        """Pause a running queue."""
        queue = self.get_object()
        if queue.status != CallQueue.Status.RUNNING:
            return Response(
                {"detail": f"Queue is '{queue.status}', cannot pause. Must be RUNNING."},
                status=status.HTTP_400_BAD_REQUEST,
            )
        queue.status = CallQueue.Status.PAUSED
        queue.save(update_fields=["status", "updated_at"])
        log_activity_for_request(
            request,
            verb=Activity.Verb.STATUS_CHANGED,
            resource=queue,
            before={"status": "RUNNING"},
            after={"status": "PAUSED"},
        )
        return Response(CallQueueDetailSerializer(queue).data)

    @extend_schema(
        tags=["Call Queues"],
        summary="Resume queue processing",
        request=None,
        responses={200: CallQueueDetailSerializer},
    )
    @action(detail=True, methods=["post"], url_path="resume")
    def resume(self, request, pk=None):
        """Resume a paused queue."""
        from .tasks import process_call_queue

        queue = self.get_object()
        if queue.status != CallQueue.Status.PAUSED:
            return Response(
                {"detail": f"Queue is '{queue.status}', cannot resume. Must be PAUSED."},
                status=status.HTTP_400_BAD_REQUEST,
            )
        queue.status = CallQueue.Status.RUNNING
        queue.save(update_fields=["status", "updated_at"])
        process_call_queue.delay(str(queue.id), str(request.tenant_id))
        log_activity_for_request(
            request,
            verb=Activity.Verb.STATUS_CHANGED,
            resource=queue,
            before={"status": "PAUSED"},
            after={"status": "RUNNING"},
        )
        return Response(CallQueueDetailSerializer(queue).data)

    @extend_schema(
        tags=["Call Queues"],
        summary="Cancel queue processing",
        request=None,
        responses={200: CallQueueDetailSerializer},
    )
    @action(detail=True, methods=["post"], url_path="cancel")
    def cancel(self, request, pk=None):
        """Cancel a queue — marks all PENDING items as CANCELLED."""
        queue = self.get_object()
        if queue.status in [CallQueue.Status.COMPLETED, CallQueue.Status.CANCELLED]:
            return Response(
                {"detail": f"Queue is already '{queue.status}'."},
                status=status.HTTP_400_BAD_REQUEST,
            )
        queue.status = CallQueue.Status.CANCELLED
        queue.save(update_fields=["status", "updated_at"])

        # Cancel all PENDING items
        CallQueueItem.objects.filter(
            queue=queue,
            status=CallQueueItem.Status.PENDING,
        ).update(status=CallQueueItem.Status.CANCELLED)

        log_activity_for_request(
            request,
            verb=Activity.Verb.STATUS_CHANGED,
            resource=queue,
            before={"status": queue.status},
            after={"status": "CANCELLED"},
        )
        return Response(CallQueueDetailSerializer(queue).data)

    @extend_schema(
        tags=["Call Queues"],
        summary="List queue items",
        description="Returns paginated list of items in this queue.",
        parameters=[
            OpenApiParameter("status", OpenApiTypes.STR,
                enum=["PENDING", "CALLING", "COMPLETED", "FAILED", "SKIPPED", "CANCELLED"]),
        ],
        responses={200: CallQueueItemListSerializer(many=True)},
    )
    @action(detail=True, methods=["get"], url_path="items")
    def items(self, request, pk=None):
        """Return paginated queue items."""
        queue = self.get_object()
        qs = (
            CallQueueItem.objects.filter(queue=queue)
            .select_related("application__applicant", "application__job")
            .order_by("position")
        )

        # Apply status filter if provided
        item_status = request.query_params.get("status")
        if item_status:
            qs = qs.filter(status=item_status)

        page = self.paginate_queryset(qs)
        if page is not None:
            serializer = CallQueueItemListSerializer(page, many=True, context={"request": request})
            return self.get_paginated_response(serializer.data)
        serializer = CallQueueItemListSerializer(qs, many=True, context={"request": request})
        return Response(serializer.data)

    @extend_schema(
        tags=["Call Queues"],
        summary="Populate queue from job applications",
        description=(
            "Auto-populates queue items from job applications matching filter_statuses config. "
            "Skips applications that are already in the queue."
        ),
        request=None,
        responses={200: inline_serializer("PopulateResponse", fields={
            "added": drf_serializers.IntegerField(),
            "skipped": drf_serializers.IntegerField(),
            "total_queued": drf_serializers.IntegerField(),
        })},
    )
    @action(detail=True, methods=["post"], url_path="populate")
    def populate(self, request, pk=None):
        """Auto-populate queue items from job applications."""
        from applications.models import Application

        queue = self.get_object()
        if queue.status not in [CallQueue.Status.DRAFT, CallQueue.Status.PAUSED]:
            return Response(
                {"detail": f"Queue is '{queue.status}', cannot populate. Must be DRAFT or PAUSED."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        config = queue.get_config()
        filter_statuses = config.get("filter_statuses", ["APPLIED"])

        # Fetch matching applications
        applications = Application.objects.filter(
            job=queue.job,
            tenant_id=request.tenant_id,
            status__in=filter_statuses,
        ).select_related("applicant").order_by("created_at")

        # Get existing queue application IDs to avoid duplicates
        existing_app_ids = set(
            CallQueueItem.objects.filter(queue=queue).values_list("application_id", flat=True)
        )

        # Determine next position
        last_position = (
            CallQueueItem.objects.filter(queue=queue).order_by("-position").values_list("position", flat=True).first()
            or 0
        )

        items_to_create = []
        skipped = 0
        for app in applications:
            if app.id in existing_app_ids:
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

        CallQueueItem.objects.bulk_create(items_to_create)

        total_queued = CallQueueItem.objects.filter(queue=queue).count()
        queue.total_queued = total_queued
        queue.save(update_fields=["total_queued", "updated_at"])

        added = len(items_to_create)
        log_activity_for_request(
            request,
            verb=Activity.Verb.UPDATED,
            resource=queue,
            after={"added": added, "total_queued": total_queued},
            metadata={"filter_statuses": filter_statuses},
        )

        return Response({"added": added, "skipped": skipped, "total_queued": total_queued})
