"""django-filter FilterSet for Applicant model."""
import django_filters

from .models import Applicant


class ApplicantFilterSet(django_filters.FilterSet):
    source = django_filters.CharFilter(field_name="source", lookup_expr="exact")
    email = django_filters.CharFilter(field_name="email", lookup_expr="icontains")
    first_name = django_filters.CharFilter(
        field_name="first_name", lookup_expr="icontains"
    )
    last_name = django_filters.CharFilter(
        field_name="last_name", lookup_expr="icontains"
    )
    experience_years_gte = django_filters.NumberFilter(
        field_name="experience_years", lookup_expr="gte"
    )
    experience_years_lte = django_filters.NumberFilter(
        field_name="experience_years", lookup_expr="lte"
    )
    skills = django_filters.CharFilter(method="filter_skills")

    class Meta:
        model = Applicant
        fields = [
            "source",
            "email",
            "first_name",
            "last_name",
            "experience_years_gte",
            "experience_years_lte",
            "skills",
        ]

    def filter_skills(self, queryset, name, value):
        """Filter applicants whose skills JSONField list contains the given value."""
        return queryset.filter(skills__contains=value)
