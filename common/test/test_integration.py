from django.urls import reverse
from mock.mock import patch
from model_bakery import baker
from rest_framework import status

from common.models import Translation, TranslatedFile, Locale
from common.types import FileType
from custom_test.base_test import CustomAPITestCase
from custom_test.mixins import CRUDPermissionTestsMixin


class LocaleViewTestCase(CRUDPermissionTestsMixin, CustomAPITestCase):
    list_url_name = "common:locale-viewset"
    detail_url_name = "common:locale-detail-viewset"
    create_data = {"name": "Permission Test Locale", "code": "en"}
    update_data = {"name": "Updated Name"}

    def setUp(self):
        super().setUp()
        self.create_standard_users()
        self.locale = Locale.get_default()
        self.authenticate_as(self.admin)

    def resource_factory(self):
        return self.locale

    def test_list_locales(self):
        url = reverse("common:locale-viewset")
        response = self.client.get(url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertGreaterEqual(len(response.data.get("response_body")), 1)

    def test_paginated_list_locales(self):
        url = reverse("common:locale-viewset")
        response = self.client.get(url, {"page": 1, "size": 2})
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertGreaterEqual(
            len(response.data.get("response_body").get("results")), 1
        )

    def test_create_locale(self):
        data = {"name": "New locale", "code": "en"}
        locale_count = Locale.objects.count()
        url = reverse("common:locale-viewset")
        response = self.client.post(url, data, format="json")
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(Locale.objects.count(), locale_count + 1)

    def test_retrieve_locale(self):
        url = reverse("common:locale-detail-viewset", kwargs={"id": self.locale.id})
        response = self.client.get(url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data.get("response_body").get("id"), self.locale.id)

    def test_partial_update_locale(self):
        url = reverse("common:locale-detail-viewset", kwargs={"id": self.locale.id})
        name = "New name"
        response = self.client.patch(url, {"name": name}, format="json")
        updated_locale = Locale.objects.get(id=self.locale.id)
        self.assertEqual(name, updated_locale.name)
        self.assertEqual(response.status_code, status.HTTP_200_OK)

    def test_delete_locale(self):
        url = reverse("common:locale-detail-viewset", kwargs={"id": self.locale.id})
        self.client.delete(url, format="json")
        self.assertFalse(Locale.objects.filter(id=self.locale.id).exists())


class TranslationTestCase(CRUDPermissionTestsMixin, CustomAPITestCase):
    list_url_name = "common:translation-viewset"
    detail_url_name = "common:translation-detail-viewset"
    update_data = {"text": "Updated text"}

    def setUp(self):
        super().setUp()
        self.create_standard_users()
        self.locale = Locale.get_default()
        self.eng_locale = baker.make(Locale, name="English", code="en")
        self.root_translation = baker.make(
            Translation, text="Merhaba Dünya", root=None, locale=self.locale
        )
        self.second_root_translation = baker.make(
            Translation, text="Hello World", root=None, locale=self.eng_locale
        )
        self.create_data = {
            "text": "Hello World",
            "locale": self.eng_locale.id,
            "root_id": self.root_translation.id,
        }
        self.authenticate_as(self.admin)

    def resource_factory(self):
        return self.root_translation

    def test_list_translations(self):
        url = reverse("common:translation-viewset")
        response = self.client.get(url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertGreaterEqual(len(response.data.get("response_body")), 2)

    def test_create_translation(self):
        data = {
            "text": "Hello World",
            "locale": self.eng_locale.id,
            "root_id": self.root_translation.id,
        }

        translation_count = Translation.objects.count()
        translations_count_of_root = self.root_translation.translations.count()
        url = reverse("common:translation-viewset")
        response = self.client.post(url, data, format="json")
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(Translation.objects.count(), translation_count + 1)
        self.assertEqual(
            self.root_translation.translations.count(),
            translations_count_of_root + 1,
        )

        response = self.client.post(url, data, format="json")
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_retrieve_translation(self):
        url = reverse(
            "common:translation-detail-viewset", kwargs={"id": self.root_translation.id}
        )
        response = self.client.get(url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(
            response.data.get("response_body").get("id"), self.root_translation.id
        )

    def test_partial_update_translation(self):
        url = reverse(
            "common:translation-detail-viewset", kwargs={"id": self.root_translation.id}
        )
        response = self.client.patch(url, {"text": "Hello!"}, format="json")
        translation = Translation.objects.get(id=self.root_translation.id)
        self.assertEqual("Hello!", translation.text)
        self.assertEqual(response.status_code, status.HTTP_200_OK)

    def test_delete_translation(self):
        url = reverse(
            "common:translation-detail-viewset", kwargs={"id": self.root_translation.id}
        )
        self.client.delete(url, format="json")
        self.assertFalse(
            Translation.objects.filter(id=self.root_translation.id).exists()
        )


class TranslatedFileTestCase(CustomAPITestCase):

    def setUp(self):
        super().setUp()
        self.create_standard_users()
        self.locale = Locale.get_default()
        self.eng_locale = baker.make(Locale, name="English", code="en")
        self.root_translated_file = baker.make(
            TranslatedFile,
            name="File1",
            extension="png",
            vendor_url="http://example.com",
            bucket_name="myapp-dev",
            directory="translated_file/",
            type=FileType.IMAGE,
            vendor="idrive",
            public=True,
            root=None,
            locale=self.eng_locale,
        )
        self.authenticate_as(self.admin)

    @patch("cloud_storage.idrive_client.IDriveClient.create_presigned_url")
    def test_list_translated_files(self, mock_create_presigned_url):
        mock_create_presigned_url.return_value = "http://example.com"
        url = reverse("common:translated-file-viewset")
        response = self.client.get(url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertGreaterEqual(len(response.data.get("response_body")), 1)

    @patch("cloud_storage.idrive_client.IDriveClient.create_presigned_url")
    def test_create_translated_file(self, mock_create_presigned_url):
        mock_create_presigned_url.return_value = "http://example.com"
        data = {
            "locale": self.locale.id,
            "extension": "jpeg",
            "type": "IMAGE",
            "root_id": self.root_translated_file.id,
        }

        translation_count = TranslatedFile.objects.count()
        translations_count_of_root = self.root_translated_file.translations.count()
        url = reverse("common:translated-file-viewset")
        response = self.client.post(url, data, format="json")
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(TranslatedFile.objects.count(), translation_count + 1)
        self.assertEqual(
            self.root_translated_file.translations.count(),
            translations_count_of_root + 1,
        )

        response = self.client.post(url, data, format="json")
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    @patch("cloud_storage.idrive_client.IDriveClient.create_presigned_url")
    def test_retrieve_translated_file(self, mock_create_presigned_url):
        mock_create_presigned_url.return_value = "http://example.com"
        url = reverse(
            "common:translated-file-detail-viewset",
            kwargs={"id": self.root_translated_file.id},
        )
        response = self.client.get(url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(
            response.data.get("response_body").get("id"), self.root_translated_file.id
        )

    @patch("cloud_storage.idrive_client.IDriveClient.create_presigned_url")
    def test_partial_update_translated_file(self, mock_create_presigned_url):
        mock_create_presigned_url.return_value = "http://example.com"
        url = reverse(
            "common:translated-file-detail-viewset",
            kwargs={"id": self.root_translated_file.id},
        )
        response = self.client.patch(url, {"type": "AUDIO"}, format="json")
        translated_file = TranslatedFile.objects.get(id=self.root_translated_file.id)
        self.assertEqual("AUDIO", translated_file.type)
        self.assertEqual(response.status_code, status.HTTP_200_OK)

    @patch("cloud_storage.idrive_client.IDriveClient.create_presigned_url")
    def test_delete_translated_file(self, mock_create_presigned_url):
        mock_create_presigned_url.return_value = "http://example.com"
        url = reverse(
            "common:translated-file-detail-viewset",
            kwargs={"id": self.root_translated_file.id},
        )
        self.client.delete(url, format="json")
        self.assertFalse(
            TranslatedFile.objects.filter(id=self.root_translated_file.id).exists()
        )
