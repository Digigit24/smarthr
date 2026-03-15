from django.apps import AppConfig


class PipelineConfig(AppConfig):
    name = "pipeline"
    default_auto_field = "django.db.models.BigAutoField"

    def ready(self) -> None:
        import pipeline.signals  # noqa: F401
