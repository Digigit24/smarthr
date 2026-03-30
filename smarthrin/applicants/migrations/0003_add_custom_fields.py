"""Add custom_fields JSONField to Applicant for storing arbitrary import data."""
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("applicants", "0002_add_trigram_indexes"),
    ]

    operations = [
        migrations.AddField(
            model_name="applicant",
            name="custom_fields",
            field=models.JSONField(
                blank=True,
                default=dict,
                help_text="Arbitrary key-value data from import or manual entry (e.g. salary expectation, notice period).",
            ),
        ),
    ]
