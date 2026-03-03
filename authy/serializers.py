import time
from typing import Dict, Union

import jwt
from django.conf import settings
from django.contrib.auth import authenticate
from django.utils.translation import gettext_lazy as _
from phonenumber_field.serializerfields import PhoneNumberField
from rest_framework import serializers, status
from rest_framework_simplejwt.tokens import RefreshToken, Token
from structlog import get_logger

from authy.helpers.social_auth import login_social_user
from authy.helpers.token_helper import (
    get_token_subscription_for_user,
    authenticate_user,
)
from authy.social_auth.apple import Apple
from authy.social_auth.facebook import Facebook
from authy.social_auth.google import Google
from common.custom_exceptions.custom_exception import CustomException
from common.response.response_information_codes.error_code import ErrorCode
from contact_verification.services import ContactVerificationService
from subscription.models import UserSubscription
from user.models import User

log = get_logger(__name__)


class UserLoginSerializer(serializers.Serializer):
    email = serializers.CharField(
        max_length=254, allow_null=True, allow_blank=True, required=False
    )
    phone = PhoneNumberField(required=False, allow_null=True, allow_blank=True)
    password = serializers.CharField(max_length=128, write_only=True)
    verification_id = serializers.CharField(required=False, max_length=64)
    verification_code = serializers.CharField(required=False, max_length=8)
    access = serializers.CharField(read_only=True)
    refresh = serializers.CharField(read_only=True)
    role = serializers.CharField(read_only=True)

    def create(self, validated_date):
        pass

    def update(self, instance, validated_data):
        pass

    def validate(self, data):
        email = data.get("email", None)
        phone = data.get("phone", None)

        if email:
            email = email.strip().lower()

        if not email and not phone:
            # New structured error format - provides better field-based errors
            raise CustomException.validation_error(
                field_errors={
                    "email": [_("Cannot be empty if no phone provided")],
                    "phone": [_("Cannot be empty if no email provided")],
                },
                title=_("Contact Information Required"),
                instance="/api/v1/auth/login",
            )

        if email and phone:
            # New structured error format - provides better field-based errors
            raise CustomException.validation_error(
                field_errors={
                    "email": [_("Should not be provided if phone provided")],
                    "phone": [_("Should not be provided if email provided")],
                },
                title=_("Only One Contact Method Allowed"),
                instance="/api/v1/auth/login",
            )

        if data.get("verification_code") and data.get("verification_id"):
            ContactVerificationService.verify_contact(
                {"code": data["verification_code"], "uuid": data["verification_id"]}
            )

        password = data["password"]
        user = (
            User.objects.filter(email=email).select_related("locale").first()
            if email
            else User.objects.filter(phone=phone).select_related("locale").first()
        )

        if user is None:
            field_name = "email" if email else "phone"
            error_message = (
                _("User with this email doesn't exist")
                if email
                else _("User with this phone doesn't exist")
            )
            raise CustomException.validation_error(
                field_errors={field_name: [str(error_message)]},
                title=_("User Not Found"),
                instance="/api/v1/auth/login",
                status_code=status.HTTP_404_NOT_FOUND,
            )

        if email and not user.email_verified:
            raise CustomException.validation_error(
                field_errors={"email": [_("Email is not verified")]},
                title=_("Email Verification Required"),
                instance="/api/v1/auth/login",
            )

        if phone and not user.phone_verified:
            raise CustomException.validation_error(
                field_errors={"phone": [_("Phone is not verified")]},
                title=_("Phone Verification Required"),
                instance="/api/v1/auth/login",
            )

        return authenticate_user(user, password)


class UserRegisterSerializer(serializers.Serializer):
    phone = PhoneNumberField(allow_null=True, allow_blank=True, required=False)
    email = serializers.CharField(
        max_length=254, required=False, allow_blank=True, allow_null=True
    )
    password = serializers.CharField(max_length=128, write_only=True, required=True)
    verify_password = serializers.CharField(
        max_length=128, write_only=True, required=True
    )

    def create(self, validated_date):
        pass

    def update(self, instance, validated_data):
        pass

    def validate(self, data):
        email = data.get("email", None)
        phone = data.get("phone", None)
        password = data.get("password")
        verify_password = data.get("verify_password")

        if not email and not phone:
            raise CustomException.validation_error(
                field_errors={
                    "email": [_("Cannot be empty if no phone provided")],
                    "phone": [_("Cannot be empty if no email provided")],
                },
                title=_("Contact Information Required"),
                instance="/api/v1/auth/register",
            )

        if not password == verify_password:
            raise CustomException.validation_error(
                field_errors={"verify_password": [_("Password doesn't match")]},
                title=_("Password Mismatch"),
                instance="/api/v1/auth/register",
            )

        validation = {
            "phone": str(data.get("phone")) if data.get("phone") else None,
            "email": data.get("email").lower().strip() if data.get("email") else None,
            "password": data.get("password"),
        }

        return validation


class ResetPasswordSerializer(serializers.Serializer):
    email = serializers.EmailField(allow_null=True, allow_blank=True, required=False)
    phone = serializers.CharField(allow_null=True, allow_blank=True, required=False)


class UpdatePasswordSerializer(serializers.Serializer):
    old_password = serializers.CharField(required=True)
    new_password = serializers.CharField(required=True)
    confirm_password = serializers.CharField(required=True)

    def validate(self, attrs):
        old_password = attrs.get("old_password")
        new_password = attrs.get("new_password")
        confirm_password = attrs.get("confirm_password")
        request = self.context.get("request", None)
        if request is None:
            raise CustomException.from_exception(
                Exception("Request could not be gotten"),
                code=ErrorCode.INTERNAL_SERVER_ERROR,
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )
        user = request.user if request else None

        authenticated_user = authenticate(email=user.email, password=old_password)
        errors = {}
        if not authenticated_user:
            errors.update({"old_password": ["Password is incorrect!"]})

        if new_password != confirm_password:
            errors.update({"confirm_password": ["Given passwords doesn't match"]})

        if errors:
            raise CustomException.validation_error(
                field_errors=errors,
                title=_("Password Change Failed"),
                instance="/api/v1/auth/change-password",
            )

        user.set_password(new_password)
        user.save()
        return {}


class CustomTokenRefreshSerializer(serializers.Serializer):
    refresh = serializers.CharField()
    access = serializers.CharField(read_only=True)
    token_class = RefreshToken

    def validate(self, attrs):
        refresh = self.token_class(attrs["refresh"])
        access_token = refresh.access_token
        subscription = self.get_user_subscription_from_token(access_token)
        access_token = self.set_token_parameters(
            access_token,
            {
                "subscription": (
                    subscription.safe_json() if subscription is not None else None
                ),
                "locale_code": access_token.payload.get("locale_code"),
            },
        )

        data = {"access": str(access_token)}

        if settings.SIMPLE_JWT["ROTATE_REFRESH_TOKENS"]:
            if settings.SIMPLE_JWT["BLACKLIST_AFTER_ROTATION"]:
                try:
                    # Attempt to blacklist the given refresh token
                    refresh.blacklist()
                except AttributeError:
                    # If blacklist app not installed, `blacklist` method will
                    # not be present
                    pass

            refresh.set_jti()
            refresh.set_exp()
            refresh.set_iat()

            data["refresh"] = str(refresh)

        return data

    def set_token_parameters(self, token: Token, parameters: Dict[str, any]) -> Token:
        for key in parameters.keys():
            token.payload[key] = parameters[key]

        return token

    def get_user_subscription_from_token(
        self, token: Token
    ) -> Union[UserSubscription, None]:
        payload = token.payload
        user_id = payload.get("user_id", None)
        if user_id is not None:
            user = User.objects.get(pk=user_id)
            return get_token_subscription_for_user(user)

        else:
            return None


class GoogleSocialAuthSerializer(serializers.Serializer):
    auth_token = serializers.CharField()

    def validate_auth_token(self, auth_token):
        user_data = Google.validate(auth_token)
        request = self.context.get("request", None)
        contact_permission = False
        if request and request.data:
            contact_permission = request.data.get("contact_permission", False)
        try:
            user_data["sub"]
        except Exception:
            raise serializers.ValidationError(
                "The token is invalid or expired. Please login again."
            )

        if user_data["aud"] != settings.GOOGLE_CLIENT_ID:
            raise CustomException.authentication_error(
                title=_("Google Authentication Failed"),
                detail=_(
                    "Google client ID doesn't match with system's client ID. Please try logging in again."
                ),
                instance="/api/v1/auth/google",
            )

        try:
            user_id = user_data["sub"]
            email = user_data["email"]
            name = user_data["name"]
            provider = "google"

            return login_social_user(
                provider=provider,
                user_id=user_id,
                email=email,
                name=name,
                contact_permission=contact_permission,
            )
        except Exception as exp:
            log.warning("Google authentication failed", exception=exp)
            raise serializers.ValidationError(
                "The token  is invalid or expired. Please login again."
            )


class FacebookSocialAuthSerializer(serializers.Serializer):
    """Handles serialization of facebook related data."""

    auth_token = serializers.CharField()

    def validate_auth_token(self, auth_token):
        user_data = Facebook.validate(auth_token)
        request = self.context.get("request", None)
        contact_permission = False
        if request and request.data:
            contact_permission = request.data.get("contact_permission", False)

        try:
            user_id = user_data["id"]
            email = user_data["email"]
            name = user_data["name"]
            provider = "facebook"
            return login_social_user(
                provider=provider,
                user_id=user_id,
                email=email,
                name=name,
                contact_permission=contact_permission,
            )
        except Exception as exp:
            log.warning("Facebook authentication failed", exception=exp)
            raise serializers.ValidationError(
                "The token  is invalid or expired. Please login again."
            )


class AppleSocialAuthSerializer(serializers.Serializer):
    """Handles serialization of apple related data."""

    auth_token = serializers.CharField()
    code = serializers.CharField()

    def validate_code(self, code):
        user_data = Apple.validate(code)
        request = self.context.get("request", None)
        contact_permission = False
        if request and request.data:
            contact_permission = request.data.get("contact_permission", False)

        try:
            user_id = None
            email = user_data["email"]
            provider = "apple"
            return login_social_user(
                provider=provider,
                user_id=user_id,
                email=email,
                name=None,
                contact_permission=contact_permission,
            )
        except Exception as exp:
            log.warning("Apple authentication failed", exception=exp)
            raise serializers.ValidationError(
                "The token  is invalid or expired. Please login again."
            )

    def validate_auth_token(self, auth_token):
        # Decode the Apple Sign In JWT token without signature verification (PyJWT does not support ES256)
        decoded_token = jwt.decode(
            auth_token, algorithms=["RS256"], options={"verify_signature": False}
        )

        iss = decoded_token.get("iss", None)
        aud = decoded_token.get("aud", None)
        exp = decoded_token.get("exp", None)

        if settings.SOCIAL_AUTH_APPLE_ID_URL not in iss:
            raise serializers.ValidationError(
                f"iss is not correct. Given: {iss}, Required: {settings.SOCIAL_AUTH_APPLE_ID_URL}"
            )

        if aud != settings.APPLE_BUNDLE_ID:
            raise serializers.ValidationError(
                f"aud is not correct. Given: {aud}, Required: {settings.APPLE_BUNDLE_ID}"
            )

        if exp is None or exp < time.time():
            raise serializers.ValidationError(
                f"aud is invalid. Given: {exp}, Required: >{time.time()}"
            )
