"""django-filter FilterSets for CallRecord and Scorecard models."""
import django_filters

from .models import CallRecord, Scorecard


class CallRecordFilterSet(django_filters.FilterSet):
    status = django_filters.CharFilter(field_name="status", lookup_expr="exact")
    provider = django_filters.CharFilter(field_name="provider", lookup_expr="exact")
    application = django_filters.UUIDFilter(field_name="application_id", lookup_expr="exact")
    created_at_gte = django_filters.DateFilter(field_name="created_at", lookup_expr="date__gte")
    created_at_lte = django_filters.DateFilter(field_name="created_at", lookup_expr="date__lte")

    class Meta:
        model = CallRecord
        fields = [
            "status",
            "provider",
            "application",
            "created_at_gte",
            "created_at_lte",
        ]


class ScorecardFilterSet(django_filters.FilterSet):
    application = django_filters.UUIDFilter(field_name="application_id", lookup_expr="exact")
    recommendation = django_filters.CharFilter(field_name="recommendation", lookup_expr="exact")
    overall_score_gte = django_filters.NumberFilter(
        field_name="overall_score", lookup_expr="gte"
    )
    overall_score_lte = django_filters.NumberFilter(
        field_name="overall_score", lookup_expr="lte"
    )

    class Meta:
        model = Scorecard
        fields = [
            "application",
            "recommendation",
            "overall_score_gte",
            "overall_score_lte",
        ]
