import datetime
from typing import Dict

import httplib2
from django.conf import settings
from django.utils.translation import gettext_lazy as _
from googleapiclient.discovery import build
from oauth2client.service_account import ServiceAccountCredentials
from rest_framework import status

from common.custom_exceptions.custom_exception import CustomException
from common.response.response_information_codes.error_code import ErrorCode


class GooglePlayClient:
    DEFAULT_AUTH_SCOPE = "https://www.googleapis.com/auth/androidpublisher"

    def __init__(
        self,
        http_timeout: int = 15,
    ) -> None:
        """
        Arguments:
            bundle_id: str - Also known as Android app's package name.
            play_console_credentials - Path or dict contents of Google's Service Credentials
            http_timeout: int - HTTP connection timeout.
        """
        api_credentials = {
            "type": settings.GOOGLE_PLAY_TYPE,
            "project_id": settings.GOOGLE_PLAY_PROJECT_ID,
            "private_key_id": settings.GOOGLE_PLAY_PRIVATE_KEY_ID,
            "private_key": settings.GOOGLE_PLAY_PRIVATE_KEY.replace("\\n", "\n"),
            "client_email": settings.GOOGLE_PLAY_CLIENT_EMAIL,
            "client_id": settings.GOOGLE_PLAY_CLIENT_ID,
            "auth_uri": settings.GOOGLE_PLAY_AUTH_URI,
            "token_uri": settings.GOOGLE_PLAY_TOKEN_URI,
            "auth_provider_x509_cert_url": settings.GOOGLE_PLAY_AUTH_PROVIDER_X509_CERT_URL,
            "client_x509_cert_url": settings.GOOGLE_PLAY_CLIENT_X509_CERT_URL,
            "universe_domain": settings.GOOGLE_PLAY_UNIVERSE_DOMAIN,
        }
        self.bundle_id = settings.GOOGLE_PLAY_PACKAGE_NAME
        self.play_console_credentials = api_credentials
        self.http_timeout = http_timeout
        self.http = self._authorize()
        self.service = build("androidpublisher", "v3", http=self.http)

    @staticmethod
    def _ms_timestamp_expired(ms_timestamp: str) -> bool:
        now = datetime.datetime.utcnow()

        # Return if it's 0/None, expired.
        if not ms_timestamp:
            return True

        ms_timestamp_value = int(ms_timestamp) / 1000

        # Return if it's 0, expired.
        if not ms_timestamp_value:
            return True

        return datetime.datetime.utcfromtimestamp(ms_timestamp_value) < now

    @staticmethod
    def _create_credentials(play_console_credentials: Dict, scope_str: str):
        # If dict, assume parsed json
        if isinstance(play_console_credentials, dict):
            return ServiceAccountCredentials.from_json_keyfile_dict(
                play_console_credentials, scope_str
            )
        raise CustomException.business_logic_error(
            title=_("Google Play Console Credentials Error"),
            detail=f"Unknown play console credentials format: {repr(play_console_credentials)}, expected 'dict' type",
            code=ErrorCode.GOOGLE_PLAY_CONSOLE_CREDENTIALS_NOT_FOUND,
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        )

    def _authorize(self):
        http = httplib2.Http(timeout=self.http_timeout)
        credentials = self._create_credentials(
            self.play_console_credentials, self.DEFAULT_AUTH_SCOPE
        )
        http = credentials.authorize(http)
        return http

    def get_subscription_info(self, product_name: str, transaction_id: str) -> dict:
        """
        Fetches the details from google play console
        :param product_name: name of Product instance (from Product database model)
        :param transaction_id: transaction_id of payment transaction (from PaymentTransaction database model)
        :return: response from google play console as dict
        """

        purchases = self.service.purchases()
        subscriptions = purchases.subscriptions()
        subscriptions_get = subscriptions.get(
            packageName=self.bundle_id,
            subscriptionId=product_name,
            token=transaction_id,
        )
        result = subscriptions_get.execute(http=self.http)
        return result
