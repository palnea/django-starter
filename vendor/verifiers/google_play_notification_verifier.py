import base64
import json
from datetime import datetime

from django.conf import settings
from google.auth.transport import requests as google_requests
from google.oauth2 import id_token
from structlog import get_logger

from vendor.types import (
    StoreNotificationVerificationResult,
    GooglePlayNotificationType,
    GooglePlayNotificationSubtype,
)

log = get_logger(__name__)


class InvalidTokenError(Exception):
    pass


class GooglePlayNotificationVerifier:
    @staticmethod
    def verify_bearer_token(authorization_header: str) -> bool:
        """
        Verify the Google Cloud Pub/Sub OIDC bearer token.

        Google Cloud Pub/Sub can be configured to include an OIDC token in the
        Authorization header of push subscription requests. This method verifies
        that the token was issued by Google and matches the expected service account.

        Returns True if verification succeeds, False otherwise.
        """
        expected_email = getattr(settings, "GOOGLE_PUBSUB_SERVICE_ACCOUNT_EMAIL", None)
        if not expected_email:
            log.warning(
                "GOOGLE_PUBSUB_SERVICE_ACCOUNT_EMAIL not configured, "
                "skipping Google Pub/Sub bearer token verification"
            )
            return True

        if not authorization_header:
            log.warning("Missing Authorization header on Google Play webhook request")
            return False

        parts = authorization_header.split(" ", 1)
        if len(parts) != 2 or parts[0].lower() != "bearer":
            log.warning(
                "Invalid Authorization header format on Google Play webhook request"
            )
            return False

        token = parts[1]
        try:
            claim = id_token.verify_oauth2_token(token, google_requests.Request())
            token_email = claim.get("email", "")
            if token_email != expected_email:
                log.warning(
                    "Google Pub/Sub token email mismatch",
                    expected=expected_email,
                    received=token_email,
                )
                return False
            if not claim.get("email_verified", False):
                log.warning("Google Pub/Sub token email not verified")
                return False
            return True
        except Exception as e:
            log.warning(
                "Google Pub/Sub bearer token verification failed",
                error=str(e),
            )
            return False

    @staticmethod
    def parse(request_body) -> StoreNotificationVerificationResult:
        message = request_body.get("message")
        data = json.loads(base64.b64decode(message.get("data", "")))
        notification_id = message.get("messageId")
        publish_time = datetime.strptime(
            message.get("publishTime"), "%Y-%m-%dT%H:%M:%S.%fZ"
        )
        (
            notification_type,
            subtype_num,
        ) = GooglePlayNotificationType.get_type_from_notification_data(data)
        subtype = GooglePlayNotificationSubtype(subtype_num)
        return StoreNotificationVerificationResult.from_verification_result(
            notification_type=notification_type,
            subtype=subtype,
            notification_id=notification_id,
            data=data,
            notification_publish_time=publish_time,
        )
