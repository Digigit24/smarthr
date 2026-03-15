"""django-filter FilterSet for Application model."""
import django_filters
from django_filters import BaseInFilter, CharFilter

from .models import Application


class StatusInFilter(BaseInFilter, CharFilter):
    """Allow filtering status by multiple comma-separated values."""
    pass


class ApplicationFilterSet(django_filters.FilterSet):
    status = StatusInFilter(field_name="status", lookup_expr="in")
    job = django_filters.UUIDFilter(field_name="job__id", lookup_expr="exact")
    applicant = django_filters.UUIDFilter(field_name="applicant__id", lookup_expr="exact")
    score_gte = django_filters.NumberFilter(field_name="score", lookup_expr="gte")
    score_lte = django_filters.NumberFilter(field_name="score", lookup_expr="lte")
    created_at_gte = django_filters.DateFilter(field_name="created_at", lookup_expr="date__gte")
    created_at_lte = django_filters.DateFilter(field_name="created_at", lookup_expr="date__lte")

    class Meta:
        model = Application
        fields = [
            "status",
            "job",
            "applicant",
            "score_gte",
            "score_lte",
            "created_at_gte",
            "created_at_lte",
        ]
