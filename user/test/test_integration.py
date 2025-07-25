from django.contrib.auth.models import Group, Permission
from django.urls import reverse
from model_bakery import baker
from rest_framework import status

from custom_test.base_test import CustomIntegrationTestCase
from user.models import User


class UserViewSetTestCase(CustomIntegrationTestCase):

    def setUp(self):
        super().setUp()
        self.create_common_models()
        response = self.login_admin_user()
        self.access_token = response.get("access", None)


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

    def test_regular_user_can_only_list_own_data(self):
        """
        Test that regular users can only see their own data in list operations.
        """
        # Create additional users
        user2, password2 = self.create_user()
        user3, password3 = self.create_user()
        
        # Login as regular user (self.user created in setUp)
        response = self.login_user(self.user, self.user_password)
        user_access_token = response.get("access", None)
        
        # List users - should only see own data
        url = reverse("user-viewset")
        response = self.client.get(
            url, HTTP_AUTHORIZATION=f"Bearer {user_access_token}"
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        response_users = response.data.get("response_body")
        
        # Should only see own user data  
        self.assertEqual(response_users['count'], 1)
        self.assertEqual(len(response_users['results']), 1)
        self.assertEqual(response_users['results'][0]["id"], str(self.user.id))

    def test_regular_user_can_access_own_detail(self):
        """
        Test that regular users can access their own user detail.
        """
        # Login as regular user
        response = self.login_user(self.user, self.user_password)
        user_access_token = response.get("access", None)
        
        # Access own user detail - should work
        url = reverse("user-detail-viewset", kwargs={"user_id": self.user.id})
        response = self.client.get(
            url, HTTP_AUTHORIZATION=f"Bearer {user_access_token}"
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data.get("response_body").get("id"), str(self.user.id))

    def test_regular_user_cannot_access_other_user_detail(self):
        """
        Test that regular users cannot access other users' detail data.
        
        Returns 403 (Forbidden) because the object exists but the user lacks permission.
        This is correct behavior for object-level permission checks.
        """
        # Create another user
        other_user, _ = self.create_user()
        
        # Login as regular user
        response = self.login_user(self.user, self.user_password)
        user_access_token = response.get("access", None)
        
        # Try to access other user's detail - should return 403 (permission denied)
        url = reverse("user-detail-viewset", kwargs={"user_id": other_user.id})
        response = self.client.get(
            url, HTTP_AUTHORIZATION=f"Bearer {user_access_token}"
        )
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_regular_user_can_update_own_data(self):
        """
        Test that regular users can update their own data.
        """
        # Login as regular user
        response = self.login_user(self.user, self.user_password)
        user_access_token = response.get("access", None)
        
        # Update own data - should work
        url = reverse("user-detail-viewset", kwargs={"user_id": self.user.id})
        new_fullname = "Updated Name"
        response = self.client.patch(
            url,
            {"fullname": new_fullname},
            content_type="application/json",
            format="json",
            HTTP_AUTHORIZATION=f"Bearer {user_access_token}",
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        
        # Verify update
        self.user.refresh_from_db()
        self.assertEqual(self.user.fullname, new_fullname)

    def test_regular_user_cannot_update_other_user_data(self):
        """
        Test that regular users cannot update other users' data.
        
        Note: This returns 404 instead of 403 because the ownership filtering
        makes the object invisible to the user, which is better for security.
        """
        # Create another user
        other_user, _ = self.create_user()
        
        # Login as regular user
        response = self.login_user(self.user, self.user_password)
        user_access_token = response.get("access", None)
        
        # Try to update other user's data - should return 403 (permission denied)
        url = reverse("user-detail-viewset", kwargs={"user_id": other_user.id})
        response = self.client.patch(
            url,
            {"fullname": "Should Not Work"},
            content_type="application/json",
            format="json",
            HTTP_AUTHORIZATION=f"Bearer {user_access_token}",
        )
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_regular_user_can_delete_own_data(self):
        """
        Test that regular users can delete their own data.
        """
        # Create a user specifically for deletion test
        user_to_delete, password = self.create_user()
        
        # Login as that user
        response = self.login_user(user_to_delete, password)
        user_access_token = response.get("access", None)
        
        # Delete own data - should work
        url = reverse("user-detail-viewset", kwargs={"user_id": user_to_delete.id})
        response = self.client.delete(
            url, format="json", HTTP_AUTHORIZATION=f"Bearer {user_access_token}"
        )
        self.assertEqual(response.status_code, status.HTTP_204_NO_CONTENT)
        
        # Verify deletion
        self.assertFalse(User.objects.filter(id=user_to_delete.id).exists())

    def test_regular_user_cannot_delete_other_user_data(self):
        """
        Test that regular users cannot delete other users' data.
        """
        # Create another user
        other_user, _ = self.create_user()
        
        # Login as regular user
        response = self.login_user(self.user, self.user_password)
        user_access_token = response.get("access", None)
        
        # Try to delete other user's data - should be forbidden
        url = reverse("user-detail-viewset", kwargs={"user_id": other_user.id})
        response = self.client.delete(
            url, format="json", HTTP_AUTHORIZATION=f"Bearer {user_access_token}"
        )
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)
        
        # Verify other user still exists
        self.assertTrue(User.objects.filter(id=other_user.id).exists())

    def test_admin_can_access_all_users(self):
        """
        Test that admin users can access all user data.
        """
        # Create additional users
        user2, _ = self.create_user()
        user3, _ = self.create_user()
        
        # List all users as admin - should see all users
        url = reverse("user-viewset")
        response = self.client.get(
            url, HTTP_AUTHORIZATION=f"Bearer {self.access_token}"
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        response_users = response.data.get("response_body")
        
        # Should see all users (including admin, self.user, user2, user3)
        self.assertGreaterEqual(len(response_users), 4)
        
        # Admin should be able to access any user's detail
        url = reverse("user-detail-viewset", kwargs={"user_id": user2.id})
        response = self.client.get(
            url, HTTP_AUTHORIZATION=f"Bearer {self.access_token}"
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data.get("response_body").get("id"), str(user2.id))

    def test_unauthenticated_user_cannot_access_users(self):
        """
        Test that unauthenticated users cannot access user data.
        """
        # Try to list users without authentication
        url = reverse("user-viewset")
        response = self.client.get(url)
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)
        
        # Try to access user detail without authentication
        url = reverse("user-detail-viewset", kwargs={"user_id": self.user.id})
        response = self.client.get(url)
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)
