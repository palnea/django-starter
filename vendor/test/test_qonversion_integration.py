import time
import uuid
from datetime import datetime
from decimal import Decimal

from dateutil.relativedelta import relativedelta
from mock.mock import patch
from model_bakery import baker

from custom_test.baker_recipes import qonversion_payment_transaction
from custom_test.base_test import CustomAPITestCase
from payment.models import Purchase, PaymentTransaction, Buyable
from payment.types import PaymentStatus, PaymentVendor
from subscription.models import UserSubscription
from subscription.types import SubscriptionStatus
from vendor.notification_handlers.qonversion_notification_handler import (
    QonversionNotificationHandler,
)
from vendor.types import QonversionNotificationType


class QonversionNotificationHandlerTestCase(CustomAPITestCase):
    def setUp(self):
        super().setUp()
        self.create_standard_users()
        self.product = baker.make(
            Buyable, name="qon_product", title=baker.make("common.Translation")
        )
        self.purchase = baker.make(
            Purchase,
            user_id=self.user.id,
            stored_payment_method_id="stored_payment_method_id",
            vendor=PaymentVendor.QONVERSION.value,
            original_transaction_id="qon_original_txn_001",
        )
        self.purchase.buyables.add(self.product)
        self.payment_transaction = qonversion_payment_transaction.make(
            purchase=self.purchase,
            transaction_id="qon_txn_001",
        )

    def _create_qonversion_event(self, event_name, **overrides):
        """Build a Qonversion webhook payload for the given event name."""
        payload = {
            "event_name": event_name,
            "id": str(uuid.uuid4()),
            "custom_user_id": str(self.user.id),
            "user_id": str(self.user.id),
            "product_id": self.product.name,
            "fired_at": int(time.time()),
            "transaction": {
                "id": f"qon_txn_{int(time.time())}",
                "original_id": "qon_original_txn_001",
                "expires_at": int(
                    (datetime.utcnow() + relativedelta(months=1)).timestamp()
                ),
            },
            "price": 10.0,
            "currency": "TRY",
        }
        payload.update(overrides)
        return payload

    def test_subscription_started__subscription_exists(self):
        """Subscription_started with existing subscription should not raise."""
        baker.make(
            UserSubscription,
            user_id=self.user.id,
            buyable_id=self.product.id,
            purchase_id=self.purchase.id,
            expiration_date=datetime.utcnow() + relativedelta(months=1),
            start_date=datetime.utcnow(),
            status=SubscriptionStatus.ACTIVE.value,
            used_trial_days=0,
        )
        payload = self._create_qonversion_event("subscription_started")
        handler = QonversionNotificationHandler(payload)
        handler.handle()

    @patch("vendor.notification_handlers.qonversion_notification_handler.log")
    def test_subscription_started__no_subscription_logs_error(self, m_logger):
        """Subscription_started without subscription should log error."""
        payload = self._create_qonversion_event("subscription_started")
        handler = QonversionNotificationHandler(payload)
        handler.handle()
        m_logger.error.assert_called_once()
        self.assertIn(
            "Notified subscription purchase doesn't exist",
            m_logger.error.call_args[0],
        )

    def test_subscription_renewed__creates_transaction_and_extends(self):
        """Subscription_renewed should create a new PaymentTransaction and extend expiration."""
        subscription = baker.make(
            UserSubscription,
            user_id=self.user.id,
            buyable_id=self.product.id,
            purchase_id=self.purchase.id,
            expiration_date=datetime.utcnow() - relativedelta(minutes=1),
            start_date=datetime.utcnow() - relativedelta(months=1),
            status=SubscriptionStatus.EXPIRED.value,
            used_trial_days=0,
        )
        new_expiration = datetime.utcnow() + relativedelta(months=1)
        payload = self._create_qonversion_event(
            "subscription_renewed",
            transaction={
                "id": "qon_renewal_txn_001",
                "original_id": "qon_original_txn_001",
                "expires_at": int(new_expiration.timestamp()),
            },
        )
        self.assertEqual(self.purchase.payment_transactions.count(), 1)
        handler = QonversionNotificationHandler(payload)
        handler.handle()
        self.assertEqual(self.purchase.payment_transactions.count(), 2)
        subscription.refresh_from_db()
        self.assertGreater(
            subscription.expiration_date,
            datetime.utcnow() + relativedelta(days=26),
        )

    def test_subscription_canceled__sets_canceled_status(self):
        """Subscription_canceled should set subscription status to CANCELED."""
        subscription = baker.make(
            UserSubscription,
            user_id=self.user.id,
            buyable_id=self.product.id,
            purchase_id=self.purchase.id,
            expiration_date=datetime.utcnow() + relativedelta(days=15),
            start_date=datetime.utcnow() - relativedelta(days=15),
            status=SubscriptionStatus.ACTIVE.value,
            used_trial_days=0,
        )
        payload = self._create_qonversion_event("subscription_canceled")
        handler = QonversionNotificationHandler(payload)
        handler.handle()
        subscription.refresh_from_db()
        self.assertEqual(subscription.status, SubscriptionStatus.CANCELED.value)

    def test_subscription_expired__expires_subscription(self):
        """Subscription_expired should set subscription to expired immediately."""
        subscription = baker.make(
            UserSubscription,
            user_id=self.user.id,
            buyable_id=self.product.id,
            purchase_id=self.purchase.id,
            expiration_date=datetime.utcnow() + relativedelta(days=1),
            start_date=datetime.utcnow() - relativedelta(months=1),
            status=SubscriptionStatus.ACTIVE.value,
            used_trial_days=0,
        )
        payload = self._create_qonversion_event("subscription_expired")
        handler = QonversionNotificationHandler(payload)
        handler.handle()
        subscription.refresh_from_db()
        self.assertEqual(subscription.status, SubscriptionStatus.EXPIRED.value)

    def test_subscription_billing_retry__suspends_subscription(self):
        """Subscription_billing_retry should set subscription status to SUSPENDED."""
        subscription = baker.make(
            UserSubscription,
            user_id=self.user.id,
            buyable_id=self.product.id,
            purchase_id=self.purchase.id,
            expiration_date=datetime.utcnow() + relativedelta(days=5),
            start_date=datetime.utcnow() - relativedelta(days=25),
            status=SubscriptionStatus.ACTIVE.value,
            used_trial_days=0,
        )
        payload = self._create_qonversion_event("subscription_billing_retry")
        handler = QonversionNotificationHandler(payload)
        handler.handle()
        subscription.refresh_from_db()
        self.assertEqual(subscription.status, SubscriptionStatus.SUSPENDED.value)

    def test_trial_canceled__sets_canceled_status(self):
        """Trial_canceled should set subscription status to CANCELED."""
        subscription = baker.make(
            UserSubscription,
            user_id=self.user.id,
            buyable_id=self.product.id,
            purchase_id=self.purchase.id,
            expiration_date=datetime.utcnow() + relativedelta(days=5),
            start_date=datetime.utcnow() - relativedelta(days=2),
            status=SubscriptionStatus.ACTIVE.value,
            used_trial_days=7,
        )
        payload = self._create_qonversion_event("trial_canceled")
        handler = QonversionNotificationHandler(payload)
        handler.handle()
        subscription.refresh_from_db()
        self.assertEqual(subscription.status, SubscriptionStatus.CANCELED.value)

    def test_trial_expired__expires_subscription(self):
        """Trial_expired should set subscription to expired."""
        subscription = baker.make(
            UserSubscription,
            user_id=self.user.id,
            buyable_id=self.product.id,
            purchase_id=self.purchase.id,
            expiration_date=datetime.utcnow() + relativedelta(days=1),
            start_date=datetime.utcnow() - relativedelta(days=6),
            status=SubscriptionStatus.ACTIVE.value,
            used_trial_days=7,
        )
        payload = self._create_qonversion_event("trial_expired")
        handler = QonversionNotificationHandler(payload)
        handler.handle()
        subscription.refresh_from_db()
        self.assertEqual(subscription.status, SubscriptionStatus.EXPIRED.value)

    @patch("vendor.notification_handlers.qonversion_notification_handler.log")
    def test_subscription_refunded__logs_and_expires(self, m_logger):
        """Subscription_refunded should log and expire the subscription."""
        subscription = baker.make(
            UserSubscription,
            user_id=self.user.id,
            buyable_id=self.product.id,
            purchase_id=self.purchase.id,
            expiration_date=datetime.utcnow() + relativedelta(days=10),
            start_date=datetime.utcnow() - relativedelta(days=20),
            status=SubscriptionStatus.ACTIVE.value,
            used_trial_days=0,
        )
        payload = self._create_qonversion_event("subscription_refunded")
        handler = QonversionNotificationHandler(payload)
        handler.handle()
        m_logger.info.assert_called_once()
        self.assertIn(
            "Qonversion refund event received",
            m_logger.info.call_args[0],
        )
        subscription.refresh_from_db()
        self.assertEqual(subscription.status, SubscriptionStatus.EXPIRED.value)

    @patch("vendor.notification_handlers.qonversion_notification_handler.log")
    def test_trial_converted__logs_event(self, m_logger):
        """Trial_converted should log the event."""
        payload = self._create_qonversion_event("trial_converted")
        handler = QonversionNotificationHandler(payload)
        handler.handle()
        m_logger.info.assert_called_once()
        self.assertIn(
            "Qonversion trial converted event received",
            m_logger.info.call_args[0],
        )

    @patch("vendor.notification_handlers.qonversion_notification_handler.log")
    def test_in_app_purchase__logs_event(self, m_logger):
        """In_app_purchase should log the event."""
        payload = self._create_qonversion_event("in_app_purchase")
        handler = QonversionNotificationHandler(payload)
        handler.handle()
        m_logger.info.assert_called_once()
        self.assertIn(
            "Qonversion in-app purchase event received",
            m_logger.info.call_args[0],
        )

    def test_trial_still_active__no_op(self):
        """Trial_still_active event should complete without error."""
        payload = self._create_qonversion_event("trial_still_active")
        handler = QonversionNotificationHandler(payload)
        handler.handle()

    def test_unknown_event_type__no_op(self):
        """Unknown event type should be handled gracefully."""
        payload = self._create_qonversion_event("some_future_event_type")
        handler = QonversionNotificationHandler(payload)
        handler.handle()
