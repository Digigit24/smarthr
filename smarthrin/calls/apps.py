from django.apps import AppConfig


class CallsConfig(AppConfig):
    name = "calls"
    default_auto_field = "django.db.models.BigAutoField"

    def ready(self) -> None:
        import calls.signals  # noqa: F401
