from typing import Dict

from django.utils.translation import gettext_lazy as _
from rest_framework import status

from common.custom_exceptions.custom_exception import CustomException
from common.response.response_information_codes.error_code import ErrorCode
from user.models import User
from utils.converters import ModelConverter


class UserService:
    @staticmethod
    def update_user(
        data: Dict[str, any], partial: bool = False
    ) -> (Dict[str, any], bool):
        if not data.get("user", None):
            raise CustomException.not_found_error(
                title=_("Content not found!"),
                detail=_("User not found"),
            )

        user: User = data.get("user")

        for key, value in data.items():
            try:
                if hasattr(user, key):
                    user.__setattr__(key, value)
            except Exception as e:
                if not partial:
                    raise e

        user.save()
        return ModelConverter.model_to_dict(
            user, fields=["id", "fullname", "parent_fullname", "role"]
        )
