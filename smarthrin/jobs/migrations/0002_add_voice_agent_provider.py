"""Add voice_agent_provider field to Job model."""
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("jobs", "0001_initial"),
    ]

    operations = [
        migrations.AddField(
            model_name="job",
            name="voice_agent_provider",
            field=models.CharField(blank=True, default="", max_length=50),
        ),
    ]
