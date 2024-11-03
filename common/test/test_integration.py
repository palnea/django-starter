from django.urls import reverse
from mock.mock import patch
from model_bakery import baker
from rest_framework import status

from common.models import Translation, TranslatedFile, Locale
from common.types import FileType
from custom_test.base_test import CustomIntegrationTestCase


class LocaleViewTestCase(CustomIntegrationTestCase):
    def setUp(self):
        super().setUp()
        self.create_common_models()
        response = self.login_admin_user()
        self.access_token = response.get("access", None)

    def test_list_locales(self):
        url = reverse("locale-viewset")
        response = self.client.get(
            url, HTTP_AUTHORIZATION=f"Bearer {self.access_token}"
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertGreaterEqual(len(response.data.get("response_body")), 1)

    def test_paginated_list_locales(self):
        url = reverse("locale-viewset")
        response = self.client.get(
            url,
            {"page": 1, "size": 2},
            HTTP_AUTHORIZATION=f"Bearer {self.access_token}",
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertGreaterEqual(
            len(response.data.get("response_body").get("results")), 1
        )

    def test_create_locale(self):
        data = {"name": "New locale", "code": "en"}
        locale_count = Locale.objects.count()
        url = reverse("locale-viewset")
        response = self.client.post(
            url, data, format="json", HTTP_AUTHORIZATION=f"Bearer {self.access_token}"
        )
        locale_count_after_create = Locale.objects.count()
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(locale_count_after_create, locale_count + 1)

    def test_retrieve_locale(self):
        created_locale = Locale.objects.first()
        url = reverse("locale-detail-viewset", kwargs={"id": created_locale.id})
        response = self.client.get(
            url, HTTP_AUTHORIZATION=f"Bearer {self.access_token}"
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(
            response.data.get("response_body").get("id"), created_locale.id
        )

    def test_partial_update_locale(self):
        created_locale = Locale.objects.first()
        url = reverse("locale-detail-viewset", kwargs={"id": created_locale.id})
        name = "New name"
        response = self.client.patch(
            url,
            {"name": name},
            content_type="application/json",
            format="json",
            HTTP_AUTHORIZATION=f"Bearer {self.access_token}",
        )
        updated_locale = Locale.objects.get(id=created_locale.id)
        self.assertEqual(name, updated_locale.name)
        self.assertEqual(response.status_code, status.HTTP_200_OK)

    def test_delete_locale(self):
        created_locale = Locale.objects.first()
        url = reverse("locale-detail-viewset", kwargs={"id": created_locale.id})
        self.client.delete(
            url, format="json", HTTP_AUTHORIZATION=f"Bearer {self.access_token}"
        )
        self.assertFalse(Locale.objects.filter(id=created_locale.id).exists())


class TranslationTestCase(CustomIntegrationTestCase):

    def setUp(self):
        super().setUp()
        self.create_common_models()
        self.eng_locale = baker.make("common.Locale", name="English", code="en")
        self.root_translation = baker.make(
            Translation, text="Merhaba Dünya", root=None, locale=self.locale
        )

        response = self.login_admin_user()
        self.access_token = response.get("access", None)

    def test_list_translations(self):
        url = reverse("translation-viewset")
        response = self.client.get(
            url, HTTP_AUTHORIZATION=f"Bearer {self.access_token}"
        )
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
        url = reverse("translation-viewset")
        response = self.client.post(
            url, data, format="json", HTTP_AUTHORIZATION=f"Bearer {self.access_token}"
        )
        translation_count_after_create = Translation.objects.count()
        translations_count_of_root_after_created = (
            self.root_translation.translations.count()
        )

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(translation_count_after_create, translation_count + 1)
        self.assertEqual(
            translations_count_of_root_after_created, translations_count_of_root + 1
        )

        response = self.client.post(
            url, data, format="json", HTTP_AUTHORIZATION=f"Bearer {self.access_token}"
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_retrieve_translation(self):
        translation = Translation.objects.first()
        url = reverse("translation-detail-viewset", kwargs={"id": translation.id})
        response = self.client.get(
            url, HTTP_AUTHORIZATION=f"Bearer {self.access_token}"
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data.get("response_body").get("id"), translation.id)

    def test_partial_update_translation(self):
        translation = Translation.objects.first()
        url = reverse("translation-detail-viewset", kwargs={"id": translation.id})
        response = self.client.patch(
            url,
            {"text": "Hello!"},
            content_type="application/json",
            format="json",
            HTTP_AUTHORIZATION=f"Bearer {self.access_token}",
        )
        translation = Translation.objects.get(id=translation.id)
        self.assertEqual("Hello!", translation.text)
        self.assertEqual(response.status_code, status.HTTP_200_OK)

    def test_delete_translation(self):
        translation = Translation.objects.first()
        url = reverse("translation-detail-viewset", kwargs={"id": translation.id})
        response = self.client.delete(
            url, format="json", HTTP_AUTHORIZATION=f"Bearer {self.access_token}"
        )
        self.assertFalse(Translation.objects.filter(id=translation.id).exists())


class TranslatedFileTestCase(CustomIntegrationTestCase):

    def setUp(self):
        super().setUp()
        self.create_common_models()
        self.eng_locale = baker.make("common.Locale", name="English", code="en")
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

        response = self.login_admin_user()
        self.access_token = response.get("access", None)

    @patch("cloud_storage.idrive_client.IDriveClient.create_presigned_url")
    def test_list_translated_files(self, mock_create_presigned_url):
        mock_create_presigned_url.return_value = "http://example.com"
        url = reverse("translated-file-viewset")
        response = self.client.get(
            url, HTTP_AUTHORIZATION=f"Bearer {self.access_token}"
        )
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
        url = reverse("translated-file-viewset")
        response = self.client.post(
            url, data, format="json", HTTP_AUTHORIZATION=f"Bearer {self.access_token}"
        )
        translates_count_after_create = TranslatedFile.objects.count()
        translations_count_of_root_after_created = (
            self.root_translated_file.translations.count()
        )

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(translates_count_after_create, translation_count + 1)
        self.assertEqual(
            translations_count_of_root_after_created, translations_count_of_root + 1
        )

        response = self.client.post(
            url, data, format="json", HTTP_AUTHORIZATION=f"Bearer {self.access_token}"
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    @patch("cloud_storage.idrive_client.IDriveClient.create_presigned_url")
    def test_retrieve_translated_file(self, mock_create_presigned_url):
        mock_create_presigned_url.return_value = "http://example.com"
        translated_file = TranslatedFile.objects.first()
        url = reverse(
            "translated-file-detail-viewset", kwargs={"id": translated_file.id}
        )
        response = self.client.get(
            url, HTTP_AUTHORIZATION=f"Bearer {self.access_token}"
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(
            response.data.get("response_body").get("id"), translated_file.id
        )

    @patch("cloud_storage.idrive_client.IDriveClient.create_presigned_url")
    def test_partial_update_translated_file(self, mock_create_presigned_url):
        mock_create_presigned_url.return_value = "http://example.com"
        translated_file = TranslatedFile.objects.first()
        url = reverse(
            "translated-file-detail-viewset", kwargs={"id": translated_file.id}
        )
        response = self.client.patch(
            url,
            {"type": "AUDIO"},
            content_type="application/json",
            format="json",
            HTTP_AUTHORIZATION=f"Bearer {self.access_token}",
        )
        translated_file = TranslatedFile.objects.get(id=translated_file.id)
        self.assertEqual("AUDIO", translated_file.type)
        self.assertEqual(response.status_code, status.HTTP_200_OK)

    @patch("cloud_storage.idrive_client.IDriveClient.create_presigned_url")
    def test_delete_translated_file(self, mock_create_presigned_url):
        mock_create_presigned_url.return_value = "http://example.com"
        translated_file = TranslatedFile.objects.first()
        url = reverse(
            "translated-file-detail-viewset", kwargs={"id": translated_file.id}
        )
        response = self.client.delete(
            url, format="json", HTTP_AUTHORIZATION=f"Bearer {self.access_token}"
        )
        self.assertFalse(TranslatedFile.objects.filter(id=translated_file.id).exists())
