"""
Relax email unique constraint to allow multiple applicants with blank email.

The old constraint (tenant_id, email) blocked bulk imports where not every
row has an email.  The new partial constraint only enforces uniqueness when
email is not empty, so manual create still requires unique emails while
import can store rows without email freely.
"""
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("applicants", "0003_add_custom_fields"),
    ]

    operations = [
        # 1. Drop the old absolute unique constraint
        migrations.RemoveConstraint(
            model_name="applicant",
            name="unique_tenant_applicant_email",
        ),
        # 2. Add partial unique constraint (only when email is not blank)
        migrations.AddConstraint(
            model_name="applicant",
            constraint=models.UniqueConstraint(
                fields=["tenant_id", "email"],
                name="unique_tenant_applicant_email",
                condition=models.Q(email__gt=""),
            ),
        ),
        # 3. Allow blank email at DB level
        migrations.AlterField(
            model_name="applicant",
            name="email",
            field=models.EmailField(blank=True, default="", max_length=254),
        ),
    ]
