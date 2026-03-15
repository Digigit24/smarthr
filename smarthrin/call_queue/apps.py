"""CallQueue app configuration."""
from django.apps import AppConfig


class CallQueueConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "call_queue"
    verbose_name = "Call Queue"
