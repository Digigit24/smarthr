"""Add composite index on (tenant_id, recipient_user_id, -created_at) for inbox queries."""
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("notifications", "0001_initial"),
    ]

    operations = [
        migrations.AddIndex(
            model_name="notification",
            index=models.Index(
                fields=["tenant_id", "recipient_user_id", "-created_at"],
                name="notifications_inbox_idx",
            ),
        ),
    ]
