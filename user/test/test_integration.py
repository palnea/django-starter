from django.contrib.auth.models import Group, Permission
from django.urls import reverse
from rest_framework import status

from custom_test.base_test import CustomIntegrationTestCase
from user.models import User


class UserViewSetTestCase(CustomIntegrationTestCase):

    def setUp(self):
        super().setUp()
        self.create_common_models()
        response = self.login_admin_user()
        self.access_token = response.get("access", None)
        self.assign_permissions_to_admin_group()

    def assign_permissions_to_admin_group(self):
        group = Group.objects.get(name="Admin")
        group.permissions.add(
            Permission.objects.get(
                codename="can_write_user", content_type__app_label="user"
            ),
        )

    def test_list_users(self):
        url = reverse("user-viewset")
        response = self.client.get(
            url, HTTP_AUTHORIZATION=f"Bearer {self.access_token}"
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertGreaterEqual(len(response.data.get("response_body")), 1)

    def test_retrieve_user(self):
        created_user = User.objects.first()
        url = reverse("user-detail-viewset", kwargs={"user_id": created_user.id})
        response = self.client.get(
            url, HTTP_AUTHORIZATION=f"Bearer {self.access_token}"
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(
            response.data.get("response_body").get("id"), str(created_user.id)
        )

    def test_partial_update_user(self):
        created_user = User.objects.first()
        url = reverse("user-detail-viewset", kwargs={"user_id": created_user.id})
        fullname = "teacher"
        response = self.client.patch(
            url,
            {"fullname": fullname},
            content_type="application/json",
            format="json",
            HTTP_AUTHORIZATION=f"Bearer {self.access_token}",
        )
        updated_user = User.objects.get(id=created_user.id)
        self.assertEqual(fullname, updated_user.fullname)
        self.assertEqual(response.status_code, status.HTTP_200_OK)

    def test_delete_user(self):
        created_user = User.objects.first()
        url = reverse("user-detail-viewset", kwargs={"user_id": created_user.id})
        self.client.delete(
            url, format="json", HTTP_AUTHORIZATION=f"Bearer {self.access_token}"
        )
        self.assertFalse(User.objects.filter(id=created_user.id).exists())
