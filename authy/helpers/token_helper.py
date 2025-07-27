from typing import Dict, TYPE_CHECKING

from django.contrib.auth import authenticate
from django.contrib.auth.models import update_last_login
from django.core.exceptions import ObjectDoesNotExist
from django.utils.translation import gettext_lazy as _
from rest_framework import status
from rest_framework_simplejwt.tokens import Token

from authy.custom.token_serializer import CustomTokenObtainPairSerializer
from common.custom_exceptions.custom_exception import CustomException
from common.response.response_information_codes.error_code import ErrorCode

if TYPE_CHECKING:
    from user.models import User


def get_token_subscription_for_user(user: "User"):
    subscription = user.last_or_active_subscription
    return subscription


def set_token_parameters(token: Token, parameters: Dict[str, any]) -> Token:
    for key in parameters.keys():
        token.payload[key] = parameters[key]

    return token


def authenticate_response(user: "User"):
    try:
        token = CustomTokenObtainPairSerializer.get_token(user, user)
        refresh_token = token
        access_token = token.access_token
        subscription = get_token_subscription_for_user(user)
        access_token = set_token_parameters(
            access_token,
            {
                "subscription": (
                    subscription.safe_json() if subscription is not None else None
                ),
                "locale_code": user.locale.code,
            },
        )

        update_last_login(None, user)

        validation = {
            "access": str(access_token),
            "refresh": str(refresh_token),
            "user": user.to_dict(exclude=["phone", "products"]),
        }
        return validation
    except ObjectDoesNotExist:
        raise CustomException.authentication_error(
            title=_("Invalid login credentials"),
            detail=_("Invalid login credentials"),
        )


def authenticate_user(user: "User", password: str):
    if not user.check_password(password):
        raise CustomException.authentication_error(
            title=_("Invalid login credentials"),
            detail=_("Invalid login credentials"),
        )
    return authenticate_response(user)


def social_auth_authenticate_user(user: "User"):
    return authenticate_response(user)
