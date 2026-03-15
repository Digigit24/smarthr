"""Django admin registration for Applicant model."""
from django.contrib import admin

from .models import Applicant


@admin.register(Applicant)
class ApplicantAdmin(admin.ModelAdmin):
    list_display = [
        "id",
        "first_name",
        "last_name",
        "email",
        "phone",
        "source",
        "tenant_id",
    ]
    list_filter = ["source"]
    search_fields = ["first_name", "last_name", "email"]
