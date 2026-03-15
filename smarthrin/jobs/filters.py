"""django-filter FilterSet for Job model."""
import django_filters

from .models import Job


class JobFilterSet(django_filters.FilterSet):
    status = django_filters.CharFilter(field_name="status", lookup_expr="exact")
    job_type = django_filters.CharFilter(field_name="job_type", lookup_expr="exact")
    experience_level = django_filters.CharFilter(
        field_name="experience_level", lookup_expr="exact"
    )
    department = django_filters.CharFilter(
        field_name="department", lookup_expr="icontains"
    )
    location = django_filters.CharFilter(
        field_name="location", lookup_expr="icontains"
    )
    published_at_gte = django_filters.DateFilter(
        field_name="published_at", lookup_expr="date__gte"
    )
    published_at_lte = django_filters.DateFilter(
        field_name="published_at", lookup_expr="date__lte"
    )

    class Meta:
        model = Job
        fields = [
            "status",
            "job_type",
            "experience_level",
            "department",
            "location",
            "published_at_gte",
            "published_at_lte",
        ]
