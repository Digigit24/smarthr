from django.apps import AppConfig


class ApplicationsConfig(AppConfig):
    name = "applications"
    default_auto_field = "django.db.models.BigAutoField"

    def ready(self) -> None:
        import applications.signals  # noqa: F401
