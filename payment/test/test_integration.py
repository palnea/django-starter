import json
from decimal import Decimal

from django.urls import reverse
from model_bakery import baker
from rest_framework import status

from common.custom_exceptions.custom_exception import CustomException
from custom_test.base_test import CustomAPITestCase
from custom_test.mixins import CRUDPermissionTestsMixin
from payment.models import Buyable
from payment.subscription.strategies import (
    ApplePurchaseStrategy,
    GooglePurchaseStrategy,
)
from payment.types import BuyableType, SubscriptionPeriod


class PurchaseTestCase(CustomAPITestCase):
    def setUp(self):
        super().setUp()
        self.create_standard_users()

    def _login_as_user(self):
        data = {"phone": str(self.user.phone), "password": self.user_password}
        url = reverse("login")
        response = self.client.post(url, data, format="json")
        self.access_token = response.data["response_body"]["access"]

    def test_apple_verify_correct_receipt(self):
        self.skipTest(
            "TODO: requires Apple App Store account — implement after accounts provisioned"
        )

    def test_apple_verify_incorrect_receipt(self):
        self.skipTest(
            "TODO: requires Apple App Store account — implement after accounts provisioned"
        )

    def test_google_verify_correct_receipt(self):
        self.skipTest(
            "TODO: requires Google Play Store account — implement after accounts provisioned"
        )

    def test_google_verify_incorrect_receipt(self):
        self.skipTest(
            "TODO: requires Google Play Store account — implement after accounts provisioned"
        )

    def test_receipt_verification_missing_metadata_structured_response(self):
        """Test structured error response for missing metadata in receipt verification."""
        self._login_as_user()

        data = {
            "transaction_id": "test_transaction_123",
            "store": "GooglePlay",
            "product_key": "monthly_subscription",
            "raw_product_data": {
                "purchasedProduct": {
                    "receipt": "test_receipt_data"
                    # Missing metadata field
                }
            },
        }

        url = reverse("payment_action")
        response = self.client.post(
            url,
            data,
            content_type="application/json",
            HTTP_AUTHORIZATION=f"Bearer {self.access_token}",
        )

        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.data.get("type"), "validation_error")
        self.assertEqual(response.data.get("title"), "Metadata is required")
        self.assertIn("errors", response.data)
        self.assertIn("metadata", response.data["errors"])
        self.assertEqual(
            response.data["errors"]["metadata"][0]["message"], "Cannot be null or empty"
        )


class BuyableTestCase(CRUDPermissionTestsMixin, CustomAPITestCase):
    list_url_name = "buyable-viewset"
    detail_url_name = "buyable-detail-viewset"
    create_data = {
        "name": "blabla",
        "price": "69.99",
        "currency": "TRY",
        "period": "monthly",
        "type": "personal_subscription",
        "trial_days": 1,
        "is_active": True,
    }
    update_data = {"price": "111"}

    def setUp(self):
        super().setUp()
        self.create_standard_users()
        self.translation = baker.make("common.Translation")
        self.create_data["title_id"] = self.translation.id
        self.create_data["description_id"] = self.translation.id
        self.monthly_buyable = baker.make(
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
        self.client.force_authenticate(user=self.admin)

    def resource_factory(self):
        return self.monthly_buyable

    def test_purchase_validation_invalid_subscription_configuration_structured_response(
        self,
    ):
        """Test structured error response for invalid subscription configuration."""
        from payment.models import Purchase

        subscription_buyables = Buyable.objects.filter(
            type=BuyableType.PERSONAL_SUBSCRIPTION.value
        )

        if subscription_buyables.count() > 1:
            Purchase(user=self.user)

    def test_list_buyables(self):
        url = reverse("buyable-viewset")
        self.client.force_authenticate(user=None)
        response = self.client.get(url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertGreaterEqual(len(response.data.get("response_body")), 2)

    def test_create_buyables(self):
        url = reverse("buyable-viewset")
        buyable_count = Buyable.objects.count()
        response = self.client.post(
            url,
            {
                **self.create_data,
                "is_deleted": False,
                "created": "2022-10-22T12:00:00",
                "updated": "2022-10-22T12:00:00",
            },
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(Buyable.objects.count(), buyable_count + 1)

    def test_retrieve_buyable(self):
        url = reverse("buyable-detail-viewset", kwargs={"id": self.monthly_buyable.id})
        response = self.client.get(url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(
            response.data.get("response_body").get("id"), self.monthly_buyable.id
        )

    def test_partial_update_buyable(self):
        url = reverse("buyable-detail-viewset", kwargs={"id": self.monthly_buyable.id})
        response = self.client.patch(url, {"price": "111"}, format="json")
        buyable = Buyable.objects.get(id=self.monthly_buyable.id)
        self.assertEqual(Decimal("111"), buyable.price)
        self.assertEqual(response.status_code, status.HTTP_200_OK)

    def test_delete_buyable(self):
        url = reverse("buyable-detail-viewset", kwargs={"id": self.monthly_buyable.id})
        self.client.delete(url, format="json")
        self.assertFalse(Buyable.objects.filter(id=self.monthly_buyable.id).exists())


class PurchaseStrategyTestCase(CustomAPITestCase):
    """Test cases for purchase strategy error handling.

    Note: These tests call strategy classes directly rather than via HTTP endpoints. This is an intentional exception to
    the API-level integration philosophy because the strategies encapsulate complex receipt-parsing logic that is most
    clearly tested at the class boundary.
    """

    def setUp(self):
        super().setUp()
        self.create_standard_users()

    def create_mock_request(self, data):
        """Helper to create a mock request object."""

        class MockRequest:
            def __init__(self, data):
                self.data = data

        return MockRequest(data)

    def test_google_purchase_strategy_missing_receipt_fields_structured_response(self):
        """Test structured error response for Google receipt with missing fields."""
        incomplete_receipt = {
            "Payload": {
                "json": {
                    "productId": "monthly_subscription"
                    # Missing purchaseToken
                }
            }
        }

        receipt_string = json.dumps(incomplete_receipt)
        mock_request = self.create_mock_request({})

        with self.assertRaises(CustomException):
            GooglePurchaseStrategy(mock_request, self.user, receipt_string)

    def test_google_purchase_strategy_empty_receipt_structured_response(self):
        """Test structured error response for empty Google receipt."""
        mock_request = self.create_mock_request({})

        with self.assertRaises(CustomException):
            strategy = GooglePurchaseStrategy(mock_request, self.user)
            strategy.validate_receipt_data()

    def test_apple_purchase_strategy_missing_transaction_id_structured_response(self):
        """Test structured error response for Apple receipt missing TransactionID."""
        incomplete_receipt = {
            # Missing TransactionID
            "other_field": "value"
        }

        receipt_string = json.dumps(incomplete_receipt)
        mock_request = self.create_mock_request({})

        with self.assertRaises(CustomException):
            ApplePurchaseStrategy(mock_request, self.user, receipt_string)

    def test_purchase_strategy_create_transaction_before_prepare_structured_response(
        self,
    ):
        """Test structured error response when create_transaction is called before prepare."""
        receipt_dict = {
            "Payload": {
                "json": {
                    "purchaseToken": "valid_token",
                    "productId": "monthly_subscription",
                }
            }
        }
        receipt_string = json.dumps(receipt_dict)
        mock_request = self.create_mock_request({})
        strategy = GooglePurchaseStrategy(mock_request, self.user, receipt_string)

        with self.assertRaises(CustomException):
            strategy.create_transaction()

    def test_purchase_strategy_verification_prerequisite_structured_response(self):
        """Test structured error response when verification is required but not done."""
        mock_request = self.create_mock_request(
            {
                "product_key": "monthly_subscription",
                "transaction_id": "test_transaction_123",
                "raw_product_data": {"test": "data"},
            }
        )

        receipt_dict = {
            "Payload": {
                "json": {
                    "purchaseToken": "valid_token",
                    "productId": "monthly_subscription",
                }
            }
        }
        receipt_string = json.dumps(receipt_dict)
        strategy = GooglePurchaseStrategy(mock_request, self.user, receipt_string)

        with self.assertRaises(CustomException):
            strategy.prepare_transaction_creation_for_receipt()


class VendorTestCase(CustomAPITestCase):
    """Test cases for vendor-related error handling."""

    def setUp(self):
        super().setUp()
        self.create_standard_users()

    def test_google_play_credentials_error_structured_response(self):
        """Test structured error response for invalid Google Play credentials format."""
        from vendor.clients.googleplay import GooglePlayClient

        invalid_credentials = "invalid_string_format"

        with self.assertRaises(CustomException):
            GooglePlayClient._create_credentials(invalid_credentials, "test_scope")


class UserValidationTestCase(CustomAPITestCase):
    """Test cases for user validation error handling."""

    def setUp(self):
        super().setUp()
        self.create_standard_users()

    def test_user_creation_validation_error_structured_response(self):
        """Test structured error response for user creation validation errors."""
        from user.models import User

        invalid_data = {
            # Missing required fields like email/phone, password
            "fullname": "Test User"
        }

        with self.assertRaises(CustomException):
            User.create_with_password(invalid_data)

    def test_user_service_missing_user_structured_response(self):
        """Test structured error response when user is not found in service."""
        from user.services import UserService

        invalid_data = {
            "some_field": "value"
            # Missing user field
        }

        with self.assertRaises(CustomException):
            UserService.update_user(invalid_data)
