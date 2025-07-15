from typing import Dict

from django.utils.translation import gettext_lazy as _
from rest_framework import status

from common.custom_exceptions.custom_exception import CustomException
from common.response.response_information_codes.error_code import ErrorCode
from utils.validators import BaseValidator


class UserValidator(BaseValidator):

    def __init__(self, data: Dict):
        super().__init__(data)

    def validate_create(self, raise_exception: bool = False) -> (bool, Dict[str, any]):
        errors = []

        email = self._data.get("email", None)
        phone = self._data.get("phone", None)
        password = self._data.get("password", None)
        fullname = self._data.get("fullname", "")

        if email is None and phone is None:
            errors.append("Email or phone should be provided")

        if password is None:
            errors.append("Password should be provided")

        if len(errors) > 0 and raise_exception:
            raise CustomException(
                detail=str(errors),
                code=ErrorCode.GENERAL_VALIDATION_ERROR,
                status_code=status.HTTP_400_BAD_REQUEST,
                message=_("Validation error occured. Please check the fields."),
            )

        validated_data = {"email": email, "phone": phone, "password": password, "fullname": fullname}

        return errors, validated_data
