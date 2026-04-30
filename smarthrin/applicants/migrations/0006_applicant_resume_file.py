"""Add optional resume_file FileField on Applicant."""
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("applicants", "0005_relax_field_limits"),
    ]

    operations = [
        migrations.AddField(
            model_name="applicant",
            name="resume_file",
            field=models.FileField(
                blank=True,
                help_text=(
                    "Optional uploaded resume file (PDF/DOC/DOCX). Coexists "
                    "with resume_url for legacy/external links."
                ),
                max_length=500,
                null=True,
                upload_to="resumes/%Y/%m/",
            ),
        ),
    ]
