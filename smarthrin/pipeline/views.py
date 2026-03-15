"""Views for the PipelineStage resource."""
from django.utils.text import slugify
from rest_framework import status
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.viewsets import ModelViewSet

from common.authentication import JWTRequestAuthentication
from common.mixins import TenantViewSetMixin
from common.pagination import StandardResultsPagination
from common.permissions import require_permission

from .models import PipelineStage
from .serializers import PipelineStageSerializer

_DEFAULT_STAGES = [
    {"name": "Applied", "order": 0, "color": "#6b7280", "is_terminal": False},
    {"name": "AI Screening", "order": 1, "color": "#8b5cf6", "is_terminal": False},
    {"name": "Shortlisted", "order": 2, "color": "#3b82f6", "is_terminal": False},
    {"name": "Interview", "order": 3, "color": "#f59e0b", "is_terminal": False},
    {"name": "Offer", "order": 4, "color": "#10b981", "is_terminal": False},
    {"name": "Hired", "order": 5, "color": "#059669", "is_terminal": True},
    {"name": "Rejected", "order": 6, "color": "#ef4444", "is_terminal": True},
]


class PipelineStageViewSet(TenantViewSetMixin, ModelViewSet):
    """CRUD + reorder + seed-defaults actions for PipelineStage."""

    queryset = PipelineStage.objects.all()
    authentication_classes = [JWTRequestAuthentication]
    pagination_class = StandardResultsPagination
    serializer_class = PipelineStageSerializer
    ordering_fields = ["order", "created_at"]

    def get_permissions(self):
        action_permission_map = {
            "list": require_permission("smarthrin.pipeline.view"),
            "retrieve": require_permission("smarthrin.pipeline.view"),
            "create": require_permission("smarthrin.pipeline.create"),
            "update": require_permission("smarthrin.pipeline.edit"),
            "partial_update": require_permission("smarthrin.pipeline.edit"),
            "destroy": require_permission("smarthrin.pipeline.edit"),
            "reorder": require_permission("smarthrin.pipeline.edit"),
            "seed_defaults": require_permission("smarthrin.pipeline.create"),
        }
        perm_class = action_permission_map.get(
            self.action, require_permission("smarthrin.pipeline.view")
        )
        return [perm_class()]

    @action(detail=False, methods=["post"], url_path="reorder")
    def reorder(self, request):
        """
        Reorder pipeline stages.

        Body: { "stage_ids": ["<uuid>", "<uuid>", ...] }

        Sets order = index (0-based) for each stage_id in the provided list.
        Returns the updated list of stages ordered by their new order.
        """
        stage_ids = request.data.get("stage_ids", [])
        if not isinstance(stage_ids, list):
            return Response(
                {"detail": "stage_ids must be a list."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        tenant_id = request.tenant_id
        stages_by_id = {
            str(stage.id): stage
            for stage in PipelineStage.objects.filter(
                tenant_id=tenant_id, id__in=stage_ids
            )
        }

        for index, stage_id in enumerate(stage_ids):
            stage = stages_by_id.get(str(stage_id))
            if stage is not None:
                stage.order = index
                stage.save(update_fields=["order", "updated_at"])

        updated_stages = PipelineStage.objects.filter(tenant_id=tenant_id).order_by("order")
        serializer = self.get_serializer(updated_stages, many=True)
        return Response(serializer.data)

    @action(detail=False, methods=["post"], url_path="seed-defaults")
    def seed_defaults(self, request):
        """
        Seed the default pipeline stages for this tenant if they don't already exist.

        Creates up to 7 default stages (Applied, AI Screening, Shortlisted, Interview,
        Offer, Hired, Rejected). Stages are matched by slug to avoid duplicates.
        Returns the full list of stages for this tenant after seeding.
        """
        tenant_id = request.tenant_id
        owner_user_id = request.user_id

        existing_slugs = set(
            PipelineStage.objects.filter(tenant_id=tenant_id).values_list("slug", flat=True)
        )

        stages_to_create = []
        for stage_data in _DEFAULT_STAGES:
            slug = slugify(stage_data["name"])
            if slug not in existing_slugs:
                stages_to_create.append(
                    PipelineStage(
                        name=stage_data["name"],
                        slug=slug,
                        order=stage_data["order"],
                        color=stage_data["color"],
                        is_terminal=stage_data["is_terminal"],
                        is_default=True,
                        tenant_id=tenant_id,
                        owner_user_id=owner_user_id,
                    )
                )

        if stages_to_create:
            PipelineStage.objects.bulk_create(stages_to_create)

        all_stages = PipelineStage.objects.filter(tenant_id=tenant_id).order_by("order")
        serializer = self.get_serializer(all_stages, many=True)
        return Response(serializer.data, status=status.HTTP_200_OK)
