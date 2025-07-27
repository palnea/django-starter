from decimal import Decimal

from django.urls import reverse
from model_bakery import baker
from rest_framework import status

from custom_test.base_test import CustomIntegrationTestCase
from payment.models import Buyable
from payment.subscription.strategies import (
    GooglePurchaseStrategy,
    ApplePurchaseStrategy,
)
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

    def test_receipt_verification_missing_metadata_structured_response(self):
        """Test structured error response for missing metadata in receipt verification"""
        self.login_user()

        # Create a receipt with missing metadata
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
        # Validate structured error response
        self.assertEqual(response.data.get("type"), "validation_error")
        self.assertEqual(response.data.get("title"), "Metadata is required")
        self.assertIn("errors", response.data)
        self.assertIn("metadata", response.data["errors"])
        self.assertEqual(
            response.data["errors"]["metadata"][0]["message"], "Cannot be null or empty"
        )


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

    def test_purchase_validation_invalid_subscription_configuration_structured_response(
        self,
    ):
        """Test structured error response for invalid subscription configuration"""
        # This would test the business logic error in Purchase.save() method
        # when trying to add multiple subscription buyables

        # First, we need to simulate the scenario that triggers this error
        # This is more of a model-level test that would be triggered during model save
        from payment.models import Purchase

        # Create multiple subscription buyables
        subscription_buyables = Buyable.objects.filter(
            type=BuyableType.PERSONAL_SUBSCRIPTION.value
        )

        if subscription_buyables.count() > 1:
            purchase = Purchase(user=self.user)
            # This test would need to be implemented at the model level
            # as it's triggered during the save() method validation
            pass

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


class PurchaseStrategyTestCase(CustomIntegrationTestCase):
    """Test cases for purchase strategy error handling"""

    def setUp(self):
        super().setUp()
        self.create_common_models()

    def create_mock_request(self, data):
        """Helper to create a mock request object"""

        class MockRequest:
            def __init__(self, data):
                self.data = data

        return MockRequest(data)

    def test_google_purchase_strategy_missing_receipt_fields_structured_response(self):
        """Test structured error response for Google receipt with missing fields"""

        # Test receipt missing purchaseToken
        incomplete_receipt = {
            "Payload": {
                "json": {
                    "productId": "monthly_subscription"
                    # Missing purchaseToken
                }
            }
        }

        import json

        receipt_string = json.dumps(incomplete_receipt)
        mock_request = self.create_mock_request({})

        try:
            GooglePurchaseStrategy(mock_request, self.user, receipt_string)
            self.fail("Should have raised CustomException for missing fields")
        except Exception as e:
            # Verify it's our structured error
            self.assertEqual(str(e.__class__.__name__), "CustomException")
            # The error should be business_logic_error type when handled by exception handler

    def test_google_purchase_strategy_empty_receipt_structured_response(self):
        """Test structured error response for empty Google receipt"""

        mock_request = self.create_mock_request({})

        try:
            strategy = GooglePurchaseStrategy(mock_request, self.user)
            strategy.validate_receipt_data()  # This should fail with empty receipt
            self.fail("Should have raised CustomException for empty receipt")
        except Exception as e:
            # Verify it's our structured error
            self.assertEqual(str(e.__class__.__name__), "CustomException")

    def test_apple_purchase_strategy_missing_transaction_id_structured_response(self):
        """Test structured error response for Apple receipt missing TransactionID"""

        incomplete_receipt = {
            # Missing TransactionID
            "other_field": "value"
        }

        import json

        receipt_string = json.dumps(incomplete_receipt)
        mock_request = self.create_mock_request({})

        try:
            ApplePurchaseStrategy(mock_request, self.user, receipt_string)
            self.fail("Should have raised CustomException for missing TransactionID")
        except Exception as e:
            # Verify it's our structured error
            self.assertEqual(str(e.__class__.__name__), "CustomException")

    def test_purchase_strategy_create_transaction_before_prepare_structured_response(
        self,
    ):
        """Test structured error response when create_transaction is called before prepare"""

        import json

        # Provide valid receipt structure that passes constructor validation
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

        try:
            # Try to create transaction without preparing first
            strategy.create_transaction()
            self.fail(
                "Should have raised CustomException for calling create_transaction before prepare"
            )
        except Exception as e:
            # Verify it's our structured error
            self.assertEqual(str(e.__class__.__name__), "CustomException")

    def test_purchase_strategy_verification_prerequisite_structured_response(self):
        """Test structured error response when verification is required but not done"""

        mock_request = self.create_mock_request(
            {
                "product_key": "monthly_subscription",
                "transaction_id": "test_transaction_123",
                "raw_product_data": {"test": "data"},
            }
        )

        import json

        # Provide valid receipt structure that passes constructor validation
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

        try:
            # Try to prepare transaction without verification
            strategy.prepare_transaction_creation_for_receipt()
            self.fail("Should have raised CustomException for missing verification")
        except Exception as e:
            # Verify it's our structured error
            self.assertEqual(str(e.__class__.__name__), "CustomException")


class VendorTestCase(CustomIntegrationTestCase):
    """Test cases for vendor-related error handling"""

    def setUp(self):
        super().setUp()
        self.create_common_models()

    def test_google_play_credentials_error_structured_response(self):
        """Test structured error response for invalid Google Play credentials format"""
        from vendor.clients.googleplay import GooglePlayClient

        # Test with invalid credentials format
        invalid_credentials = "invalid_string_format"  # Should be dict

        try:
            GooglePlayClient._create_credentials(invalid_credentials, "test_scope")
            self.fail(
                "Should have raised CustomException for invalid credentials format"
            )
        except Exception as e:
            # Verify it's our structured error
            self.assertEqual(str(e.__class__.__name__), "CustomException")
            # The error should be business_logic_error type when handled by exception handler


class UserValidationTestCase(CustomIntegrationTestCase):
    """Test cases for user validation error handling"""

    def setUp(self):
        super().setUp()
        self.create_common_models()

    def test_user_creation_validation_error_structured_response(self):
        """Test structured error response for user creation validation errors"""
        from user.models import User

        # Test creating user with invalid data that triggers validation errors
        invalid_data = {
            # Missing required fields like email/phone, password
            "fullname": "Test User"
        }

        try:
            User.create_with_password(invalid_data)
            self.fail("Should have raised CustomException for validation errors")
        except Exception as e:
            # Verify it's our structured error
            self.assertEqual(str(e.__class__.__name__), "CustomException")

    def test_user_service_missing_user_structured_response(self):
        """Test structured error response when user is not found in service"""
        from user.services import UserService

        # Test with data missing user
        invalid_data = {
            "some_field": "value"
            # Missing user field
        }

        try:
            UserService.update_user(invalid_data)
            self.fail("Should have raised CustomException for missing user")
        except Exception as e:
            # Verify it's our structured error
            self.assertEqual(str(e.__class__.__name__), "CustomException")
