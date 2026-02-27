from django.urls import reverse
from mock.mock import patch, MagicMock
from model_bakery import baker
from rest_framework import status

from common.custom_exceptions.custom_exception import CustomException
from custom_test.base_test import CustomAPITestCase
from payment.models import Buyable
from payment.subscription.qonversion_strategy import QonversionPurchaseStrategy


class QonversionPurchaseStrategyTestCase(CustomAPITestCase):
    """Test cases for Qonversion purchase strategy."""

    def setUp(self):
        super().setUp()
        self.create_standard_users()
        self.translation = baker.make("common.Translation")
        self.buyable = baker.make(
            Buyable,
            name="qon_monthly",
            price=10,
            currency="TRY",
            title=self.translation,
        )

    def create_mock_request(self, data):
        class MockRequest:
            def __init__(self, data):
                self.data = data

        return MockRequest(data)

    @patch("payment.subscription.qonversion_strategy.QonversionClient")
    def test_verify__product_found_in_entitlements(self, MockClient):
        """Verify() succeeds when product exists in user's entitlements."""
        mock_instance = MockClient.return_value
        mock_instance.get_user_entitlements.return_value = {
            "data": [
                {
                    "active": True,
                    "product": {
                        "product_id": "qon_monthly",
                    },
                    "expires": 1735689600,
                    "source": "app_store",
                }
            ]
        }

        mock_request = self.create_mock_request(
            {
                "product_key": "qon_monthly",
                "receipt": "{}",
            }
        )
        strategy = QonversionPurchaseStrategy(mock_request, self.user)
        result, is_valid = strategy.verify()

        self.assertTrue(is_valid)
        self.assertEqual(result["product_key"], "qon_monthly")

    @patch("payment.subscription.qonversion_strategy.QonversionClient")
    def test_verify__product_not_found_raises(self, MockClient):
        """Verify() raises CustomException when product not found in entitlements."""
        mock_instance = MockClient.return_value
        mock_instance.get_user_entitlements.return_value = {"data": []}

        mock_request = self.create_mock_request(
            {
                "product_key": "qon_monthly",
                "receipt": "{}",
            }
        )
        strategy = QonversionPurchaseStrategy(mock_request, self.user)

        with self.assertRaises(CustomException):
            strategy.verify()

    def test_prepare_transaction_before_verify__raises(self):
        """Prepare_transaction_creation_for_receipt() raises when called before verify()."""
        mock_request = self.create_mock_request(
            {
                "product_key": "qon_monthly",
                "transaction_id": "qon_txn_001",
                "raw_product_data": {"test": "data"},
                "receipt": "{}",
            }
        )
        strategy = QonversionPurchaseStrategy(mock_request, self.user)

        with self.assertRaises(CustomException):
            strategy.prepare_transaction_creation_for_receipt()

    def test_create_transaction_before_prepare__raises(self):
        """Create_transaction() raises when called before prepare."""
        mock_request = self.create_mock_request(
            {
                "receipt": "{}",
            }
        )
        strategy = QonversionPurchaseStrategy(mock_request, self.user)

        with self.assertRaises(CustomException):
            strategy.create_transaction()


class QonversionWebhookViewTestCase(CustomAPITestCase):
    """Test cases for Qonversion webhook endpoint."""

    def setUp(self):
        super().setUp()
        self.create_standard_users()
        self.url = reverse("qonversion-webhook-viewset")

    @patch(
        "payment.views.QonversionNotificationVerifier.verify_authorization",
        return_value=True,
    )
    @patch("payment.views.QonversionNotificationHandler")
    def test_webhook__valid_auth_processes_event(self, MockHandler, mock_auth):
        """Webhook with valid auth should process the event."""
        mock_handler_instance = MockHandler.return_value
        mock_handler_instance.handle.return_value = None

        payload = {
            "event_name": "subscription_started",
            "id": "test-event-id",
        }
        response = self.client.post(
            self.url,
            payload,
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        MockHandler.assert_called_once()
        mock_handler_instance.handle.assert_called_once()

    @patch(
        "payment.views.QonversionNotificationVerifier.verify_authorization",
        return_value=False,
    )
    @patch("payment.views.QonversionNotificationHandler")
    def test_webhook__invalid_auth_returns_200_no_processing(
        self, MockHandler, mock_auth
    ):
        """Webhook with invalid auth should return 200 but not process."""
        payload = {
            "event_name": "subscription_renewed",
            "id": "test-event-id",
        }
        response = self.client.post(
            self.url,
            payload,
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        MockHandler.assert_not_called()

    @patch(
        "payment.views.QonversionNotificationVerifier.verify_authorization",
        return_value=True,
    )
    @patch(
        "payment.views.QonversionNotificationHandler",
        side_effect=Exception("Unexpected error"),
    )
    def test_webhook__handler_exception_returns_200(self, MockHandler, mock_auth):
        """Webhook should return 200 even if handler raises an exception."""
        payload = {
            "event_name": "subscription_renewed",
            "id": "test-event-id",
        }
        response = self.client.post(
            self.url,
            payload,
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)

    def test_webhook__missing_auth_header_returns_200(self):
        """Webhook without auth header should return 200 (no processing)."""
        with patch(
            "payment.views.QonversionNotificationVerifier.verify_authorization",
            return_value=False,
        ):
            payload = {
                "event_name": "subscription_renewed",
                "id": "test-event-id",
            }
            response = self.client.post(
                self.url,
                payload,
                format="json",
            )
            self.assertEqual(response.status_code, status.HTTP_200_OK)
