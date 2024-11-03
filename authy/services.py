from typing import Dict

from django.conf import settings
from django.db import transaction
from django.utils.translation import gettext_lazy as _
from rest_framework import status

from authy.helpers.token_helper import (
    authenticate_user,
)
from authy.models import Account
from common.custom_exceptions.custom_exception import CustomException
from common.response.response_information_codes.error_code import ErrorCode
from communications.clients.email import DjangoEmailClient
from communications.clients.sms import get_sms_client
from communications.services.communication_services import EmailService, SMSService
from contact_verification.services import ContactVerificationService
from user.models import User
from utils.generators import random_numeric_string


class RegistrationService:
    @staticmethod
    @transaction.atomic
    def register(data):
        # Create account
        account = Account.objects.create()
        account.set_password(data["password"])
        account.save()

        # Create user
        user_data = {
            x: data[x]
            for x in data
            if x not in ["password", "verify_password", "reference_code"]
        }
        user = User.objects.create(
            **user_data,
            account=account,
        )

        # Authenticate
        validation = authenticate_user(user, data["password"])

        try:
            if user.email:
                code = ContactVerificationService.create_contact_verification(
                    {"receiver_address": data.get("email"), "medium": "email"},
                    send_code=False,
                )
                EmailService(DjangoEmailClient()).send_async(
                    [user.email],
                    _("email verification message").format(code=code),
                    _("Email Verification Code"),
                    from_email=settings.EMAIL_HOST_USER,
                )
            elif user.phone:
                code = ContactVerificationService.create_contact_verification(
                    {"receiver_address": data.get("phone"), "medium": "phone"},
                    send_code=False,
                )
                SMSService(get_sms_client()).send(
                    [user.phone.as_international.replace(" ", "").replace("+", "00")],
                    _("phone verification message").format(code=code),
                    settings.SMS_HEADER,
                )
        except Exception as e:
            pass

        return {
            **validation,
            "phone": user.phone_as_international,
        }


class PasswordService:
    @staticmethod
    @transaction.atomic
    def reset_password(data: Dict):
        email = data.get("email", None)
        phone = data.get("phone", None)

        if not email and not phone:
            raise CustomException(
                detail={
                    "email": "Cannot be null if phone is null",
                    "phone": "Cannot be null if email is null",
                },
                code=ErrorCode.INVALID_INPUT,
                status_code=status.HTTP_400_BAD_REQUEST,
                message=_("Email or phone should be provided"),
            )

        if email and phone:
            raise CustomException(
                detail={"error": "Email and phone cannot be provided at the same time"},
                code=ErrorCode.INVALID_INPUT,
                status_code=status.HTTP_400_BAD_REQUEST,
                message=_("Enter email or phone not both"),
            )

        user = (
            User.objects.filter(email=email).first()
            if email
            else User.objects.filter(phone=phone).first()
        )
        if not user:
            raise CustomException(
                detail={"error": "User not found"},
                code=ErrorCode.NOT_FOUND_ERROR,
                status_code=status.HTTP_404_NOT_FOUND,
            )

        account = user.account
        password = random_numeric_string(6)

        account.set_password(password)
        account.save()

        if data.get("email"):
            EmailService(DjangoEmailClient()).send_async(
                [user.email],
                _("Reset password email message").format(password=password),
                _("Reset password title"),
                from_email=settings.EMAIL_HOST_USER,
            )
        elif data.get("phone"):
            SMSService(get_sms_client()).send(
                [user.phone.as_international.replace(" ", "").replace("+", "00")],
                _("Reset password sms message").format(password=password),
                settings.SMS_HEADER,
            )
        return
