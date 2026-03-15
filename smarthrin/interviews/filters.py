"""django-filter FilterSet for Interview model."""
import django_filters

from .models import Interview


class InterviewFilterSet(django_filters.FilterSet):
    interview_type = django_filters.CharFilter(field_name="interview_type", lookup_expr="exact")
    status = django_filters.CharFilter(field_name="status", lookup_expr="exact")
    interviewer_user_id = django_filters.UUIDFilter(
        field_name="interviewer_user_id", lookup_expr="exact"
    )
    scheduled_at_gte = django_filters.DateFilter(
        field_name="scheduled_at", lookup_expr="date__gte"
    )
    scheduled_at_lte = django_filters.DateFilter(
        field_name="scheduled_at", lookup_expr="date__lte"
    )

    class Meta:
        model = Interview
        fields = [
            "interview_type",
            "status",
            "interviewer_user_id",
            "scheduled_at_gte",
            "scheduled_at_lte",
        ]
