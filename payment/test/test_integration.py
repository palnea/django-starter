from decimal import Decimal

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
