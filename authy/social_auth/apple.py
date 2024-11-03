import base64
from datetime import timedelta

import jwt
import requests
from django.conf import settings
from django.utils import timezone
from structlog import get_logger

log = get_logger(__name__)


class Apple:
    """apple authentication backend"""

    name = "apple"
    SCOPE_SEPARATOR = ","
    ID_KEY = "uid"

    @staticmethod
    def validate(auth_token):
        """
        validate method Queries the apple API
        """
        try:
            profile = Apple.do_auth(auth_token)
            return profile
        except Exception as e:
            log.info(
                "Social auth validation failure.", provider="apple", exception=str(e)
            )
            return None

    @staticmethod
    def do_auth(access_token):
        """
        Finish the auth process once the access_token was retrieved
        Get the email from ID token received from apple
        """
        response_data = {}
        client_id, client_secret = Apple.get_key_and_secret()

        headers = {"content-type": "application/x-www-form-urlencoded"}
        data = {
            "client_id": client_id,
            "client_secret": client_secret,
            "code": access_token,
            "grant_type": "authorization_code",
        }

        res = requests.post(
            settings.SOCIAL_AUTH_APPLE_ACCESS_TOKEN_URL, data=data, headers=headers
        )
        response_dict = res.json()
        id_token = response_dict.get("id_token", None)

        if id_token:
            decoded = jwt.decode(
                id_token, algorithms=["RS256"], options={"verify_signature": False}
            )
            (
                response_data.update({"email": decoded["email"]})
                if "email" in decoded
                else None
            )
            response_data.update({"uid": decoded["sub"]}) if "sub" in decoded else None
            return response_data
        log.warning(
            "Data could not be gotten on Apple Social auth",
            apple_response=str(response_dict),
        )
        return None

    def get_user_details(self, response):
        email = response.get("email", None)
        details = {
            "email": email,
        }
        return details

    @staticmethod
    def get_key_and_secret():
        headers = {"kid": settings.SOCIAL_AUTH_APPLE_KEY_ID}

        payload = {
            "iss": settings.SOCIAL_AUTH_APPLE_TEAM_ID,
            "iat": timezone.now(),
            "exp": timezone.now() + timedelta(days=180),
            "aud": "https://appleid.apple.com",
            "sub": settings.APPLE_BUNDLE_ID,
        }

        private_key = base64.b64decode(settings.SOCIAL_AUTH_APPLE_PRIVATE_KEY)
        client_secret = jwt.encode(
            payload, private_key, algorithm="ES256", headers=headers
        )

        return settings.APPLE_BUNDLE_ID, client_secret
