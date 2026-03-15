from django.utils import timezone
from rest_framework import mixins, status
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.viewsets import GenericViewSet

from common.authentication import JWTRequestAuthentication
from common.mixins import TenantViewSetMixin
from common.pagination import StandardResultsPagination

from .models import Notification
from .serializers import NotificationSerializer


class NotificationViewSet(TenantViewSetMixin, mixins.ListModelMixin, mixins.RetrieveModelMixin, GenericViewSet):
    serializer_class = NotificationSerializer
    authentication_classes = [JWTRequestAuthentication]
    pagination_class = StandardResultsPagination

    def get_queryset(self):
        qs = Notification.objects.filter(
            tenant_id=self.request.tenant_id,
            recipient_user_id=self.request.user_id,
        )
        return qs

    @action(detail=True, methods=["patch"], url_path="read")
    def mark_read(self, request, pk=None):
        notification = self.get_object()
        if not notification.is_read:
            notification.is_read = True
            notification.read_at = timezone.now()
            notification.save(update_fields=["is_read", "read_at", "updated_at"])
        return Response(NotificationSerializer(notification).data)

    @action(detail=False, methods=["post"], url_path="read-all")
    def mark_all_read(self, request):
        count = Notification.objects.filter(
            tenant_id=request.tenant_id,
            recipient_user_id=request.user_id,
            is_read=False,
        ).update(is_read=True, read_at=timezone.now())
        return Response({"marked_read": count})
