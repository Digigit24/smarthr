"""Add composite index on (tenant_id, provider_call_id) for webhook lookups."""
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("calls", "0001_initial"),
    ]

    operations = [
        migrations.AddIndex(
            model_name="callrecord",
            index=models.Index(
                fields=["tenant_id", "provider_call_id"],
                name="call_records_tenant_provider_idx",
            ),
        ),
    ]
