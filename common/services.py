from typing import Dict, List

from django.db import transaction, IntegrityError
from django.utils.translation import gettext_lazy as _
from rest_framework import status

from common.custom_exceptions.custom_exception import CustomException
from common.models import Translation, TranslatedFile
from common.response.response_information_codes.error_code import ErrorCode
from utils.converters import ModelConverter, ValueConverter


class TranslationService:
    @staticmethod
    @transaction.atomic
    def bulk_create(request_data: Dict, query_params: Dict) -> List[Dict]:
        root = request_data.get("root", {})
        translations = request_data.get("translations", [])
        return_existing_one = ValueConverter.str2bool(
            query_params.get("return_existing_one", "False"), empty_is_true=True
        )

        if not root:
            raise CustomException(
                detail={"root": "Root must be provided"},
                code=ErrorCode.GENERAL_VALIDATION_ERROR,
                status_code=status.HTTP_400_BAD_REQUEST,
                message=_("Root must be provided"),
            )

        try:
            root_translation = Translation.objects.create(**root)
        except IntegrityError as e:
            if "unique_locale_id_text_if_not_deleted" in str(e) and return_existing_one:
                root_translation = Translation.objects.filter(
                    locale_id=root.get("locale_id"), text=root.get("text")
                ).first()
                if not root_translation:
                    raise CustomException(
                        detail={"error": "An error occured"},
                        code=ErrorCode.UNKNOWN_ERROR,
                        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                    )
            else:
                raise e

        translation_list = []
        for translation in translations:
            translation_list.append(
                Translation(**translation, root_id=root_translation.id)
            )

        created_translations = []
        if not return_existing_one:
            created_translations = Translation.objects.bulk_create(translation_list)
        else:
            for translation_data in translations:
                try:
                    created_translations.append(
                        Translation.objects.create(
                            **translation_data, root_id=root_translation.id
                        )
                    )
                except IntegrityError as e:
                    if "unique_locale_id_text_if_not_deleted" in str(
                        e
                    ) or "unique_root_id_locale_id_if_not_deleted" in str(e):
                        translation = Translation.objects.filter(
                            locale=translation_data["locale_id"],
                            text=translation_data["text"],
                            root_id=root_translation,
                        ).first()
                        if not translation:
                            raise e
                        created_translations.append(translation)
                    else:
                        raise e
        created_translations = created_translations + [root_translation]
        return [
            ModelConverter.model_to_dict(translation)
            for translation in created_translations
        ]


class TranslatedFileService:
    @staticmethod
    @transaction.atomic
    def bulk_create(request_data: Dict) -> Dict[str, any]:
        upload_urls = {}
        root = request_data.get("root", None)
        translations = request_data.get("translations", None)
        name = request_data.get("name", None)

        if root is None:
            raise CustomException(
                detail={"root": "Root must be provided"},
                code=ErrorCode.GENERAL_VALIDATION_ERROR,
                status_code=status.HTTP_400_BAD_REQUEST,
                message=_("Root must be provided"),
            )

        root_translation = TranslatedFile.objects.create(**root, name=name)
        root_url = root_translation.get_upload_url(14400)  # 4 hours
        upload_urls[root_translation.locale_id] = root_url

        translation_list = []
        for translation in translations:
            translation_list.append(
                TranslatedFile(**translation, root_id=root_translation.id)
            )

        translated_files = TranslatedFile.objects.bulk_create(translation_list)
        for translated_file in translated_files:
            upload_url = translated_file.get_upload_url(14400)  # 4 hours
            upload_urls[translated_file.locale_id] = upload_url

        return {
            "upload_urls": upload_urls,
            "root_id": root_translation.id,
            "name": root_translation.name,
        }
