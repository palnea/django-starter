from django.utils.translation import gettext_lazy as _
from phonenumber_field.serializerfields import PhoneNumberField
from rest_framework import serializers, status

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
            raise CustomException.validation_error(
                field_errors={
                    "email": [_("Email should be provided if phone is empty")],
                    "phone": [_("Phone should be provided if email is empty")],
                },
                title=_("Email or phone should be provided"),
                status_code=status.HTTP_400_BAD_REQUEST,
            )

        if email is not None and phone is not None:
            raise CustomException.validation_error(
                field_errors={
                    "email": [_("Email should be empty if phone is provided")],
                    "phone": [_("Phone should be empty if email is provided")],
                },
                title=_("Enter email or phone not both"),
                status_code=status.HTTP_400_BAD_REQUEST,
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


class VerifyContactSerializer(serializers.Serializer):
    code = serializers.CharField(required=True)
    uuid = serializers.UUIDField(required=True)


class CodeVerificationSerializer(serializers.Serializer):
    code = serializers.CharField(required=False)
