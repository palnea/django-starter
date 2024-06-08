from phonenumber_field.serializerfields import PhoneNumberField
from rest_framework import serializers, status
from django.utils.translation import gettext_lazy as _

from common.custom_exceptions.custom_exception import CustomException
from common.response.response_information_codes.error_code import ErrorCode
from communications.services import CommunicationMedium


class ContactVerificationSerializer(serializers.Serializer):
    email = serializers.EmailField(required=False)
    phone = PhoneNumberField(required=False)

    def validate(self, attrs):
        email = attrs.get("email", None)
        phone = attrs.get("phone", None)

        if email is None and phone is None:
            raise CustomException(
                detail={
                    "email": ["Email should be provided if phone is empty"],
                    "phone": ["Phone should be provided if email is empty"],
                },
                code=ErrorCode.GENERAL_VALIDATION_ERROR,
                status_code=status.HTTP_400_BAD_REQUEST,
                message=_("Email or phone should be provided"),
            )

        if email is not None and phone is not None:
            raise CustomException(
                detail={
                    "email": ["Email should be empty if phone is provided"],
                    "phone": ["Phone should be empty if email is provided"],
                },
                code=ErrorCode.GENERAL_VALIDATION_ERROR,
                status_code=status.HTTP_400_BAD_REQUEST,
                message=_("Enter email or phone not both"),
            )

        validated_data = {}

        if email:
            validated_data.update(
                {"receiver_address": email, "medium": CommunicationMedium.EMAIL.value}
            )
        if phone:
            validated_data.update(
                {
                    "receiver_address": phone.as_international.replace(" ", ""),
                    "medium": CommunicationMedium.PHONE.value,
                }
            )

        return validated_data


class CodeVerificationSerializer(serializers.Serializer):
    code = serializers.CharField(required=False)
