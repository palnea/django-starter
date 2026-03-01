import base64
import json
from datetime import datetime, timedelta
from time import time, mktime
from typing import Dict

import httpx
import jwt
from structlog import get_logger

import settings

log = get_logger(__name__)


def retry_on_sandbox(f):
    def wrapper(*args):
        response = f(*args)
        if (
            response.get("errorCode", None) in [4040010]
            and args[0].auto_retry_wrong_env_request
            and not args[0].sandbox
        ):
            client = args[0].__class__(
                True,
                auto_retry_wrong_env_request=args[0].auto_retry_wrong_env_request,
                http_timeout=args[0].http_timeout,
            )
            function = getattr(client, f.__name__)
            response = function(*args[1:])
        return response

    return wrapper


class AppStoreInAppPurchaseAPIClient:
    def __init__(
        self,
        sandbox: bool = False,
        auto_retry_wrong_env_request: bool = False,
        http_timeout: int = None,
    ):
        self.sandbox = sandbox
        self.auto_retry_wrong_env_request: bool = auto_retry_wrong_env_request
        self.http_timeout = http_timeout

    @property
    def url(self) -> str:
        return (
            "https://api.storekit-sandbox.itunes.apple.com"
            if self.sandbox
            else "https://api.storekit.itunes.apple.com"
        )

    @property
    def jwt_token(self) -> str:
        dt = datetime.now() + timedelta(minutes=19)

        headers = {
            "alg": "ES256",
            "kid": settings.APPLE_DEVELOPER_KEY_ID,
            "typ": "JWT",
        }
        payload = {
            "iss": settings.APPLE_DEVELOPER_ISSUER_ID,
            "iat": int(time()),
            "exp": int(mktime(dt.timetuple())),
            "aud": "appstoreconnect-v1",
            "bid": settings.APPLE_BUNDLE_ID,
        }

        signing_key_base64 = settings.APPLE_IN_APP_SIGNING_KEY
        signing_key = base64.b64decode(signing_key_base64)
        gen_jwt = jwt.encode(payload, signing_key, algorithm="ES256", headers=headers)
        return gen_jwt

    @retry_on_sandbox
    def get_transaction_info(self, transaction_id: str) -> Dict:
        response = httpx.get(
            f"{self.url}/inApps/v1/transactions/{transaction_id}",
            headers={"Authorization": f"Bearer {self.jwt_token}"},
        )
        try:
            response_json = json.loads(response.text)
        except Exception:
            log.error(
                "Cannot serialize apple response",
                method_name="get_transaction_info",
                class_name=self.__class__.__name__,
                response=response,
            )
            response_json = {}
        return response_json

    @retry_on_sandbox
    def get_subscription_info(self, transaction_id: str) -> Dict:
        response = httpx.get(
            f"{self.url}/inApps/v1/subscription/{transaction_id}",
            headers={"Authorization": f"Bearer {self.jwt_token}"},
        )
        try:
            response_json = json.loads(response.text)
        except Exception:
            log.error(
                "Cannot serialize apple response",
                method_name="get_subscription_info",
                class_name=self.__class__.__name__,
                response=response,
            )
            response_json = {}
        return response_json


class AppStoreConnectAPI:
    def __init__(
        self,
        http_timeout: int = None,
    ):
        self.http_timeout = http_timeout

    @property
    def url(self) -> str:
        return "https://api.appstoreconnect.apple.com"

    @property
    def jwt_token(self) -> str:
        dt = datetime.now() + timedelta(minutes=19)

        headers = {
            "alg": "ES256",
            "kid": settings.APPLE_CONNECT_API_KEY_ID,
            "typ": "JWT",
        }
        payload = {
            "iss": settings.APPLE_DEVELOPER_ISSUER_ID,
            "iat": int(time()),
            "exp": int(mktime(dt.timetuple())),
            "aud": "appstoreconnect-v1",
            "bid": settings.APPLE_BUNDLE_ID,
        }

        signing_key_base64 = settings.APPLE_CONNECT_API_SIGNING_KEY
        signing_key = base64.b64decode(signing_key_base64)
        gen_jwt = jwt.encode(payload, signing_key, algorithm="ES256", headers=headers)
        return gen_jwt

    def list_subscriptions_in_subscription_group(
        self, subscription_group_id: str
    ) -> Dict:
        url = f"{self.url}/v1/subscriptionGroups/{subscription_group_id}/subscriptions"
        response = httpx.get(url, headers={"Authorization": f"Bearer {self.jwt_token}"})
        return json.loads(response.text)

    def list_subscription_price(self, product_id: str, country_code: str):
        url = f"{self.url}/v1/subscriptions/{product_id}/prices"
        params = {
            "filter[territory]": country_code,
            "include": "territory,subscriptionPricePoint",
            "fields[territories]": "currency",
        }
        response = httpx.get(
            url, params=params, headers={"Authorization": f"Bearer {self.jwt_token}"}
        )
        return json.loads(response.text)
