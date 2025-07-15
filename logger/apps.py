import structlog
from django.apps import AppConfig

from logger.logging_processors import send_to_betterstack


class LoggerConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "logger"

    def ready(self):
        # Configure Structlog's processor pipeline for BetterStack
        structlog.configure(
            processors=[send_to_betterstack, structlog.processors.JSONRenderer()],
        )
