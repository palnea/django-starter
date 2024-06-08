import time
from typing import Dict, List

from django.conf import settings
from django.db import transaction
from django.utils.translation import gettext_lazy as _
from rest_framework import status

from cloud_storage.idrive_client import IDriveClient
from common.custom_exceptions.custom_exception import CustomException
from common.response.response_information_codes.error_code import ErrorCode
from user.models import Avatar, User
from utils.converters import FileConverter, ModelConverter


class UserService:
    @staticmethod
    def update_user(
        data: Dict[str, any], partial: bool = False
    ) -> (Dict[str, any], bool):
        if not data.get("user", None):
            raise CustomException(
                detail={"user_id": "User not found"},
                code=ErrorCode.NOT_FOUND_ERROR,
                status_code=status.HTTP_404_NOT_FOUND,
                message=_("Content not found!"),
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
            user, fields=["id", "fullname", "parent_fullname", "avatar", "role"]
        )


class AvatarService:
    client = IDriveClient(
        settings.IDRIVE_ENDPOINT_URL,
        settings.IDRIVE_ACCESS_KEY,
        settings.IDRIVE_SECRET_ACCESS_KEY,
    )

    @staticmethod
    def _upload_image(image_data, avatar_id, bucket_name):
        image_file, ext = FileConverter.ImageBase64ToBytes(image_data)
        file_name = settings.AVATAR_FILE_PATH.format(avatar_id=avatar_id, extension=ext)
        return (
            AvatarService.client.upload_file(image_file, file_name, bucket_name),
            file_name,
        )

    @staticmethod
    def _set_avatar_image_url(avatar: Avatar, bucket_name: str, file_name: str):
        expiration = settings.PUBLIC_FILE_EXPIRATION_TIMESTAMP - int(time.time())
        url = AvatarService.client.create_presigned_url(
            bucket_name=bucket_name, file_path=file_name, expiration=expiration
        )
        avatar.image = url
        avatar.save()

    @staticmethod
    @transaction.atomic
    def create_avatar(data) -> Dict[str, any]:
        bucket_name = settings.IDRIVE_BUCKET_NAME
        image = data.get("image")
        avatar = Avatar.objects.create()
        uploaded, filename = AvatarService._upload_image(
            image_data=image, avatar_id=avatar.id, bucket_name=bucket_name
        )
        AvatarService._set_avatar_image_url(
            avatar=avatar, bucket_name=bucket_name, file_name=filename
        )
        avatar_dict = ModelConverter.model_to_dict(avatar)
        return avatar_dict

    @staticmethod
    def list_avatars() -> List[Dict[str, any]]:
        avatars = Avatar.objects.all()
        avatars_dict = ModelConverter.model_queryset_to_dict_queryset(avatars)
        return avatars_dict
