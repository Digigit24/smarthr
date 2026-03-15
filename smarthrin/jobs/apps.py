from django.apps import AppConfig


class JobsConfig(AppConfig):
    name = "jobs"
    default_auto_field = "django.db.models.BigAutoField"

    def ready(self) -> None:
        import jobs.signals  # noqa: F401
