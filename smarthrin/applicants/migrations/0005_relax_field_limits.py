"""Relax phone and URL field limits for import compatibility."""
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("applicants", "0004_relax_email_constraint_for_import"),
    ]

    operations = [
        migrations.AlterField(
            model_name="applicant",
            name="phone",
            field=models.CharField(blank=True, default="", max_length=50),
        ),
        migrations.AlterField(
            model_name="applicant",
            name="resume_url",
            field=models.CharField(blank=True, default="", max_length=500),
        ),
        migrations.AlterField(
            model_name="applicant",
            name="linkedin_url",
            field=models.CharField(blank=True, default="", max_length=500),
        ),
        migrations.AlterField(
            model_name="applicant",
            name="portfolio_url",
            field=models.CharField(blank=True, default="", max_length=500),
        ),
    ]
