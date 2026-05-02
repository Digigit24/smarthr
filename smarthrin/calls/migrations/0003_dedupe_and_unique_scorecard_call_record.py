"""Deduplicate Scorecards per call_record + add unique constraint to prevent races."""
from django.db import migrations, models


def dedupe_scorecards(apps, schema_editor):
    """
    A race in the webhook handler (two voiceb webhooks arriving in parallel for
    the same call_record) created multiple Scorecard rows pointing at the same
    CallRecord. Keep the most recent Scorecard per call_record and delete the
    older duplicates so the upcoming UNIQUE constraint can be applied.
    """
    Scorecard = apps.get_model("calls", "Scorecard")
    qs = Scorecard.objects.filter(call_record__isnull=False).order_by("call_record_id", "-created_at")
    seen = set()
    to_delete = []
    for sc in qs:
        if sc.call_record_id in seen:
            to_delete.append(sc.id)
        else:
            seen.add(sc.call_record_id)
    if to_delete:
        Scorecard.objects.filter(id__in=to_delete).delete()


def noop_reverse(apps, schema_editor):
    """Deletions can't be undone — reverse is a no-op."""
    return


class Migration(migrations.Migration):

    dependencies = [
        ("calls", "0002_add_tenant_provider_call_id_index"),
    ]

    operations = [
        migrations.RunPython(dedupe_scorecards, reverse_code=noop_reverse),
        migrations.AddConstraint(
            model_name="scorecard",
            constraint=models.UniqueConstraint(
                fields=["call_record"],
                name="unique_scorecard_per_call_record",
                condition=models.Q(call_record__isnull=False),
            ),
        ),
    ]
