from typing import Dict, List

from rest_framework import serializers, status
from django.utils.translation import gettext_lazy as _

from common.custom_exceptions.custom_exception import CustomException
from common.models import Translation, TranslatedFile
from common.response.response_information_codes.error_code import ErrorCode
from common.types import FileType
from common.models import Locale


class TranslationBulkCreateItemSerializer(serializers.Serializer):
    locale_id = serializers.IntegerField(required=True)
    text = serializers.CharField(required=True)


class TranslationBulkCreateSerializer(serializers.Serializer):
    root = TranslationBulkCreateItemSerializer(required=True)
    translations = serializers.ListSerializer(
        child=TranslationBulkCreateItemSerializer(), required=True
    )

    def validate(self, attrs) -> List[Dict]:
        super().validate(attrs)
        english_locale = Locale.objects.filter(code="en").first()
        if not english_locale:
            raise CustomException(
                detail={
                    "locale": "The locale that refers to English language doesn't exist. Please create a locale with 'en' code first!"
                },
                message=_(
                    "The locale that refers to English language doesn't exist. Please create a locale with 'en' code first!"
                ),
            )
        if not attrs.get("root").get("locale_id") == english_locale.id:
            raise CustomException(
                detail={
                    "locale_id": f"Root object locale id must be {english_locale.id} which refers to English language"
                },
                message=_(
                    "Root object locale id must be {} which refers to English language"
                ).format(english_locale.id),
            )

        return attrs


class TranslationListItemSerializer(serializers.ModelSerializer):
    class Meta:
        model = Translation
        fields = "__all__"


class TranslationSerializer(serializers.ModelSerializer):
    root_id = serializers.IntegerField(required=False)
    translations = serializers.ListSerializer(
        child=TranslationListItemSerializer(), read_only=True
    )

    class Meta:
        model = Translation
        fields = "__all__"
        read_only_fields = ("root",)

    def validate(self, attrs):
        validated_data = super().validate(attrs)
        root_id = attrs.get("root_id", None)
        locale = attrs.get("locale", None)
        if self.context["request"].method == "POST":
            if root_id is None and (not locale or locale.code != "en"):
                raise CustomException(
                    detail={
                        "locale": "If this is the first time to create a translation it should be in English"
                    },
                    code=ErrorCode.GENERAL_VALIDATION_ERROR,
                    status_code=status.HTTP_400_BAD_REQUEST,
                    message=_(
                        "If this is the first time to create a translation it should be in English"
                    ),
                )
        return validated_data


class TranslatedFileBulkCreateItemSerializer(serializers.Serializer):
    locale_id = serializers.IntegerField(required=True)
    extension = serializers.CharField(required=True)
    type = serializers.ChoiceField(choices=FileType.choices)


class TranslatedFileBulkCreateSerializer(serializers.Serializer):
    root = TranslatedFileBulkCreateItemSerializer(required=True)
    translations = serializers.ListSerializer(
        child=TranslatedFileBulkCreateItemSerializer(), required=True
    )
    name = serializers.CharField(required=True)

    def validate(self, attrs) -> List[Dict]:
        super().validate(attrs)
        english_locale = Locale.objects.filter(code="en").first()
        if not english_locale:
            raise CustomException(
                detail={
                    "locale": "The locale that refers to English language doesn't exist. Please create a locale with 'en' code first!"
                },
                message=_(
                    "The locale that refers to English language doesn't exist. Please create a locale with 'en' code first!"
                ),
            )
        if not attrs.get("root").get("locale_id") == english_locale.id:
            raise CustomException(
                detail={
                    "locale_id": f"Root object locale id must be {english_locale.id} which refers to English language"
                },
                message=_(
                    "Root object locale id must be {} which refers to English language"
                ).format(english_locale.id),
            )

        return attrs


class TranslatedFileListItemSerializer(serializers.ModelSerializer):
    class Meta:
        model = TranslatedFile
        fields = "__all__"


class TranslatedFileSerializer(serializers.ModelSerializer):
    root_id = serializers.IntegerField(required=False)
    translations = serializers.ListSerializer(
        child=TranslatedFileListItemSerializer(), read_only=True
    )
    url = serializers.SerializerMethodField(read_only=True)
    presigned_url = serializers.SerializerMethodField(read_only=True)

    class Meta:
        model = TranslatedFile
        fields = "__all__"
        read_only_fields = ("root", "vendor", "public", "directory", "bucket_name")

    def validate(self, attrs):
        validated_data = super().validate(attrs)
        root_id = attrs.get("root_id", None)
        locale = attrs.get("locale", None)
        if self.context["request"].method == "POST":
            if root_id is None and (not locale or locale.code != "en"):
                raise CustomException(
                    detail={
                        "locale": "If this is the first time to create a translation it should be in English"
                    },
                    code=ErrorCode.GENERAL_VALIDATION_ERROR,
                    status_code=status.HTTP_400_BAD_REQUEST,
                    message=_(
                        "If this is the first time to create a translation it should be in English"
                    ),
                )
        return validated_data

    def get_url(self, translated_file: TranslatedFile):
        return translated_file.url

    def get_presigned_url(self, translated_file: TranslatedFile):
        if self.context["request"].method in ["POST", "PUT", "PATCH"]:
            return translated_file.get_upload_url(3600)


class LocaleSerializer(serializers.ModelSerializer):
    class Meta:
        model = Locale
        fields = "__all__"
