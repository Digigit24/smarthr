"""Initial migration for call_queue app."""
import uuid
import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    initial = True

    dependencies = [
        ("applications", "0001_initial"),
        ("calls", "0001_initial"),
        ("jobs", "0001_initial"),
    ]

    operations = [
        migrations.CreateModel(
            name="CallQueue",
            fields=[
                ("id", models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ("tenant_id", models.UUIDField(db_index=True)),
                ("owner_user_id", models.UUIDField(db_index=True)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("name", models.CharField(max_length=255)),
                ("voice_agent_id", models.CharField(max_length=255)),
                (
                    "status",
                    models.CharField(
                        choices=[
                            ("DRAFT", "Draft"),
                            ("RUNNING", "Running"),
                            ("PAUSED", "Paused"),
                            ("COMPLETED", "Completed"),
                            ("CANCELLED", "Cancelled"),
                        ],
                        default="DRAFT",
                        max_length=20,
                    ),
                ),
                ("config", models.JSONField(blank=True, default=dict)),
                ("total_queued", models.IntegerField(default=0)),
                ("total_called", models.IntegerField(default=0)),
                ("total_completed", models.IntegerField(default=0)),
                ("total_failed", models.IntegerField(default=0)),
                ("started_at", models.DateTimeField(blank=True, null=True)),
                ("completed_at", models.DateTimeField(blank=True, null=True)),
                (
                    "job",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="call_queues",
                        to="jobs.job",
                    ),
                ),
            ],
            options={
                "db_table": "call_queues",
                "ordering": ["-created_at"],
            },
        ),
        migrations.CreateModel(
            name="CallQueueItem",
            fields=[
                ("id", models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ("tenant_id", models.UUIDField(db_index=True)),
                ("owner_user_id", models.UUIDField(db_index=True)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("position", models.IntegerField()),
                (
                    "status",
                    models.CharField(
                        choices=[
                            ("PENDING", "Pending"),
                            ("CALLING", "Calling"),
                            ("COMPLETED", "Completed"),
                            ("FAILED", "Failed"),
                            ("SKIPPED", "Skipped"),
                            ("CANCELLED", "Cancelled"),
                        ],
                        default="PENDING",
                        max_length=20,
                    ),
                ),
                ("attempts", models.IntegerField(default=0)),
                ("last_attempt_at", models.DateTimeField(blank=True, null=True)),
                ("error_message", models.TextField(blank=True, default="")),
                ("score", models.DecimalField(blank=True, decimal_places=2, max_digits=5, null=True)),
                ("completed_at", models.DateTimeField(blank=True, null=True)),
                (
                    "application",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="queue_items",
                        to="applications.application",
                    ),
                ),
                (
                    "call_record",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name="queue_items",
                        to="calls.callrecord",
                    ),
                ),
                (
                    "queue",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="items",
                        to="call_queue.callqueue",
                    ),
                ),
            ],
            options={
                "db_table": "call_queue_items",
                "ordering": ["position"],
            },
        ),
        migrations.AddIndex(
            model_name="callqueue",
            index=models.Index(fields=["tenant_id", "status"], name="call_queues_tenant_id_status_idx"),
        ),
        migrations.AddIndex(
            model_name="callqueue",
            index=models.Index(fields=["tenant_id", "job_id"], name="call_queues_tenant_id_job_id_idx"),
        ),
        migrations.AddIndex(
            model_name="callqueueitem",
            index=models.Index(fields=["queue_id", "status"], name="call_queue_items_queue_id_status_idx"),
        ),
        migrations.AddIndex(
            model_name="callqueueitem",
            index=models.Index(fields=["tenant_id", "application_id"], name="call_queue_items_tenant_app_idx"),
        ),
        migrations.AddIndex(
            model_name="callqueueitem",
            index=models.Index(fields=["queue_id", "position"], name="call_queue_items_queue_pos_idx"),
        ),
        migrations.AlterUniqueTogether(
            name="callqueueitem",
            unique_together={("queue", "application")},
        ),
    ]
