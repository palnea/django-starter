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
    def create_contact_verification(data, send_code: bool = True):
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
            )
        )

        if send_code:
            contact_verification.send_code()
        if contact_verification.status == ContactVerification.Status.FAILED:
            raise CustomException.from_exception(
                Exception("Could not send the verification code"),
                code=ErrorCode.INTERNAL_SERVER_ERROR,
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )
        content = {"id": contact_verification.id}
        return content, (
            _("Code is sent. Check your email.")
            if medium == CommunicationMedium.EMAIL
            else _("Code is sent. Check your messages.")
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
            raise CustomException(
                detail={"code": ["Code is invalid or expired"]},
                code=ErrorCode.GENERAL_VALIDATION_ERROR,
                status_code=status.HTTP_400_BAD_REQUEST,
                message=_("Code is invalid or expired"),
            )

        user = (
            User.objects.filter(email=email).first()
            if email
            else User.objects.filter(phone=phone).first()
        )
        if email:
            user.email_verified = True
        elif phone:
            user.phone_verified = True
        user.save()

        account = user.account
        account.is_active = True
        account.save()
