from django.contrib.auth.models import Group, Permission
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

    def test_regular_user_can_list_locales(self):
        """
        Test that regular users can list locales (read-only access).
        """
        # Login as regular user
        response = self.login_user(self.user, self.user_password)
        user_access_token = response.get("access", None)
        
        # List locales - should work (IsReadonly permission)
        url = reverse("locale-viewset")
        response = self.client.get(
            url, HTTP_AUTHORIZATION=f"Bearer {user_access_token}"
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertGreaterEqual(len(response.data.get("response_body")), 1)

    def test_regular_user_can_retrieve_locale(self):
        """
        Test that regular users can retrieve individual locales (read-only access).
        """
        # Login as regular user
        response = self.login_user(self.user, self.user_password)
        user_access_token = response.get("access", None)
        
        # Retrieve locale - should work (IsReadonly permission)
        locale = Locale.objects.first()
        url = reverse("locale-detail-viewset", kwargs={"id": locale.id})
        response = self.client.get(
            url, HTTP_AUTHORIZATION=f"Bearer {user_access_token}"
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data.get("response_body").get("id"), locale.id)

    def test_regular_user_cannot_create_locales(self):
        """
        Test that regular users cannot create locales.
        """
        # Login as regular user
        response = self.login_user(self.user, self.user_password)
        user_access_token = response.get("access", None)
        
        # Try to create locale - should be forbidden
        data = {"name": "Unauthorized Locale", "code": "xx"}
        locale_count_before = Locale.objects.count()
        url = reverse("locale-viewset")
        response = self.client.post(
            url, data, format="json", HTTP_AUTHORIZATION=f"Bearer {user_access_token}"
        )
        locale_count_after = Locale.objects.count()
        
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)
        self.assertEqual(locale_count_after, locale_count_before)  # No new locale created

    def test_regular_user_cannot_update_locales(self):
        """
        Test that regular users cannot update locales.
        """
        # Login as regular user
        response = self.login_user(self.user, self.user_password)
        user_access_token = response.get("access", None)
        
        # Try to update locale - should be forbidden
        locale = Locale.objects.first()
        original_name = locale.name
        url = reverse("locale-detail-viewset", kwargs={"id": locale.id})
        response = self.client.patch(
            url,
            {"name": "Unauthorized Update"},
            content_type="application/json",
            format="json",
            HTTP_AUTHORIZATION=f"Bearer {user_access_token}",
        )
        
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)
        
        # Verify locale was not updated
        locale.refresh_from_db()
        self.assertEqual(locale.name, original_name)

    def test_regular_user_cannot_delete_locales(self):
        """
        Test that regular users cannot delete locales.
        """
        # Login as regular user
        response = self.login_user(self.user, self.user_password)
        user_access_token = response.get("access", None)
        
        # Try to delete locale - should be forbidden
        locale = Locale.objects.first()
        locale_id = locale.id
        url = reverse("locale-detail-viewset", kwargs={"id": locale_id})
        response = self.client.delete(
            url, format="json", HTTP_AUTHORIZATION=f"Bearer {user_access_token}"
        )
        
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)
        
        # Verify locale still exists
        self.assertTrue(Locale.objects.filter(id=locale_id).exists())

    def test_unauthenticated_user_can_list_locales(self):
        """
        Test that unauthenticated users can list locales (public read access).
        """
        # List locales without authentication - should work (IsReadonly permission)
        url = reverse("locale-viewset")
        response = self.client.get(url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertGreaterEqual(len(response.data.get("response_body")), 1)

    def test_unauthenticated_user_can_retrieve_locale(self):
        """
        Test that unauthenticated users can retrieve individual locales (public read access).
        """
        # Retrieve locale without authentication - should work (IsReadonly permission)
        locale = Locale.objects.first()
        url = reverse("locale-detail-viewset", kwargs={"id": locale.id})
        response = self.client.get(url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data.get("response_body").get("id"), locale.id)

    def test_unauthenticated_user_cannot_create_locales(self):
        """
        Test that unauthenticated users cannot create locales.
        """
        # Try to create locale without authentication - should be unauthorized
        data = {"name": "Unauthorized Locale", "code": "xx"}
        locale_count_before = Locale.objects.count()
        url = reverse("locale-viewset")
        response = self.client.post(url, data, format="json")
        locale_count_after = Locale.objects.count()
        
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)
        self.assertEqual(locale_count_after, locale_count_before)  # No new locale created

    def test_unauthenticated_user_cannot_update_locales(self):
        """
        Test that unauthenticated users cannot update locales.
        """
        # Try to update locale without authentication - should be unauthorized
        locale = Locale.objects.first()
        original_name = locale.name
        url = reverse("locale-detail-viewset", kwargs={"id": locale.id})
        response = self.client.patch(
            url,
            {"name": "Unauthorized Update"},
            content_type="application/json",
            format="json",
        )
        
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)
        
        # Verify locale was not updated
        locale.refresh_from_db()
        self.assertEqual(locale.name, original_name)

    def test_unauthenticated_user_cannot_delete_locales(self):
        """
        Test that unauthenticated users cannot delete locales.
        """
        # Try to delete locale without authentication - should be unauthorized
        locale = Locale.objects.first()
        locale_id = locale.id
        url = reverse("locale-detail-viewset", kwargs={"id": locale_id})
        response = self.client.delete(url, format="json")
        
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)
        
        # Verify locale still exists
        self.assertTrue(Locale.objects.filter(id=locale_id).exists())


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

    def test_regular_user_can_list_translations(self):
        """
        Test that regular users can list translations (read-only access).
        """
        # Login as regular user
        response = self.login_user(self.user, self.user_password)
        user_access_token = response.get("access", None)
        
        # List translations - should work (IsReadonly permission)
        url = reverse("translation-viewset")
        response = self.client.get(
            url, HTTP_AUTHORIZATION=f"Bearer {user_access_token}"
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertGreaterEqual(len(response.data.get("response_body")), 2)

    def test_regular_user_can_retrieve_translation(self):
        """
        Test that regular users can retrieve individual translations (read-only access).
        """
        # Login as regular user
        response = self.login_user(self.user, self.user_password)
        user_access_token = response.get("access", None)
        
        # Retrieve translation - should work (IsReadonly permission)
        translation = Translation.objects.first()
        url = reverse("translation-detail-viewset", kwargs={"id": translation.id})
        response = self.client.get(
            url, HTTP_AUTHORIZATION=f"Bearer {user_access_token}"
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data.get("response_body").get("id"), translation.id)

    def test_regular_user_cannot_create_translations(self):
        """
        Test that regular users cannot create translations.
        """
        # Login as regular user
        response = self.login_user(self.user, self.user_password)
        user_access_token = response.get("access", None)
        
        # Try to create translation - should be forbidden
        data = {
            "text": "Unauthorized Translation",
            "locale": self.eng_locale.id,
            "root_id": self.root_translation.id,
        }
        
        translation_count_before = Translation.objects.count()
        url = reverse("translation-viewset")
        response = self.client.post(
            url, data, format="json", HTTP_AUTHORIZATION=f"Bearer {user_access_token}"
        )
        translation_count_after = Translation.objects.count()
        
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)
        self.assertEqual(translation_count_after, translation_count_before)  # No new translation created

    def test_regular_user_cannot_update_translations(self):
        """
        Test that regular users cannot update translations.
        """
        # Login as regular user
        response = self.login_user(self.user, self.user_password)
        user_access_token = response.get("access", None)
        
        # Try to update translation - should be forbidden
        translation = Translation.objects.first()
        original_text = translation.text
        url = reverse("translation-detail-viewset", kwargs={"id": translation.id})
        response = self.client.patch(
            url,
            {"text": "Unauthorized Update"},
            content_type="application/json",
            format="json",
            HTTP_AUTHORIZATION=f"Bearer {user_access_token}",
        )
        
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)
        
        # Verify translation was not updated
        translation.refresh_from_db()
        self.assertEqual(translation.text, original_text)

    def test_regular_user_cannot_delete_translations(self):
        """
        Test that regular users cannot delete translations.
        """
        # Login as regular user
        response = self.login_user(self.user, self.user_password)
        user_access_token = response.get("access", None)
        
        # Try to delete translation - should be forbidden
        translation = Translation.objects.first()
        translation_id = translation.id
        url = reverse("translation-detail-viewset", kwargs={"id": translation_id})
        response = self.client.delete(
            url, format="json", HTTP_AUTHORIZATION=f"Bearer {user_access_token}"
        )
        
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)
        
        # Verify translation still exists
        self.assertTrue(Translation.objects.filter(id=translation_id).exists())

    def test_unauthenticated_user_can_list_translations(self):
        """
        Test that unauthenticated users can list translations (public read access).
        """
        # List translations without authentication - should work (IsReadonly permission)
        url = reverse("translation-viewset")
        response = self.client.get(url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertGreaterEqual(len(response.data.get("response_body")), 2)

    def test_unauthenticated_user_can_retrieve_translation(self):
        """
        Test that unauthenticated users can retrieve individual translations (public read access).
        """
        # Retrieve translation without authentication - should work (IsReadonly permission)
        translation = Translation.objects.first()
        url = reverse("translation-detail-viewset", kwargs={"id": translation.id})
        response = self.client.get(url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data.get("response_body").get("id"), translation.id)

    def test_unauthenticated_user_cannot_create_translations(self):
        """
        Test that unauthenticated users cannot create translations.
        """
        # Try to create translation without authentication - should be unauthorized
        data = {
            "text": "Unauthorized Translation",
            "locale": self.eng_locale.id,
            "root_id": self.root_translation.id,
        }
        
        translation_count_before = Translation.objects.count()
        url = reverse("translation-viewset")
        response = self.client.post(url, data, format="json")
        translation_count_after = Translation.objects.count()
        
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)
        self.assertEqual(translation_count_after, translation_count_before)  # No new translation created

    def test_unauthenticated_user_cannot_update_translations(self):
        """
        Test that unauthenticated users cannot update translations.
        """
        # Try to update translation without authentication - should be unauthorized
        translation = Translation.objects.first()
        original_text = translation.text
        url = reverse("translation-detail-viewset", kwargs={"id": translation.id})
        response = self.client.patch(
            url,
            {"text": "Unauthorized Update"},
            content_type="application/json",
            format="json",
        )
        
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)
        
        # Verify translation was not updated
        translation.refresh_from_db()
        self.assertEqual(translation.text, original_text)

    def test_unauthenticated_user_cannot_delete_translations(self):
        """
        Test that unauthenticated users cannot delete translations.
        """
        # Try to delete translation without authentication - should be unauthorized
        translation = Translation.objects.first()
        translation_id = translation.id
        url = reverse("translation-detail-viewset", kwargs={"id": translation_id})
        response = self.client.delete(url, format="json")
        
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)
        
        # Verify translation still exists
        self.assertTrue(Translation.objects.filter(id=translation_id).exists())


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
