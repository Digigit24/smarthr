from django.apps import AppConfig


class InterviewsConfig(AppConfig):
    name = "interviews"
    default_auto_field = "django.db.models.BigAutoField"

    def ready(self) -> None:
        import interviews.signals  # noqa: F401
