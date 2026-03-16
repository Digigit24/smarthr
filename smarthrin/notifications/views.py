from django.utils import timezone
from drf_spectacular.utils import extend_schema, extend_schema_view, inline_serializer
from rest_framework import mixins, serializers as drf_serializers, status
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.viewsets import GenericViewSet

from common.authentication import JWTRequestAuthentication
from common.mixins import TenantViewSetMixin
from common.pagination import StandardResultsPagination

from .models import Notification
from .serializers import NotificationSerializer


@extend_schema_view(
    list=extend_schema(
        tags=["Notifications"],
        summary="List notifications",
        description="Returns paginated list of notifications for the current user.",
        responses={200: NotificationSerializer(many=True)},
    ),
    retrieve=extend_schema(
        tags=["Notifications"],
        summary="Get notification",
        responses={200: NotificationSerializer},
    ),
)
class NotificationViewSet(TenantViewSetMixin, mixins.ListModelMixin, mixins.RetrieveModelMixin, GenericViewSet):
    serializer_class = NotificationSerializer
    authentication_classes = [JWTRequestAuthentication]
    pagination_class = StandardResultsPagination
    search_fields = ["title", "message", "category"]
    ordering_fields = ["created_at", "is_read", "category"]
    ordering = ["-created_at"]

    def get_queryset(self):
        qs = Notification.objects.filter(
            tenant_id=self.request.tenant_id,
            recipient_user_id=self.request.user_id,
        )
        return qs

    @extend_schema(
        tags=["Notifications"],
        summary="Mark notification as read",
        request=None,
        responses={200: NotificationSerializer},
    )
    @action(detail=True, methods=["patch"], url_path="read")
    def mark_read(self, request, pk=None):
        notification = self.get_object()
        if not notification.is_read:
            notification.is_read = True
            notification.read_at = timezone.now()
            notification.save(update_fields=["is_read", "read_at", "updated_at"])
        return Response(NotificationSerializer(notification).data)

    @extend_schema(
        tags=["Notifications"],
        summary="Mark all notifications as read",
        request=None,
        responses={200: inline_serializer("MarkAllReadResponse", fields={
            "marked_read": drf_serializers.IntegerField(),
        })},
    )
    @action(detail=False, methods=["post"], url_path="read-all")
    def mark_all_read(self, request):
        count = Notification.objects.filter(
            tenant_id=request.tenant_id,
            recipient_user_id=request.user_id,
            is_read=False,
        ).update(is_read=True, read_at=timezone.now())
        return Response({"marked_read": count})
