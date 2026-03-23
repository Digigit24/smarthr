"""Add GIN trigram index on job title for fast LIKE/search queries."""
from django.db import migrations
from django.contrib.postgres.indexes import GinIndex


class Migration(migrations.Migration):

    dependencies = [
        ("jobs", "0002_add_voice_agent_provider"),
        # pg_trgm extension is enabled in applicants/0002
        ("applicants", "0002_add_trigram_indexes"),
    ]

    operations = [
        migrations.AddIndex(
            model_name="job",
            index=GinIndex(
                fields=["title"],
                name="job_title_trgm",
                opclasses=["gin_trgm_ops"],
            ),
        ),
    ]
