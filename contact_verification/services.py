from typing import Dict

from django.conf import settings
from django.db import transaction
from django.utils.translation import gettext_lazy as _
from rest_framework import status

from common.custom_exceptions.custom_exception import CustomException
from common.response.response_information_codes.error_code import ErrorCode
from communications.services import CommunicationMedium
from contact_verification.models import ContactVerification
from user.models import User


class ContactVerificationService:
    @staticmethod
    @transaction.atomic
    def create_contact_verification(
        data,
        send_code: bool = True,
        language_code: str = "en",
        user=None,
    ) -> (Dict, str, ContactVerification):
        medium = CommunicationMedium(data.get("medium", None))
        if not medium:
            raise CustomException.from_exception(
                Exception(
                    "You should provide a medium to send the code. (ie. email, phone)"
                ),
                code=ErrorCode.INTERNAL_SERVER_ERROR,
                status_code=status.HTTP_400_BAD_REQUEST,
            )

        contact_verification = ContactVerification.objects.create(
            **data,
            valid_interval_in_seconds=(
                settings.EMAIL_VERIFICATION_ACTIVE_INTERVAL
                if medium == CommunicationMedium.EMAIL
                else settings.PHONE_VERIFICATION_ACTIVE_INTERVAL
            ),
        )

        if send_code:
            contact_verification.send_code(language_code=language_code, user=user)
        if contact_verification.status == ContactVerification.Status.FAILED:
            raise CustomException.from_exception(
                Exception("Could not send the verification code"),
                code=ErrorCode.INTERNAL_SERVER_ERROR,
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )
        content = {"id": contact_verification.id}
        return (
            content,
            (
                _("Code is sent. Check your email.")
                if medium == CommunicationMedium.EMAIL
                else _("Code is sent. Check your messages.")
            ),
            contact_verification,
        )

    @staticmethod
    @transaction.atomic
    def verify_contact(validated_data: Dict) -> None:
        """Verifies a contact verification code. Raises CustomException if verification fails."""
        code = validated_data.get("code")
        uuid = validated_data.get("uuid")

        contact_verification = ContactVerification.objects.filter(id=uuid).first()
        if not contact_verification:
            raise CustomException.validation_error(
                field_errors={"uuid": [_("UUID is invalid")]},
                title=_("Please request a new code"),
                status_code=status.HTTP_400_BAD_REQUEST,
            )

        if not contact_verification.is_valid:
            raise CustomException.validation_error(
                field_errors={"code": [_("Code is invalid or expired")]},
                title=_("Code is invalid or expired"),
                status_code=status.HTTP_400_BAD_REQUEST,
            )

        if contact_verification.attempts >= settings.MAX_VERIFICATION_ATTEMPTS:
            contact_verification.status = ContactVerification.Status.FAILED
            contact_verification.save(update_fields=["status"])
            raise CustomException.validation_error(
                field_errors={"attempts": [_("Exceeded limit of attempts")]},
                title=_("You entered the wrong code too many times"),
                status_code=status.HTTP_400_BAD_REQUEST,
            )

        if contact_verification.code != code:
            contact_verification.attempts += 1
            contact_verification.status = ContactVerification.Status.FAILED
            contact_verification.save(update_fields=["status", "attempts"])
            raise CustomException.validation_error(
                field_errors={"code": [_("Code is incorrect")]},
                title=_("Code is incorrect"),
                status_code=status.HTTP_400_BAD_REQUEST,
            )

        contact_verification.status = ContactVerification.Status.VERIFIED
        contact_verification.save(update_fields=["status"])

        CodeVerificationService.verify_user_contact(
            email=(
                contact_verification.receiver_address
                if contact_verification.medium == CommunicationMedium.EMAIL
                else None
            ),
            phone=(
                contact_verification.receiver_address
                if contact_verification.medium == CommunicationMedium.PHONE
                else None
            ),
        )


class CodeVerificationService:
    @staticmethod
    @transaction.atomic
    def verify_code(code: str, email: str = None, phone: str = None):
        contact_verification = ContactVerification.objects.filter(
            code=code, receiver_address=email or phone
        ).order_by("-id")
        if (
            not contact_verification.exists()
            or not contact_verification.first().is_valid
        ):
            raise CustomException.validation_error(
                field_errors={"code": [_("Code is invalid or expired")]},
                title=_("Code is invalid or expired"),
                status_code=status.HTTP_400_BAD_REQUEST,
            )

        CodeVerificationService.verify_user_contact(email=email, phone=phone)

    @staticmethod
    def verify_user_contact(email: str = None, phone: str = None):
        user = (
            User.objects.filter(email=email).first()
            if email
            else User.objects.filter(phone=phone).first()
        )
        if not user:
            raise CustomException.not_found_error(
                title=_("User not found"),
                detail=_("User not found") + f" {email or phone}",
            )

        if email:
            user.email_verified = True
        elif phone:
            user.phone_verified = True
        user.is_active = True
        user.save()
