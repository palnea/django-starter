import structlog
from django.apps import AppConfig

from logger.logging_processors import send_to_newrelic


class LoggerConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "logger"

    def ready(self):
        # Configure Structlog's processor pipeline
        structlog.configure(
            processors=[
                structlog.contextvars.merge_contextvars,
                send_to_newrelic,
                structlog.processors.JSONRenderer(),
            ],
        )
