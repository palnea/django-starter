import httpx
from django.conf import settings
from django.utils.translation import gettext_lazy as _
from rest_framework import status
from structlog import get_logger

from common.custom_exceptions.custom_exception import CustomException
from common.response.response_information_codes.error_code import ErrorCode

log = get_logger(__name__)

QONVERSION_BASE_URL = "https://api.qonversion.io/v3"


class QonversionClient:
    def __init__(self, http_timeout: int = 15):
        self.http_timeout = http_timeout
        self.api_key = settings.QONVERSION_API_SECRET_KEY
        self._headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }

    def _request(self, method: str, url: str, **kwargs) -> dict:
        try:
            response = httpx.request(
                method, url, headers=self._headers, timeout=self.http_timeout, **kwargs
            )
            response.raise_for_status()
            return response.json()
        except httpx.HTTPStatusError as e:
            log.error(
                "Qonversion API request failed",
                method=method,
                url=url,
                status_code=e.response.status_code,
                response_body=e.response.text,
            )
            raise CustomException.business_logic_error(
                title=_("Qonversion API Error"),
                detail=_("Qonversion API request failed."),
                code=ErrorCode.INTERNAL_SERVER_ERROR,
                status_code=status.HTTP_502_BAD_GATEWAY,
            )

    def get_user_entitlements(self, user_id: str) -> dict:
        url = f"{QONVERSION_BASE_URL}/users/{user_id}/entitlements"
        return self._request("GET", url)

    def grant_entitlement(self, user_id: str, entitlement_id: str) -> dict:
        url = f"{QONVERSION_BASE_URL}/users/{user_id}/entitlements/{entitlement_id}"
        return self._request("POST", url)

    def create_identity(self, qonversion_user_id: str, custom_user_id: str) -> dict:
        url = f"{QONVERSION_BASE_URL}/identities/{qonversion_user_id}"
        return self._request("POST", url, json={"custom_user_id": custom_user_id})

    def get_identity(self, custom_user_id: str) -> dict:
        url = f"{QONVERSION_BASE_URL}/identities/{custom_user_id}"
        return self._request("GET", url)
