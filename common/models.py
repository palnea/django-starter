from typing import Dict, List

import pycountry
from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models, transaction
from django.db.models import Q, Subquery, F, Prefetch
from django.utils.translation import gettext_lazy as _
from django_softdelete.models import SoftDeleteManager, SoftDeleteModel

from cloud_storage.constants.file_upload_constants import (
    get_storage_bucket,
    get_content_type_from_extension,
)
from cloud_storage.get_cloud_storage_client import (
    get_cloud_storage_client,
    get_cloud_storage_vendor,
)
from cloud_storage.idrive_client import CloudRequest
from common.types import FileType
from utils.converters import ModelConverter
from common.fields import DateTimeWithoutTZField


def validate_ietf_code(value):
    from langcodes import Language  # Import here to avoid circular imports

    try:
        # Attempt to create a Language object for the code
        Language.get(value)
    except LookupError:
        raise ValidationError(
            _("%(value)s is not a valid IETF language code."),
            params={"value": value},
        )


class Locale(models.Model):
    name = models.CharField(max_length=150, blank=False, null=False, unique=True)
    code = models.CharField(
        max_length=16,
        blank=False,
        null=False,
        unique=True,
        default="tr-TR",
    )
    territory = models.CharField(
        max_length=2,
        choices=[(country.alpha_2, country.name) for country in pycountry.countries],
        verbose_name=_("Territory"),
        default="TR",
    )
    date_format = models.CharField(
        max_length=10, verbose_name=_("Date Format"), default="DD/MM/YYYY"
    )
    time_format = models.CharField(
        max_length=3, verbose_name=_("Time Format"), default="24h"
    )
    currency_code = models.CharField(
        max_length=3, verbose_name=_("Default Currency"), default="TRY"
    )
    charset = models.CharField(
        max_length=25, default="UTF-8", verbose_name=_("Character Encoding")
    )
    direction = models.CharField(
        max_length=3, verbose_name=_("Writing Direction"), default="ltr"
    )
    created = DateTimeWithoutTZField(auto_now_add=True, editable=False, null=True)
    updated = DateTimeWithoutTZField(auto_now=True, editable=False, null=True)

    class Meta:
        db_table = "locale"

    def __str__(self):
        return f"{self.code} ({self.name})"

    def clean_fields(self, exclude=None):
        """Custom validation to ensure IETF code before saving the model."""
        super().clean_fields(exclude=exclude)
        validate_ietf_code(self.code)

    def save(self, *args, **kwargs):
        """Override save method to perform custom validation before saving."""
        self.full_clean()  # Call clean_fields for validation
        super().save(*args, **kwargs)

    @classmethod
    def get_default(cls) -> "Locale":
        locale, created = cls.objects.get_or_create(
            code="tr-TR",
            defaults={
                "name": "Turkish (Türkiye)",
                "territory": "TR",
                "date_format": "DD/MM/YYYY",
                "time_format": "24h",
                "currency_code": "TRY",
            },
        )
        return locale

    @classmethod
    def get_default_english(cls) -> "Locale":
        locale, created = cls.objects.get_or_create(
            code="en-US",
            defaults={
                "name": "English (USA)",
                "territory": "US",
                "date_format": "MM/DD/YYYY",
                "time_format": "12h",
                "currency_code": "USD",
            },
        )
        return locale


class TranslationManager(SoftDeleteManager):
    def get_queryset(self):
        return super(TranslationManager, self).get_queryset().select_related("root")


class Translation(SoftDeleteModel):
    text = models.CharField(max_length=512, null=False, blank=False)
    root = models.ForeignKey(
        "self",
        on_delete=models.SET_NULL,
        related_name="translations",
        null=True,
        blank=True,
    )
    locale = models.ForeignKey(
        Locale,
        on_delete=models.CASCADE,
        related_name="translations",
        null=True,
        blank=True,
    )
    created = DateTimeWithoutTZField(auto_now_add=True, editable=False)
    updated = DateTimeWithoutTZField(auto_now=True, editable=False)
    deleted_at = DateTimeWithoutTZField(blank=True, null=True)

    class Meta:
        db_table = "translation"
        constraints = [
            models.UniqueConstraint(
                fields=["root", "locale"],
                condition=Q(deleted_at__isnull=True),
                name="unique_root_id_locale_id_if_not_deleted",
            ),
        ]

    @transaction.atomic
    def delete(self, using=None, keep_parents=False):
        if self.root_id is None or self.root_id == self.id:
            # Delete all translations that have the current instance as root
            # except the current instance itself to avoid recursion
            self.translations.exclude(id=self.id).delete()

        super(Translation, self).delete(using=using, keep_parents=keep_parents)

    @transaction.atomic
    def save(
        self, force_insert=False, force_update=False, using=None, update_fields=None
    ):
        is_create = not bool(self.id)
        if self.locale_id is None:
            self.locale = Locale.get_default()
        super().save(force_insert, force_update, using, update_fields)
        if is_create and self.root_id is None:
            self.root_id = self.id
            self.save()

    def get_text_by_locale_code_or_default(self, locale_code: str) -> str:
        original_translation = self.root
        translation = (
            original_translation.translations.filter(locale__code=locale_code).first()
            or original_translation.translations.filter(locale__code="en").first()
            or original_translation.translations.first()
        )
        return translation.text if translation else ""

    @staticmethod
    def get_list_of_texts_from_id_list(
        translation_ids: List, locale_code: str
    ) -> Dict[int, str]:
        """Returns translated texts of given inputs."""
        translation_text_match = {}

        def update_translation_match(root_id: int, id: int, text: str):
            translation_text_match.update({root_id: text, id: text})

        root_ids = (
            Translation.objects.filter(id__in=translation_ids)
            .values_list("root_id", flat=True)
            .all()
        )
        translations = Translation.objects.filter(
            root_id__in=Subquery(root_ids), locale__code=locale_code
        )
        for translation in translations:
            update_translation_match(
                translation.root_id, translation.id, translation.text
            )
        missing_translation_ids = [
            translation_id
            for translation_id in translation_ids
            if translation_text_match.get(translation_id, None) is None
        ]
        missing_translations = Translation.objects.filter(
            id__in=missing_translation_ids
        ).select_related("root")
        for missing_translation in missing_translations:
            translation_text_match.update(
                {missing_translation.id: missing_translation.root.text}
            )
        return translation_text_match

    @staticmethod
    def create_prefetch_for_language(language_code, field_route, **kwargs) -> Prefetch:
        translations = Translation.objects.filter(locale__code=language_code)
        return Prefetch(field_route, queryset=translations)


class TranslatedFile(SoftDeleteModel):
    name = models.CharField(max_length=255, blank=False, null=True)
    extension = models.CharField(max_length=64, null=False, blank=False)
    vendor_url = models.CharField(
        max_length=255,
        null=False,
        blank=False,
        default=get_cloud_storage_client().endpoint,
    )
    bucket_name = models.CharField(
        max_length=255, null=False, blank=False, default=get_storage_bucket
    )
    directory = models.CharField(
        max_length=2048,
        null=False,
        blank=False,
        default=settings.TRANSLATED_FILE_DIRECTORY,
    )
    type = models.CharField(
        max_length=64, choices=FileType.choices, null=False, blank=False
    )
    vendor = models.CharField(
        max_length=64, null=False, blank=False, default=get_cloud_storage_vendor
    )
    public = models.BooleanField(
        null=False,
        blank=False,
        default=True,
    )
    root = models.ForeignKey(
        "self",
        on_delete=models.SET_NULL,
        related_name="translations",
        null=True,
        blank=True,
    )
    locale = models.ForeignKey(
        Locale,
        on_delete=models.CASCADE,
        related_name="translated_files",
        null=True,
        blank=True,
    )
    created = DateTimeWithoutTZField(auto_now_add=True, editable=False)
    updated = DateTimeWithoutTZField(auto_now=True, editable=False)
    deleted_at = DateTimeWithoutTZField(blank=True, null=True)

    class Meta:
        db_table = "translated_file"
        constraints = [
            models.UniqueConstraint(
                fields=["root", "locale"],
                condition=Q(deleted_at__isnull=True),
                name="unique_translated_file_root_id_locale_id_if_not_deleted",
            ),
            models.CheckConstraint(
                check=Q(name__isnull=True) & ~Q(root_id=F("id"))
                | (Q(name__isnull=False) & Q(root_id=F("id"))),
                name="translated_file_not_null_name_if_root",
            ),
        ]

    @transaction.atomic
    def delete(self, using=None, keep_parents=False):
        if self.root_id is None or self.root_id == self.id:
            # Delete all translations that have the current instance as root
            # except the current instance itself to avoid recursion
            self.translations.exclude(id=self.id).delete()

        super(TranslatedFile, self).delete(using=using, keep_parents=keep_parents)

    @transaction.atomic
    def save(
        self, force_insert=False, force_update=False, using=None, update_fields=None
    ):
        is_create = not bool(self.id)
        if self.locale_id is None:
            self.locale = Locale.get_default()
        super().save(force_insert, force_update, using, update_fields)
        if is_create and self.root_id is None:
            self.root_id = self.id
            self.save()

    @property
    def url(self):
        if self.public:
            return f"{self.vendor_url}/{self.bucket_name}/{self.file_path}"
        client = get_cloud_storage_client(self.vendor, self.vendor_url)
        return client.create_presigned_url(str(self.bucket_name), str(self.file_path))

    @property
    def file_path(self):
        return f"{self.directory}{self.id}.{self.extension}"

    def get_upload_url(self, expiration: int = None):
        client = get_cloud_storage_client(self.vendor, self.vendor_url)
        if not self.public:
            return client.create_presigned_url(
                str(self.bucket_name),
                str(self.file_path),
                expiration,
                CloudRequest.Upload,
                content_type=get_content_type_from_extension(self.extension),
            )
        else:
            return client.create_presigned_url(
                str(self.bucket_name),
                str(self.file_path),
                None,
                CloudRequest.Upload,
                content_type=get_content_type_from_extension(self.extension),
            )

    def to_dict(self):
        page_file_dict = ModelConverter.model_to_dict(self)
        page_file_dict["url"] = self.url
        return page_file_dict

    @staticmethod
    def get_list_of_urls_from_id_list(
        translation_ids: List, locale_code: str
    ) -> Dict[int, str]:
        """Returns translated texts of given inputs."""
        translation_url_match = {}

        def update_translation_match(root_id: int, id: int, url: str):
            translation_url_match.update({root_id: url, id: url})

        root_ids = (
            TranslatedFile.objects.filter(id__in=translation_ids)
            .values_list("root_id", flat=True)
            .all()
        )
        translations = TranslatedFile.objects.filter(
            root_id__in=Subquery(root_ids), locale__code=locale_code
        )
        for translation in translations:
            update_translation_match(
                translation.root_id, translation.id, translation.url
            )
        missing_translation_ids = [
            translation_id
            for translation_id in translation_ids
            if translation_url_match.get(translation_id, None) is None
        ]
        missing_translations = TranslatedFile.objects.filter(
            id__in=missing_translation_ids
        ).select_related("root")
        for missing_translation in missing_translations:
            translation_url_match.update(
                {missing_translation.id: missing_translation.root.url}
            )
        return translation_url_match
