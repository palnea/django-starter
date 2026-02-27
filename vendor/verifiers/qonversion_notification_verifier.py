from datetime import datetime

from django.conf import settings
from structlog import get_logger

from vendor.types import (
    QonversionNotificationType,
    QonversionNotificationSubtype,
    StoreNotificationVerificationResult,
)

log = get_logger(__name__)


class QonversionNotificationVerifier:
    @staticmethod
    def verify_authorization(request) -> bool:
        auth_header = request.META.get("HTTP_AUTHORIZATION", "")
        expected_token = settings.QONVERSION_WEBHOOK_AUTH_TOKEN
        if not expected_token:
            log.warning("QONVERSION_WEBHOOK_AUTH_TOKEN not configured")
            return False
        return auth_header == f"Basic {expected_token}"

    @staticmethod
    def parse(request_body: dict) -> StoreNotificationVerificationResult:
        event_name = request_body.get("event_name", "UNKNOWN")
        notification_type = QonversionNotificationType(event_name)

        notification_id = request_body.get("id", "")
        event_timestamp = request_body.get("fired_at")
        if event_timestamp:
            notification_publish_time = datetime.utcfromtimestamp(event_timestamp)
        else:
            notification_publish_time = datetime.utcnow()

        return StoreNotificationVerificationResult.from_verification_result(
            notification_type=notification_type,
            subtype=QonversionNotificationSubtype.NONE,
            notification_id=notification_id,
            data=request_body,
            notification_publish_time=notification_publish_time,
        )
