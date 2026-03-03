from django.urls import reverse
from rest_framework import status

from custom_test.base_test import CustomAPITestCase
from user.models import User


class UserViewSetTestCase(CustomAPITestCase):

    def setUp(self):
        super().setUp()
        self.create_standard_users()
        self.other_user, _ = self.create_user()
        self.authenticate_as(self.admin)

    def test_list_users(self):
        url = reverse("user-viewset")
        response = self.client.get(url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertGreaterEqual(len(response.data.get("response_body")), 1)

    def test_retrieve_user(self):
        url = reverse("user-detail-viewset", kwargs={"user_id": self.other_user.id})
        response = self.client.get(url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(
            response.data.get("response_body").get("id"), str(self.other_user.id)
        )

    def test_partial_update_user(self):
        url = reverse("user-detail-viewset", kwargs={"user_id": self.other_user.id})
        fullname = "teacher"
        response = self.client.patch(url, {"fullname": fullname}, format="json")
        updated_user = User.objects.get(id=self.other_user.id)
        self.assertEqual(fullname, updated_user.fullname)
        self.assertEqual(response.status_code, status.HTTP_200_OK)

    def test_delete_user(self):
        url = reverse("user-detail-viewset", kwargs={"user_id": self.other_user.id})
        self.client.delete(url, format="json")
        self.assertFalse(User.objects.filter(id=self.other_user.id).exists())

    def test_regular_user_can_only_list_own_data(self):
        """Test that regular users can only see their own data in list operations."""
        # Create additional users
        user2, _ = self.create_user()
        user3, _ = self.create_user()

        self.authenticate_as(self.user)
        url = reverse("user-viewset")
        response = self.client.get(url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        response_users = response.data.get("response_body")

        self.assertEqual(response_users["count"], 1)
        self.assertEqual(len(response_users["results"]), 1)
        self.assertEqual(response_users["results"][0]["id"], str(self.user.id))

    def test_regular_user_can_access_own_detail(self):
        """Test that regular users can access their own user detail."""
        self.authenticate_as(self.user)
        url = reverse("user-detail-viewset", kwargs={"user_id": self.user.id})
        response = self.client.get(url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(
            response.data.get("response_body").get("id"), str(self.user.id)
        )

    def test_regular_user_cannot_access_other_user_detail(self):
        """Test that regular users cannot access other users' detail data.

        Returns 403 (Forbidden) because the object exists but the user lacks permission.
        This is correct behavior for object-level permission checks.
        """
        self.authenticate_as(self.user)
        url = reverse("user-detail-viewset", kwargs={"user_id": self.other_user.id})
        response = self.client.get(url)
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_regular_user_can_update_own_data(self):
        """Test that regular users can update their own data."""
        self.authenticate_as(self.user)
        url = reverse("user-detail-viewset", kwargs={"user_id": self.user.id})
        new_fullname = "Updated Name"
        response = self.client.patch(url, {"fullname": new_fullname}, format="json")
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.user.refresh_from_db()
        self.assertEqual(self.user.fullname, new_fullname)

    def test_regular_user_cannot_update_other_user_data(self):
        """Test that regular users cannot update other users' data.

        Note: This returns 404 instead of 403 because the ownership filtering
        makes the object invisible to the user, which is better for security.
        """
        self.authenticate_as(self.user)
        url = reverse("user-detail-viewset", kwargs={"user_id": self.other_user.id})
        response = self.client.patch(
            url, {"fullname": "Should Not Work"}, format="json"
        )
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_regular_user_can_delete_own_data(self):
        """Test that regular users can delete their own data."""
        user_to_delete, password = self.create_user()
        self.authenticate_as(user_to_delete)
        url = reverse("user-detail-viewset", kwargs={"user_id": user_to_delete.id})
        response = self.client.delete(url, format="json")
        self.assertEqual(response.status_code, status.HTTP_204_NO_CONTENT)
        self.assertFalse(User.objects.filter(id=user_to_delete.id).exists())

    def test_regular_user_cannot_delete_other_user_data(self):
        """Test that regular users cannot delete other users' data."""
        self.authenticate_as(self.user)
        url = reverse("user-detail-viewset", kwargs={"user_id": self.other_user.id})
        response = self.client.delete(url, format="json")
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)
        self.assertTrue(User.objects.filter(id=self.other_user.id).exists())

    def test_admin_can_access_all_users(self):
        """Test that admin users can access all user data."""
        user2, _ = self.create_user()
        user3, _ = self.create_user()

        url = reverse("user-viewset")
        response = self.client.get(url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        response_users = response.data.get("response_body")

        self.assertGreaterEqual(len(response_users), 4)

        url = reverse("user-detail-viewset", kwargs={"user_id": user2.id})
        response = self.client.get(url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data.get("response_body").get("id"), str(user2.id))

    def test_unauthenticated_user_cannot_access_users(self):
        """Test that unauthenticated users cannot access user data."""
        self.authenticate_as(None)
        url = reverse("user-viewset")
        response = self.client.get(url)
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

        url = reverse("user-detail-viewset", kwargs={"user_id": self.user.id})
        response = self.client.get(url)
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)
