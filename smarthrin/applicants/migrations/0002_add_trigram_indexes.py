"""Add pg_trgm extension and GIN trigram indexes on first_name, last_name, email for fast LIKE/search queries."""
from django.contrib.postgres.operations import TrigramExtension
from django.db import migrations
from django.contrib.postgres.indexes import GinIndex


class Migration(migrations.Migration):

    dependencies = [
        ("applicants", "0001_initial"),
    ]

    operations = [
        # Enable pg_trgm extension (idempotent — safe to run if already enabled)
        TrigramExtension(),
        migrations.AddIndex(
            model_name="applicant",
            index=GinIndex(
                fields=["first_name"],
                name="applicant_first_name_trgm",
                opclasses=["gin_trgm_ops"],
            ),
        ),
        migrations.AddIndex(
            model_name="applicant",
            index=GinIndex(
                fields=["last_name"],
                name="applicant_last_name_trgm",
                opclasses=["gin_trgm_ops"],
            ),
        ),
        migrations.AddIndex(
            model_name="applicant",
            index=GinIndex(
                fields=["email"],
                name="applicant_email_trgm",
                opclasses=["gin_trgm_ops"],
            ),
        ),
    ]
