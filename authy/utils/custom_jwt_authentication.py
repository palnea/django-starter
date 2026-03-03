import newrelic.agent
from rest_framework_simplejwt.authentication import JWTAuthentication


class CustomJWTAuthentication(JWTAuthentication):
    def authenticate(self, request):
        # Call the parent authentication method
        auth_result = super().authenticate(request)

        # If authentication was successful, set the New Relic user ID
        if auth_result:
            user, auth_token = auth_result
            try:
                # Check if the validated token exists and contains a payload
                if auth_token and "user_id" in auth_token:
                    user_id = auth_token["user_id"]
                    newrelic.agent.set_user_id(str(user_id))
            except Exception:
                import logging

                logger = logging.getLogger(__name__)
                logger.exception("Error setting New Relic user ID")

        return auth_result
