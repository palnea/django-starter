from typing import Dict

from common.custom_exceptions.custom_exception import CustomException
from common.response.response_information_codes.error_code import ErrorCode
from communications.clients.sms import get_sms_client
from communications.services.communication_services import EmailService, SMSService
from contact_verification.services import ContactVerificationService
from django.conf import settings
from django.db import transaction
from django.utils.translation import gettext_lazy as _
from rest_framework import status
from user.models import User
from utils.generators import random_numeric_string


class RegistrationService:
    @staticmethod
    @transaction.atomic
    def register(data, language_code: str = "en", user=None):
        # Create user with password
        user_data = {
            x: data[x]
            for x in data
            if x not in ["password", "verify_password", "reference_code"]
        }
        user = User.create_with_password({**user_data, "password": data["password"]})

        contact_verification_id = None
        try:
            if user.email:
                code, message, contact_verification = (
                    ContactVerificationService.create_contact_verification(
                        {"receiver_address": data.get("email"), "medium": "email"},
                        send_code=False,
                    )
                )
                contact_verification_id = str(code.get("id"))
                contact_verification.send_code(language_code=language_code, user=user)
            elif user.phone:
                code, message, contact_verification = (
                    ContactVerificationService.create_contact_verification(
                        {"receiver_address": data.get("phone"), "medium": "phone"},
                        send_code=False,
                    )
                )
                contact_verification_id = str(code.get("id"))
                contact_verification.send_code(language_code=language_code, user=user)
        except Exception as e:
            raise CustomException.business_logic_error(
                title=_("Could not send the verification code"),
                detail=str(e),
                code=ErrorCode.INTERNAL_SERVER_ERROR,
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )

        return {
            "phone": user.phone_as_international,
            "email": user.email,
            "code_id": contact_verification_id,
        }


class PasswordService:
    @staticmethod
    @transaction.atomic
    def reset_password(data: Dict):
        email = data.get("email", None)
        phone = data.get("phone", None)

        if not email and not phone:
            raise CustomException.validation_error(
                field_errors={
                    "email": [_("Cannot be null if phone is null")],
                    "phone": [_("Cannot be null if email is null")],
                },
                title=_("Email or phone should be provided"),
                status_code=status.HTTP_400_BAD_REQUEST,
            )

        if email and phone:
            raise CustomException.business_logic_error(
                title=_("Enter email or phone not both"),
                detail=_("Email and phone cannot be provided at the same time"),
                code=ErrorCode.INVALID_INPUT,
                status_code=status.HTTP_400_BAD_REQUEST,
            )

        user = (
            User.objects.filter(email=email).first()
            if email
            else User.objects.filter(phone=phone).first()
        )
        if not user:
            raise CustomException.not_found_error(
                title=_("User not found"),
                detail=_("User not found"),
            )

        password = random_numeric_string(6)

        user.set_password(password)
        user.save()

        if data.get("email"):
            EmailService().send_async(
                receivers=[user.email],
                subject=_("Reset password title"),
                message=_("Reset password email message").format(password=password),
                from_email=settings.EMAIL_HOST_USER,
            )
        elif data.get("phone"):
            SMSService(get_sms_client()).send(
                [user.phone.as_international.replace(" ", "").replace("+", "00")],
                _("Reset password sms message").format(password=password),
                settings.SMS_HEADER,
            )
        return
