from decimal import Decimal

from django.contrib.auth.models import Group, Permission
from django.urls import reverse
from model_bakery import baker
from rest_framework import status

from custom_test.base_test import CustomIntegrationTestCase
from payment.models import Buyable
from payment.types import SubscriptionPeriod, BuyableType


class PurchaseTestCase(CustomIntegrationTestCase):
    def setUp(self):
        super().setUp()
        self.create_common_models()

    def login_user(self):
        data = {"phone": self.user.phone, "password": "123"}
        url = reverse("login")
        response = self.client.post(url, data, format="json")
        self.access_token = response.data["response_body"]["access"]

    def test_apple_verify_correct_receipt(self):
        pass  # TODO after store accounts are created

    def test_apple_verify_incorrect_receipt(self):
        pass  # TODO after store accounts are created

    def test_google_verify_correct_receipt(self):
        pass  # TODO after store accounts are created

    def test_google_verify_incorrect_receipt(self):
        pass  # TODO after store accounts are created


class BuyableTestCase(CustomIntegrationTestCase):

    def setUp(self):
        super().setUp()
        self.create_common_models()
        baker.make(
            Buyable,
            name="monthly",
            title_id=self.translation.id,
            description_id=self.translation.id,
            price=Decimal("110.0"),
            currency="TRY",
            period=SubscriptionPeriod.MONTHLY.value,
            type=BuyableType.PERSONAL_SUBSCRIPTION.value,
            trial_days=7,
            is_active=True,
        )
        baker.make(
            Buyable,
            name="annual",
            title_id=self.translation.id,
            description_id=self.translation.id,
            price=Decimal("650.0"),
            currency="TRY",
            period=SubscriptionPeriod.ANNUAL.value,
            type=BuyableType.PERSONAL_SUBSCRIPTION.value,
            trial_days=30,
            is_active=True,
        )

    def test_list_buyables(self):
        url = reverse("buyable-viewset")
        response = self.client.get(url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertGreaterEqual(len(response.data.get("response_body")), 2)

    def test_create_buyables(self):
        response = self.login_admin_user()
        access_token = response.get("access", None)

        data = {
            "title_id": self.translation.id,
            "description_id": self.translation.id,
            "is_deleted": False,
            "name": "blabla",
            "price": "69.99",
            "currency": "TRY",
            "period": "monthly",
            "type": "personal_subscription",
            "trial_days": 1,
            "is_active": True,
            "created": "2022-10-22T12:00:00",
            "updated": "2022-10-22T12:00:00",
        }

        buyable_count = Buyable.objects.count()
        url = reverse("buyable-viewset")
        response = self.client.post(
            url, data, format="json", HTTP_AUTHORIZATION=f"Bearer {access_token}"
        )
        buyable_count_after_create = Buyable.objects.count()

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(buyable_count_after_create, buyable_count + 1)

    def test_retrieve_buyable(self):
        response = self.login_admin_user()
        access_token = response.get("access", None)
        buyable = Buyable.objects.first()
        url = reverse("buyable-detail-viewset", kwargs={"id": buyable.id})
        response = self.client.get(url, HTTP_AUTHORIZATION=f"Bearer {access_token}")
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data.get("response_body").get("id"), buyable.id)

    def test_partial_update_buyable(self):
        response = self.login_admin_user()
        access_token = response.get("access", None)
        buyable = Buyable.objects.first()
        url = reverse("buyable-detail-viewset", kwargs={"id": buyable.id})
        response = self.client.patch(
            url,
            {"price": "111"},
            content_type="application/json",
            format="json",
            HTTP_AUTHORIZATION=f"Bearer {access_token}",
        )
        buyable = Buyable.objects.get(id=buyable.id)
        self.assertEqual(Decimal("111"), buyable.price)
        self.assertEqual(response.status_code, status.HTTP_200_OK)

    def test_delete_buyable(self):
        response = self.login_admin_user()
        access_token = response.get("access", None)
        buyable = Buyable.objects.first()
        url = reverse("buyable-detail-viewset", kwargs={"id": buyable.id})
        self.client.delete(
            url, format="json", HTTP_AUTHORIZATION=f"Bearer {access_token}"
        )
        self.assertFalse(Buyable.objects.filter(id=buyable.id).exists())

    def test_regular_user_can_list_buyables(self):
        """
        Test that regular users can list buyables (read-only access).
        """
        # Login as regular user
        response = self.login_user(self.user, self.user_password)
        user_access_token = response.get("access", None)

        # List buyables - should work (IsReadonly permission)
        url = reverse("buyable-viewset")
        response = self.client.get(
            url, HTTP_AUTHORIZATION=f"Bearer {user_access_token}"
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertGreaterEqual(len(response.data.get("response_body")), 2)

    def test_regular_user_can_retrieve_buyable(self):
        """
        Test that regular users can retrieve individual buyables (read-only access).
        """
        # Login as regular user
        response = self.login_user(self.user, self.user_password)
        user_access_token = response.get("access", None)

        # Retrieve buyable - should work (IsReadonly permission)
        buyable = Buyable.objects.first()
        url = reverse("buyable-detail-viewset", kwargs={"id": buyable.id})
        response = self.client.get(
            url, HTTP_AUTHORIZATION=f"Bearer {user_access_token}"
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data.get("response_body").get("id"), buyable.id)

    def test_regular_user_cannot_create_buyables(self):
        """
        Test that regular users cannot create buyables.
        """
        # Login as regular user
        response = self.login_user(self.user, self.user_password)
        user_access_token = response.get("access", None)

        # Try to create buyable - should be forbidden
        data = {
            "title_id": self.translation.id,
            "description_id": self.translation.id,
            "is_deleted": False,
            "name": "unauthorized_buyable",
            "price": "99.99",
            "currency": "TRY",
            "period": "monthly",
            "type": "personal_subscription",
            "trial_days": 1,
            "is_active": True,
        }

        buyable_count_before = Buyable.objects.count()
        url = reverse("buyable-viewset")
        response = self.client.post(
            url, data, format="json", HTTP_AUTHORIZATION=f"Bearer {user_access_token}"
        )
        buyable_count_after = Buyable.objects.count()

        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)
        self.assertEqual(
            buyable_count_after, buyable_count_before
        )  # No new buyable created

    def test_regular_user_cannot_update_buyables(self):
        """
        Test that regular users cannot update buyables.
        """
        # Login as regular user
        response = self.login_user(self.user, self.user_password)
        user_access_token = response.get("access", None)

        # Try to update buyable - should be forbidden
        buyable = Buyable.objects.first()
        original_price = buyable.price
        url = reverse("buyable-detail-viewset", kwargs={"id": buyable.id})
        response = self.client.patch(
            url,
            {"price": "999.99"},
            content_type="application/json",
            format="json",
            HTTP_AUTHORIZATION=f"Bearer {user_access_token}",
        )

        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

        # Verify buyable was not updated
        buyable.refresh_from_db()
        self.assertEqual(buyable.price, original_price)

    def test_regular_user_cannot_delete_buyables(self):
        """
        Test that regular users cannot delete buyables.
        """
        # Login as regular user
        response = self.login_user(self.user, self.user_password)
        user_access_token = response.get("access", None)

        # Try to delete buyable - should be forbidden
        buyable = Buyable.objects.first()
        buyable_id = buyable.id
        url = reverse("buyable-detail-viewset", kwargs={"id": buyable_id})
        response = self.client.delete(
            url, format="json", HTTP_AUTHORIZATION=f"Bearer {user_access_token}"
        )

        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

        # Verify buyable still exists
        self.assertTrue(Buyable.objects.filter(id=buyable_id).exists())

    def test_unauthenticated_user_can_list_buyables(self):
        """
        Test that unauthenticated users can list buyables (public read access).
        """
        # List buyables without authentication - should work (IsReadonly permission)
        url = reverse("buyable-viewset")
        response = self.client.get(url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertGreaterEqual(len(response.data.get("response_body")), 2)

    def test_unauthenticated_user_can_retrieve_buyable(self):
        """
        Test that unauthenticated users can retrieve individual buyables (public read access).
        """
        # Retrieve buyable without authentication - should work (IsReadonly permission)
        buyable = Buyable.objects.first()
        url = reverse("buyable-detail-viewset", kwargs={"id": buyable.id})
        response = self.client.get(url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data.get("response_body").get("id"), buyable.id)

    def test_unauthenticated_user_cannot_create_buyables(self):
        """
        Test that unauthenticated users cannot create buyables.
        """
        # Try to create buyable without authentication - should be unauthorized
        data = {
            "title_id": self.translation.id,
            "description_id": self.translation.id,
            "name": "unauthorized_buyable",
            "price": "99.99",
            "currency": "TRY",
            "period": "monthly",
            "type": "personal_subscription",
            "trial_days": 1,
            "is_active": True,
        }

        buyable_count_before = Buyable.objects.count()
        url = reverse("buyable-viewset")
        response = self.client.post(url, data, format="json")
        buyable_count_after = Buyable.objects.count()

        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)
        self.assertEqual(
            buyable_count_after, buyable_count_before
        )  # No new buyable created

    def test_unauthenticated_user_cannot_update_buyables(self):
        """
        Test that unauthenticated users cannot update buyables.
        """
        # Try to update buyable without authentication - should be unauthorized
        buyable = Buyable.objects.first()
        original_price = buyable.price
        url = reverse("buyable-detail-viewset", kwargs={"id": buyable.id})
        response = self.client.patch(
            url,
            {"price": "999.99"},
            content_type="application/json",
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

        # Verify buyable was not updated
        buyable.refresh_from_db()
        self.assertEqual(buyable.price, original_price)

    def test_unauthenticated_user_cannot_delete_buyables(self):
        """
        Test that unauthenticated users cannot delete buyables.
        """
        # Try to delete buyable without authentication - should be unauthorized
        buyable = Buyable.objects.first()
        buyable_id = buyable.id
        url = reverse("buyable-detail-viewset", kwargs={"id": buyable_id})
        response = self.client.delete(url, format="json")

        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

        # Verify buyable still exists
        self.assertTrue(Buyable.objects.filter(id=buyable_id).exists())
