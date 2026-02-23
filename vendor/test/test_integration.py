import base64
import json
import time
from datetime import datetime
from decimal import Decimal

from dateutil.relativedelta import relativedelta
from mock.mock import patch, call, MagicMock
from model_bakery import baker

from custom_test.baker_recipes import (
    apple_payment_transaction,
    google_payment_transaction,
)
from custom_test.base_test import CustomAPITestCase
from payment.models import Purchase, PaymentTransaction, Buyable
from payment.types import PaymentStatus, PaymentVendor
from subscription.models import UserSubscription
from subscription.types import SubscriptionStatus
from user.models import User
from vendor.notification_handlers.subscription_notification_handlers import (
    GoogleNotificationHandler,
    AppleNotificationHandler,
)
from vendor.types import (
    GooglePlayNotificationSubtype,
    GooglePlayNotificationType,
    AppStoreNotificationType,
    AppStoreNotificationSubtype,
    StoreNotificationVerificationResult,
)
from vendor.verifiers.app_store_notification_verifier import (
    AppStoreNotificationVerifier,
)


class GoogleNotificationHandlerTestCase(CustomAPITestCase):
    def setUp(self):
        super().setUp()
        self.create_standard_users()
        self.product = baker.make(
            Buyable, name="product", title=baker.make("common.Translation")
        )
        self.purchase = baker.make(
            Purchase,
            user_id=self.user.id,
            stored_payment_method_id="stored_payment_method_id",
        )
        self.purchase.buyables.add(self.product)
        self.payment_transaction = google_payment_transaction.make(
            purchase=self.purchase,
            transaction_id="eepidalpoicklfckkpfjneki.AO-J1OyjGN_Vps_gJ7oSfJtwfYRZTW_SZGbCm1_JnSwI0Gt4ByCnMhWOi31AWRMCD1aOY34pFO7Ifm5TDdVMPZL62_FJuYurNA",
        )

    def _create_subscription_notification(self, notification_type):
        data = {
            "version": "1.0",
            "packageName": "com.funly",
            "eventTimeMillis": "1697914281064",
            "subscriptionNotification": {
                "version": "1.0",
                "notificationType": notification_type,
                "purchaseToken": self.payment_transaction.transaction_id,
                "subscriptionId": self.product.name,
            },
        }
        base64_data = base64.urlsafe_b64encode(json.dumps(data).encode()).decode()
        google_message = {
            "message": {
                "data": base64_data,
                "messageId": "8911304750060604",
                "message_id": "8911304750060604",
                "publishTime": "2023-10-21T18:51:21.297Z",
                "publish_time": "2023-10-21T18:51:21.297Z",
            },
            "subscription": "projects/funly/subscriptions/funly-subscription",
        }
        return google_message

    def test_subscription_recovered(self):
        subscription = baker.make(
            UserSubscription,
            user_id=self.user.id,
            buyable_id=self.product.id,
            purchase_id=self.purchase.id,
            expiration_date=datetime.utcnow() - relativedelta(days=1),
            start_date=datetime.utcnow() - relativedelta(months=1),
            status=SubscriptionStatus.EXPIRED.value,
            used_trial_days=7,
        )
        google_message = self._create_subscription_notification(
            GooglePlayNotificationSubtype.SUBSCRIPTION_RECOVERED.value
        )
        self.assertEqual(self.purchase.payment_transactions.count(), 1)
        handler = GoogleNotificationHandler(google_message)
        handler.handle()
        subscription = UserSubscription.objects.get(id=subscription.id)
        self.assertEqual(self.purchase.payment_transactions.count(), 2)
        self.assertEqual(subscription.status, SubscriptionStatus.ACTIVE.value)
        self.assertGreater(
            subscription.expiration_date, datetime.utcnow() + relativedelta(days=26)
        )
        self.assertEqual(subscription.change_history.count(), 1)

    def test_subscription_renewed(self):
        subscription = baker.make(
            UserSubscription,
            user_id=self.user.id,
            buyable_id=self.product.id,
            purchase_id=self.purchase.id,
            expiration_date=datetime.utcnow() - relativedelta(minutes=1),
            start_date=datetime.utcnow() - relativedelta(months=1),
            status=SubscriptionStatus.EXPIRED.value,
            used_trial_days=7,
        )
        google_message = self._create_subscription_notification(
            GooglePlayNotificationSubtype.SUBSCRIPTION_RENEWED.value
        )
        self.assertEqual(self.purchase.payment_transactions.count(), 1)
        handler = GoogleNotificationHandler(google_message)
        handler.handle()
        subscription = UserSubscription.objects.get(id=subscription.id)
        self.assertEqual(self.purchase.payment_transactions.count(), 2)
        self.assertEqual(subscription.status, SubscriptionStatus.ACTIVE.value)
        self.assertGreater(
            subscription.expiration_date, datetime.utcnow() + relativedelta(days=26)
        )
        self.assertEqual(subscription.change_history.count(), 1)

    def test_active_subscription_renewed(self):
        subscription = baker.make(
            UserSubscription,
            user_id=self.user.id,
            buyable_id=self.product.id,
            purchase_id=self.purchase.id,
            expiration_date=datetime.utcnow() + relativedelta(days=3),
            start_date=datetime.utcnow() - relativedelta(months=1),
            status=SubscriptionStatus.ACTIVE.value,
            used_trial_days=7,
        )
        google_message = self._create_subscription_notification(
            GooglePlayNotificationSubtype.SUBSCRIPTION_RENEWED.value
        )
        self.assertEqual(self.purchase.payment_transactions.count(), 1)
        handler = GoogleNotificationHandler(google_message)
        handler.handle()
        subscription = UserSubscription.objects.get(id=subscription.id)
        self.assertEqual(self.purchase.payment_transactions.count(), 2)
        self.assertEqual(subscription.status, SubscriptionStatus.ACTIVE.value)
        self.assertGreater(
            subscription.expiration_date, datetime.utcnow() + relativedelta(days=26)
        )

    def test_subscription_cancellation(self):
        subscription = baker.make(
            UserSubscription,
            user_id=self.user.id,
            buyable_id=self.product.id,
            purchase_id=self.purchase.id,
            expiration_date=datetime.utcnow() + relativedelta(days=15),
            start_date=datetime.utcnow() - relativedelta(days=15),
            status=SubscriptionStatus.ACTIVE.value,
            used_trial_days=7,
        )
        google_message = self._create_subscription_notification(
            GooglePlayNotificationSubtype.SUBSCRIPTION_CANCELED.value
        )
        handler = GoogleNotificationHandler(google_message)
        handler.handle()
        subscription = UserSubscription.objects.get(id=subscription.id)
        self.assertEqual(subscription.status, SubscriptionStatus.CANCELED.value)
        self.assertEqual(subscription.change_history.count(), 1)

    def test_subscription_purchased(self):
        baker.make(
            UserSubscription,
            user_id=self.user.id,
            buyable_id=self.product.id,
            purchase_id=self.purchase.id,
            expiration_date=datetime.utcnow() + relativedelta(months=1),
            start_date=datetime.utcnow() - relativedelta(minutes=5),
            status=SubscriptionStatus.ACTIVE.value,
            used_trial_days=7,
        )
        google_message = self._create_subscription_notification(
            GooglePlayNotificationSubtype.SUBSCRIPTION_PURCHASED.value
        )
        handler = GoogleNotificationHandler(google_message)
        handler.handle()

    @patch("vendor.notification_handlers.subscription_notification_handlers.log")
    def test_subscription_purchased_no_subscription_log(self, m_logger):
        google_message = self._create_subscription_notification(
            GooglePlayNotificationSubtype.SUBSCRIPTION_PURCHASED.value
        )
        handler = GoogleNotificationHandler(google_message)
        handler.handle()
        m_logger.error.assert_called_with(
            "Notified subscription purchase doesn't exist",
            vendor="GooglePlay",
            payment_transaction_id=self.payment_transaction.id,
            vendor_transaction_id="eepidalpoicklfckkpfjneki.AO-J1OyjGN_Vps_gJ7oSfJtwfYRZTW_SZGbCm1_JnSwI0Gt4ByCnMhWOi31AWRMCD1aOY34pFO7Ifm5TDdVMPZL62_FJuYurNA",
            notification_type=GooglePlayNotificationType.SUBSCRIPTION_NOTIFICATION.value,
            notification_subtype=GooglePlayNotificationSubtype.SUBSCRIPTION_PURCHASED.value,
            notification_id=google_message.get("message").get("messageId"),
        )

    def test_subscription_on_hold(self):
        subscription = baker.make(
            UserSubscription,
            user_id=self.user.id,
            buyable_id=self.product.id,
            purchase_id=self.purchase.id,
            expiration_date=datetime.utcnow() - relativedelta(days=7),
            start_date=datetime.utcnow() - relativedelta(days=37),
            status=SubscriptionStatus.ACTIVE.value,
            used_trial_days=7,
        )
        google_message = self._create_subscription_notification(
            GooglePlayNotificationSubtype.SUBSCRIPTION_ON_HOLD.value
        )
        handler = GoogleNotificationHandler(google_message)
        handler.handle()
        subscription = UserSubscription.objects.get(id=subscription.id)
        self.assertEqual(subscription.status, SubscriptionStatus.SUSPENDED.value)
        self.assertEqual(subscription.change_history.count(), 1)

    def test_subscription_in_grace_period(self):
        subscription = baker.make(
            UserSubscription,
            user_id=self.user.id,
            buyable_id=self.product.id,
            purchase_id=self.purchase.id,
            expiration_date=datetime.utcnow() - relativedelta(days=1),
            start_date=datetime.utcnow() - relativedelta(days=31),
            status=SubscriptionStatus.ACTIVE.value,
            used_trial_days=7,
        )
        google_message = self._create_subscription_notification(
            GooglePlayNotificationSubtype.SUBSCRIPTION_IN_GRACE_PERIOD.value
        )
        handler = GoogleNotificationHandler(google_message)
        handler.handle()
        subscription = UserSubscription.objects.get(id=subscription.id)
        self.assertEqual(subscription.status, SubscriptionStatus.ACTIVE.value)

    def test_subscription_in_grace_period_expired(self):
        subscription = baker.make(
            UserSubscription,
            user_id=self.user.id,
            buyable_id=self.product.id,
            purchase_id=self.purchase.id,
            expiration_date=datetime.utcnow() - relativedelta(days=1),
            start_date=datetime.utcnow() - relativedelta(days=31),
            status=SubscriptionStatus.EXPIRED.value,
            used_trial_days=7,
        )
        google_message = self._create_subscription_notification(
            GooglePlayNotificationSubtype.SUBSCRIPTION_IN_GRACE_PERIOD.value
        )
        handler = GoogleNotificationHandler(google_message)
        handler.handle()
        subscription = UserSubscription.objects.get(id=subscription.id)
        self.assertEqual(subscription.status, SubscriptionStatus.ACTIVE.value)

    def test_subscription_restarted(self):
        subscription = baker.make(
            UserSubscription,
            user_id=self.user.id,
            buyable_id=self.product.id,
            purchase_id=self.purchase.id,
            expiration_date=datetime.utcnow() - relativedelta(days=1),
            start_date=datetime.utcnow() - relativedelta(days=31),
            status=SubscriptionStatus.EXPIRED.value,
            used_trial_days=7,
        )
        google_message = self._create_subscription_notification(
            GooglePlayNotificationSubtype.SUBSCRIPTION_RESTARTED.value
        )
        self.assertEqual(self.user.has_active_subscription, False)
        handler = GoogleNotificationHandler(google_message)
        handler.handle()
        subscription = UserSubscription.objects.get(id=subscription.id)
        user = User.objects.get(id=self.user.id)
        self.assertEqual(subscription.status, SubscriptionStatus.ACTIVE.value)
        self.assertEqual(user.has_active_subscription, True)
        self.assertGreater(
            user.active_subscription.expiration_date,
            datetime.utcnow() + relativedelta(days=26),
        )

    @patch("vendor.clients.googleplay.ServiceAccountCredentials.from_json_keyfile_dict")
    @patch("vendor.notification_handlers.subscription_notification_handlers.log")
    @patch("vendor.clients.googleplay.build")
    def test_subscription_price_change_confirmed(
        self, m_build, m_logger, m_from_json_keyfile_dict
    ):
        m_from_json_keyfile_dict.return_value = MagicMock()
        price_micros = 1000000
        price_currency = "USD"
        mock_subscriptions = m_build.return_value.purchases().subscriptions().get()
        notification_type = (
            GooglePlayNotificationSubtype.SUBSCRIPTION_PRICE_CHANGE_CONFIRMED.value
        )
        mock_subscriptions.execute.return_value = {
            "kind": "androidpublisher#subscriptionPurchase",
            "startTimeMillis": "1643724800000",
            "expiryTimeMillis": "1646316800000",
            "autoRenewing": False,
            "priceChange": {
                "newPrice": {
                    "currency": price_currency,
                    "priceMicros": str(price_micros),
                }
            },
            "countryCode": "US",
            "developerPayload": "payload",
            "paymentState": 1,
        }
        baker.make(
            UserSubscription,
            user_id=self.user.id,
            buyable_id=self.product.id,
            purchase_id=self.purchase.id,
            expiration_date=datetime.utcnow() - relativedelta(days=1),
            start_date=datetime.utcnow() - relativedelta(days=31),
            status=SubscriptionStatus.EXPIRED.value,
            used_trial_days=7,
        )
        google_message = self._create_subscription_notification(
            notification_type=notification_type
        )
        handler = GoogleNotificationHandler(google_message)
        handler.handle()
        m_logger.info.assert_has_calls(
            [
                call(
                    "User accepted price change",
                    price=Decimal(price_micros / 1000000),
                    currency=price_currency,
                    vendor=PaymentVendor.GOOGLE.value,
                    payment_transaction_id=self.payment_transaction.id,
                    vendor_transaction_id=self.payment_transaction.transaction_id,
                    notification_type=GooglePlayNotificationType.SUBSCRIPTION_NOTIFICATION.value,
                    notification_subtype=notification_type,
                    notification_id=google_message.get("message").get("messageId"),
                )
            ]
        )

    @patch("vendor.clients.googleplay.ServiceAccountCredentials.from_json_keyfile_dict")
    @patch("vendor.clients.googleplay.build")
    def test_subscription_deferred(self, m_build, m_from_json_keyfile_dict):
        m_from_json_keyfile_dict.return_value = MagicMock()

        price_micros = 1000000
        price_currency = "USD"
        ten_days_in_millis = 864000000
        expiry_time_millis = int(time.time()) * 1000 + ten_days_in_millis
        mock_subscriptions = m_build.return_value.purchases().subscriptions().get()
        notification_type = GooglePlayNotificationSubtype.SUBSCRIPTION_DEFERRED.value
        mock_subscriptions.execute.return_value = {
            "kind": "androidpublisher#subscriptionPurchase",
            "startTimeMillis": "1643724800000",
            "expiryTimeMillis": str(expiry_time_millis),
            "autoRenewing": False,
            "priceChange": {
                "newPrice": {
                    "currency": price_currency,
                    "priceMicros": str(price_micros),
                }
            },
            "countryCode": "US",
            "developerPayload": "payload",
            "paymentState": 1,
        }
        subscription = baker.make(
            UserSubscription,
            user_id=self.user.id,
            buyable_id=self.product.id,
            purchase_id=self.purchase.id,
            expiration_date=datetime.utcnow() + relativedelta(days=2),
            start_date=datetime.utcnow() - relativedelta(days=28),
            status=SubscriptionStatus.ACTIVE.value,
            used_trial_days=7,
        )
        google_message = self._create_subscription_notification(
            notification_type=notification_type
        )
        handler = GoogleNotificationHandler(google_message)
        handler.handle()
        updated_subscription = UserSubscription.objects.get(id=subscription.id)
        self.assertEqual(
            updated_subscription.expiration_date,
            datetime.utcfromtimestamp(expiry_time_millis / 1000.0),
        )

    def test_subscription_paused(self):
        subscription = baker.make(
            UserSubscription,
            user_id=self.user.id,
            buyable_id=self.product.id,
            purchase_id=self.purchase.id,
            expiration_date=datetime.utcnow() - relativedelta(days=1),
            start_date=datetime.utcnow() - relativedelta(days=31),
            status=SubscriptionStatus.ACTIVE.value,
            used_trial_days=7,
        )
        google_message = self._create_subscription_notification(
            GooglePlayNotificationSubtype.SUBSCRIPTION_PAUSED.value
        )
        self.assertEqual(self.user.has_active_subscription, True)
        handler = GoogleNotificationHandler(google_message)
        handler.handle()
        subscription = UserSubscription.objects.get(id=subscription.id)
        user = User.objects.get(id=self.user.id)
        self.assertEqual(subscription.status, SubscriptionStatus.SUSPENDED.value)
        self.assertEqual(user.has_active_subscription, False)

    def test_subscription_pause_schedule_changed(self):
        subscription = baker.make(
            UserSubscription,
            user_id=self.user.id,
            buyable_id=self.product.id,
            purchase_id=self.purchase.id,
            expiration_date=datetime.utcnow() + relativedelta(days=15),
            start_date=datetime.utcnow() - relativedelta(days=15),
            status=SubscriptionStatus.SUSPENDED.value,
            used_trial_days=7,
        )
        google_message = self._create_subscription_notification(
            GooglePlayNotificationSubtype.SUBSCRIPTION_PAUSE_SCHEDULE_CHANGED.value
        )
        self.assertEqual(self.user.has_active_subscription, False)
        handler = GoogleNotificationHandler(google_message)
        handler.handle()
        subscription = UserSubscription.objects.get(id=subscription.id)
        user = User.objects.get(id=self.user.id)
        self.assertEqual(subscription.status, SubscriptionStatus.ACTIVE.value)
        self.assertEqual(user.has_active_subscription, True)

    def test_subscription_revoked(self):
        subscription = baker.make(
            UserSubscription,
            user_id=self.user.id,
            buyable_id=self.product.id,
            purchase_id=self.purchase.id,
            expiration_date=datetime.utcnow() + relativedelta(days=15),
            start_date=datetime.utcnow() - relativedelta(days=15),
            status=SubscriptionStatus.ACTIVE.value,
            used_trial_days=7,
        )
        google_message = self._create_subscription_notification(
            GooglePlayNotificationSubtype.SUBSCRIPTION_REVOKED.value
        )
        self.assertEqual(self.user.has_active_subscription, True)
        handler = GoogleNotificationHandler(google_message)
        handler.handle()
        subscription = UserSubscription.objects.get(id=subscription.id)
        user = User.objects.get(id=self.user.id)
        self.assertEqual(subscription.status, SubscriptionStatus.EXPIRED.value)
        self.assertEqual(user.has_active_subscription, False)

    def test_subscription_expired(self):
        subscription = baker.make(
            UserSubscription,
            user_id=self.user.id,
            buyable_id=self.product.id,
            purchase_id=self.purchase.id,
            expiration_date=datetime.utcnow() - relativedelta(days=1),
            start_date=datetime.utcnow() - relativedelta(days=31),
            status=SubscriptionStatus.ACTIVE.value,
            used_trial_days=7,
        )
        google_message = self._create_subscription_notification(
            GooglePlayNotificationSubtype.SUBSCRIPTION_EXPIRED.value
        )
        self.assertEqual(self.user.has_active_subscription, True)
        handler = GoogleNotificationHandler(google_message)
        handler.handle()
        subscription = UserSubscription.objects.get(id=subscription.id)
        user = User.objects.get(id=self.user.id)
        self.assertEqual(subscription.status, SubscriptionStatus.EXPIRED.value)
        self.assertEqual(user.has_active_subscription, False)


class AppleNotificationHandlerTestCase(CustomAPITestCase):
    def setUp(self):
        super().setUp()
        self.create_standard_users()
        self.product = baker.make(
            Buyable, name="product", title=baker.make("common.Translation")
        )
        self.purchase = baker.make(
            Purchase,
            user_id=self.user.id,
            stored_payment_method_id="stored_payment_method_id",
            vendor=PaymentVendor.APPLE.value,
            original_transaction_id="12345",
        )
        self.purchase.buyables.add(self.product)
        self.original_payment_transaction = apple_payment_transaction.make(
            purchase=self.purchase,
            transaction_id="123",
        )
        self.payment_transaction = apple_payment_transaction.make(
            purchase=self.purchase,
            transaction_id="1234",
        )

    def tearDown(self):
        super().tearDown()
        if hasattr(self, "verification_patcher"):
            self.verification_patcher.stop()

    def _set_verification_mock(self, verified_data):
        self.verification_patcher = patch.object(AppStoreNotificationVerifier, "parse")
        self.mock_verification = self.verification_patcher.start()
        self.mock_verification.return_value = verified_data

    def _create_verified_data(
        self,
        notification_type,
        notification_subtype,
        transaction_id,
        original_transaction_id,
        expiration_millis,
        product_name,
    ):
        apple_message = {
            "notification_type": notification_type,
            "subtype": notification_subtype,
            "notification_id": "558400a3-b0d4-4cfa-b31a-05c2857cc4f2",
            "data": {
                "appAppleId": 6450896373,
                "bundleId": "com.funly.mobil",
                "bundleVersion": "0",
                "environment": "Sandbox",
                "signedTransactionInfo": {
                    "transactionId": transaction_id,
                    "originalTransactionId": original_transaction_id,
                    "webOrderLineItemId": "2000000040182000",
                    "bundleId": "com.funly.mobil",
                    "productId": product_name,
                    "subscriptionGroupIdentifier": "21385037",
                    "purchaseDate": 1700339141000,
                    "originalPurchaseDate": 1696543674000,
                    "expiresDate": expiration_millis,
                    "quantity": 1,
                    "type": "Auto-Renewable Subscription",
                    "inAppOwnershipType": "PURCHASED",
                    "signedDate": 1700339174592,
                    "environment": "Sandbox",
                    "transactionReason": "PURCHASE",
                    "storefront": "TUR",
                    "storefrontId": "143480",
                    "price": 59990,
                    "currency": "TRY",
                },
                "signedRenewalInfo": {
                    "originalTransactionId": original_transaction_id,
                    "autoRenewProductId": product_name,
                    "productId": product_name,
                    "autoRenewStatus": 1,
                    "signedDate": 1700339174592,
                    "environment": "Sandbox",
                    "recentSubscriptionStartDate": 1700339141000,
                    "renewalDate": 1700339441000,
                },
                "status": 1,
            },
            "notification_publish_time": datetime.utcnow(),
        }
        return apple_message

    def test_consumption_request(self):
        verification_result_data = self._create_verified_data(
            notification_type=AppStoreNotificationType.CONSUMPTION_REQUEST,
            notification_subtype=AppStoreNotificationSubtype.NONE,
            transaction_id=self.payment_transaction.transaction_id,
            original_transaction_id=self.purchase.original_transaction_id,
            expiration_millis=time.time() * 1000 + 1000000000,
            product_name=self.product.name,
        )
        verification_result = (
            StoreNotificationVerificationResult.from_verification_result(
                **verification_result_data
            )
        )
        self._set_verification_mock(verification_result)
        apple_message = {}
        handler = AppleNotificationHandler(apple_message)
        handler.handle()

    def test_did_change_renewal_preference(self):
        subscription = baker.make(
            UserSubscription,
            user_id=self.user.id,
            buyable_id=self.product.id,
            purchase_id=self.purchase.id,
            expiration_date=datetime.utcnow() + relativedelta(days=15),
            start_date=datetime.utcnow() - relativedelta(days=15),
            status=SubscriptionStatus.ACTIVE.value,
            used_trial_days=7,
        )
        downgraded_product = baker.make(
            Buyable,
            name="downgraded_product",
            title=baker.make("common.Translation"),
        )
        baker.make(
            UserSubscription,
            user_id=self.user.id,
            buyable_id=downgraded_product.id,
            purchase_id=self.purchase.id,
            expiration_date=datetime.utcnow() + relativedelta(days=45),
            start_date=datetime.utcnow() + relativedelta(days=15),
            status=SubscriptionStatus.INITIAL.value,
            used_trial_days=7,
        )
        verification_result_data = self._create_verified_data(
            notification_type=AppStoreNotificationType.DID_CHANGE_RENEWAL_PREF,
            notification_subtype=AppStoreNotificationSubtype.NONE,
            transaction_id=self.payment_transaction.transaction_id,
            original_transaction_id=self.purchase.original_transaction_id,
            expiration_millis=time.time() * 1000 + 1000000000,
            product_name=downgraded_product.name,
        )
        verification_result = (
            StoreNotificationVerificationResult.from_verification_result(
                **verification_result_data
            )
        )
        self._set_verification_mock(verification_result)
        apple_message = {}
        self.assertEqual(self.user.subscriptions.count(), 2)
        handler = AppleNotificationHandler(apple_message)
        handler.handle()
        self.assertEqual(self.user.subscriptions.count(), 1)
        self.assertTrue(self.user.has_active_subscription)

    def test_downgrade(self):
        baker.make(
            UserSubscription,
            user_id=self.user.id,
            buyable_id=self.product.id,
            purchase_id=self.purchase.id,
            expiration_date=datetime.utcnow() + relativedelta(days=15),
            start_date=datetime.utcnow() - relativedelta(days=15),
            status=SubscriptionStatus.ACTIVE.value,
            used_trial_days=7,
        )
        downgraded_product = baker.make(
            Buyable,
            name="downgraded_product",
            title=baker.make("common.Translation"),
        )
        verification_result_data = self._create_verified_data(
            notification_type=AppStoreNotificationType.DID_CHANGE_RENEWAL_PREF,
            notification_subtype=AppStoreNotificationSubtype.DOWNGRADE,
            transaction_id=self.payment_transaction.transaction_id,
            original_transaction_id=self.purchase.original_transaction_id,
            expiration_millis=time.time() * 1000 + 1000000000,
            product_name=downgraded_product.name,
        )
        verification_result = (
            StoreNotificationVerificationResult.from_verification_result(
                **verification_result_data
            )
        )
        self._set_verification_mock(verification_result)
        apple_message = {}
        self.assertEqual(self.user.subscriptions.count(), 1)
        handler = AppleNotificationHandler(apple_message)
        handler.handle()
        self.assertEqual(self.user.subscriptions.count(), 2)
        self.assertTrue(self.user.has_active_subscription)
        self.assertEqual(
            self.user.subscriptions.order_by("-id").first().status,
            SubscriptionStatus.INITIAL,
        )

    def test_upgrade(self):
        baker.make(
            UserSubscription,
            user_id=self.user.id,
            buyable_id=self.product.id,
            purchase_id=self.purchase.id,
            expiration_date=datetime.utcnow() + relativedelta(days=15),
            start_date=datetime.utcnow() - relativedelta(days=15),
            status=SubscriptionStatus.ACTIVE.value,
            used_trial_days=7,
        )
        upgraded_product = baker.make(
            Buyable,
            name="upgraded_product",
            title=baker.make("common.Translation"),
            price=Decimal("100.0"),
            currency="USD",
        )
        verification_result_data = self._create_verified_data(
            notification_type=AppStoreNotificationType.DID_CHANGE_RENEWAL_PREF,
            notification_subtype=AppStoreNotificationSubtype.UPGRADE,
            transaction_id=self.payment_transaction.transaction_id,
            original_transaction_id=self.purchase.original_transaction_id,
            expiration_millis=time.time() * 1000 + 1000000000,
            product_name=upgraded_product.name,
        )
        verification_result = (
            StoreNotificationVerificationResult.from_verification_result(
                **verification_result_data
            )
        )
        self._set_verification_mock(verification_result)
        apple_message = {}
        self.assertEqual(self.user.subscriptions.count(), 1)
        handler = AppleNotificationHandler(apple_message)
        handler.handle()
        self.assertEqual(self.user.subscriptions.count(), 2)
        self.assertTrue(self.user.has_active_subscription)
        self.assertEqual(self.user.active_subscription.buyable, upgraded_product)

    def test_did_change_renewal_status(self):
        baker.make(
            UserSubscription,
            user_id=self.user.id,
            buyable_id=self.product.id,
            purchase_id=self.purchase.id,
            expiration_date=datetime.utcnow() + relativedelta(days=15),
            start_date=datetime.utcnow() - relativedelta(days=15),
            status=SubscriptionStatus.ACTIVE.value,
            used_trial_days=7,
        )
        verification_result_data = self._create_verified_data(
            notification_type=AppStoreNotificationType.DID_CHANGE_RENEWAL_STATUS,
            notification_subtype=AppStoreNotificationSubtype.NONE,
            transaction_id=self.payment_transaction.transaction_id,
            original_transaction_id=self.purchase.original_transaction_id,
            expiration_millis=time.time() * 1000 + 1000000000,
            product_name=self.product.name,
        )
        verification_result = (
            StoreNotificationVerificationResult.from_verification_result(
                **verification_result_data
            )
        )
        self._set_verification_mock(verification_result)
        apple_message = {}
        handler = AppleNotificationHandler(apple_message)
        handler.handle()

    def test_did_fail_to_renew(self):
        subscription = baker.make(
            UserSubscription,
            user_id=self.user.id,
            buyable_id=self.product.id,
            purchase_id=self.purchase.id,
            expiration_date=datetime.utcnow() + relativedelta(days=15),
            start_date=datetime.utcnow() - relativedelta(days=15),
            status=SubscriptionStatus.ACTIVE.value,
            used_trial_days=7,
        )
        verification_result_data = self._create_verified_data(
            notification_type=AppStoreNotificationType.DID_FAIL_TO_RENEW,
            notification_subtype=AppStoreNotificationSubtype.NONE,
            transaction_id=self.payment_transaction.transaction_id,
            original_transaction_id=self.purchase.original_transaction_id,
            expiration_millis=time.time() * 1000 + 1000000000,
            product_name=self.product.name,
        )
        verification_result = (
            StoreNotificationVerificationResult.from_verification_result(
                **verification_result_data
            )
        )
        self._set_verification_mock(verification_result)
        apple_message = {}
        handler = AppleNotificationHandler(apple_message)
        handler.handle()
        subscription = UserSubscription.objects.get(id=subscription.id)
        self.assertFalse(self.user.has_active_subscription)
        self.assertEqual(subscription.status, SubscriptionStatus.EXPIRED)

    def test_did_renew(self):
        subscription = baker.make(
            UserSubscription,
            user_id=self.user.id,
            buyable_id=self.product.id,
            purchase_id=self.purchase.id,
            expiration_date=datetime.utcnow() - relativedelta(days=1),
            start_date=datetime.utcnow() - relativedelta(days=31),
            status=SubscriptionStatus.EXPIRED.value,
            used_trial_days=7,
        )
        verification_result_data = self._create_verified_data(
            notification_type=AppStoreNotificationType.DID_RENEW,
            notification_subtype=AppStoreNotificationSubtype.NONE,
            transaction_id=self.payment_transaction.transaction_id,
            original_transaction_id=self.purchase.original_transaction_id,
            expiration_millis=time.time() * 1000 + 1000000000,
            product_name=self.product.name,
        )
        verification_result = (
            StoreNotificationVerificationResult.from_verification_result(
                **verification_result_data
            )
        )
        self._set_verification_mock(verification_result)
        apple_message = {}
        self.assertFalse(self.user.has_active_subscription)
        handler = AppleNotificationHandler(apple_message)
        handler.handle()
        subscription = UserSubscription.objects.get(id=subscription.id)
        user = User.objects.get(id=self.user.id)
        self.assertTrue(user.has_active_subscription)
        self.assertEqual(subscription.status, SubscriptionStatus.ACTIVE)

    def test_expired(self):
        subscription = baker.make(
            UserSubscription,
            user_id=self.user.id,
            buyable_id=self.product.id,
            purchase_id=self.purchase.id,
            expiration_date=datetime.utcnow() - relativedelta(minutes=30),
            start_date=datetime.utcnow() - relativedelta(days=30),
            status=SubscriptionStatus.ACTIVE.value,
            used_trial_days=7,
        )
        verification_result_data = self._create_verified_data(
            notification_type=AppStoreNotificationType.EXPIRED,
            notification_subtype=AppStoreNotificationSubtype.NONE,
            transaction_id=self.payment_transaction.transaction_id,
            original_transaction_id=self.purchase.original_transaction_id,
            expiration_millis=time.time() * 1000 + 1000000000,
            product_name=self.product.name,
        )
        verification_result = (
            StoreNotificationVerificationResult.from_verification_result(
                **verification_result_data
            )
        )
        self._set_verification_mock(verification_result)
        apple_message = {}
        self.assertTrue(self.user.has_active_subscription)
        handler = AppleNotificationHandler(apple_message)
        handler.handle()
        subscription = UserSubscription.objects.get(id=subscription.id)
        user = User.objects.get(id=self.user.id)
        self.assertFalse(user.has_active_subscription)
        self.assertEqual(subscription.status, SubscriptionStatus.EXPIRED)
        self.assertLess(subscription.expiration_date, datetime.utcnow())

    def test_grace_period_expired(self):
        subscription = baker.make(
            UserSubscription,
            user_id=self.user.id,
            buyable_id=self.product.id,
            purchase_id=self.purchase.id,
            expiration_date=datetime.utcnow() - relativedelta(minutes=30),
            start_date=datetime.utcnow() - relativedelta(days=30),
            status=SubscriptionStatus.ACTIVE.value,
            used_trial_days=7,
        )
        verification_result_data = self._create_verified_data(
            notification_type=AppStoreNotificationType.GRACE_PERIOD_EXPIRED,
            notification_subtype=AppStoreNotificationSubtype.NONE,
            transaction_id=self.payment_transaction.transaction_id,
            original_transaction_id=self.purchase.original_transaction_id,
            expiration_millis=time.time() * 1000 + 1000000000,
            product_name=self.product.name,
        )
        verification_result = (
            StoreNotificationVerificationResult.from_verification_result(
                **verification_result_data
            )
        )
        self._set_verification_mock(verification_result)
        apple_message = {}
        self.assertTrue(self.user.has_active_subscription)
        handler = AppleNotificationHandler(apple_message)
        handler.handle()
        subscription = UserSubscription.objects.get(id=subscription.id)
        user = User.objects.get(id=self.user.id)
        self.assertFalse(user.has_active_subscription)
        self.assertEqual(subscription.status, SubscriptionStatus.EXPIRED)
        self.assertLess(subscription.expiration_date, datetime.utcnow())

    def test_price_increase_pending(self):
        baker.make(
            UserSubscription,
            user_id=self.user.id,
            buyable_id=self.product.id,
            purchase_id=self.purchase.id,
            expiration_date=datetime.utcnow() - relativedelta(minutes=30),
            start_date=datetime.utcnow() - relativedelta(days=30),
            status=SubscriptionStatus.ACTIVE.value,
            used_trial_days=7,
        )
        verification_result_data = self._create_verified_data(
            notification_type=AppStoreNotificationType.PRICE_INCREASE,
            notification_subtype=AppStoreNotificationSubtype.PENDING,
            transaction_id=self.payment_transaction.transaction_id,
            original_transaction_id=self.purchase.original_transaction_id,
            expiration_millis=time.time() * 1000 + 1000000000,
            product_name=self.product.name,
        )
        verification_result = (
            StoreNotificationVerificationResult.from_verification_result(
                **verification_result_data
            )
        )
        self._set_verification_mock(verification_result)
        apple_message = {}
        handler = AppleNotificationHandler(apple_message)
        handler.handle()

    @patch("vendor.notification_handlers.subscription_notification_handlers.log")
    def test_price_increase_accepted(self, m_logger):
        baker.make(
            UserSubscription,
            user_id=self.user.id,
            buyable_id=self.product.id,
            purchase_id=self.purchase.id,
            expiration_date=datetime.utcnow() - relativedelta(minutes=30),
            start_date=datetime.utcnow() - relativedelta(days=30),
            status=SubscriptionStatus.ACTIVE.value,
            used_trial_days=7,
        )
        verification_result_data = self._create_verified_data(
            notification_type=AppStoreNotificationType.PRICE_INCREASE,
            notification_subtype=AppStoreNotificationSubtype.ACCEPTED,
            transaction_id=self.payment_transaction.transaction_id,
            original_transaction_id=self.purchase.original_transaction_id,
            expiration_millis=time.time() * 1000 + 1000000000,
            product_name=self.product.name,
        )
        verification_result = (
            StoreNotificationVerificationResult.from_verification_result(
                **verification_result_data
            )
        )
        self._set_verification_mock(verification_result)
        apple_message = {}
        handler = AppleNotificationHandler(apple_message)
        handler.handle()
        m_logger.info.assert_has_calls(
            [
                call(
                    "User accepted price increase",
                    vendor=PaymentVendor.APPLE.value,
                    payment_transaction_id=self.payment_transaction.id,
                    vendor_transaction_id=self.payment_transaction.transaction_id,
                    notification_type=verification_result.notification_type.value,
                    notification_subtype=verification_result.subtype.value,
                    notification_id=verification_result.notification_id,
                )
            ]
        )

    def test_refunded(self):
        subscription = baker.make(
            UserSubscription,
            user_id=self.user.id,
            buyable_id=self.product.id,
            purchase_id=self.purchase.id,
            expiration_date=datetime.utcnow() - relativedelta(minutes=30),
            start_date=datetime.utcnow() - relativedelta(days=30),
            status=SubscriptionStatus.ACTIVE.value,
            used_trial_days=7,
        )
        verification_result_data = self._create_verified_data(
            notification_type=AppStoreNotificationType.REFUND,
            notification_subtype=AppStoreNotificationSubtype.NONE,
            transaction_id=self.payment_transaction.transaction_id,
            original_transaction_id=self.purchase.original_transaction_id,
            expiration_millis=time.time() * 1000 + 1000000000,
            product_name=self.product.name,
        )
        verification_result = (
            StoreNotificationVerificationResult.from_verification_result(
                **verification_result_data
            )
        )
        self._set_verification_mock(verification_result)
        apple_message = {}
        self.assertTrue(self.user.has_active_subscription)
        handler = AppleNotificationHandler(apple_message)
        handler.handle()
        subscription = UserSubscription.objects.get(id=subscription.id)
        user = User.objects.get(id=self.user.id)
        self.assertFalse(user.has_active_subscription)
        self.assertEqual(subscription.status, SubscriptionStatus.EXPIRED)
        self.assertLess(subscription.expiration_date, datetime.utcnow())

    def test_refund_declined_for_subscription_in_period(self):
        subscription = baker.make(
            UserSubscription,
            user_id=self.user.id,
            buyable_id=self.product.id,
            purchase_id=self.purchase.id,
            expiration_date=datetime.utcnow() + relativedelta(minutes=30),
            start_date=datetime.utcnow() - relativedelta(days=30),
            status=SubscriptionStatus.EXPIRED.value,
            used_trial_days=7,
        )
        verification_result_data = self._create_verified_data(
            notification_type=AppStoreNotificationType.REFUND_DECLINED,
            notification_subtype=AppStoreNotificationSubtype.NONE,
            transaction_id=self.payment_transaction.transaction_id,
            original_transaction_id=self.purchase.original_transaction_id,
            expiration_millis=time.time() * 1000 + 1000000000,
            product_name=self.product.name,
        )
        verification_result = (
            StoreNotificationVerificationResult.from_verification_result(
                **verification_result_data
            )
        )
        self._set_verification_mock(verification_result)
        apple_message = {}
        handler = AppleNotificationHandler(apple_message)
        handler.handle()
        subscription = UserSubscription.objects.get(id=subscription.id)
        self.assertEqual(subscription.status, SubscriptionStatus.ACTIVE)
        self.assertTrue(self.user.has_active_subscription)

    def test_refund_declined_for_subscription_out_of_period(self):
        subscription = baker.make(
            UserSubscription,
            user_id=self.user.id,
            buyable_id=self.product.id,
            purchase_id=self.purchase.id,
            expiration_date=datetime.utcnow() - relativedelta(minutes=30),
            start_date=datetime.utcnow() - relativedelta(days=30),
            status=SubscriptionStatus.EXPIRED.value,
            used_trial_days=7,
        )
        verification_result_data = self._create_verified_data(
            notification_type=AppStoreNotificationType.REFUND_DECLINED,
            notification_subtype=AppStoreNotificationSubtype.NONE,
            transaction_id=self.payment_transaction.transaction_id,
            original_transaction_id=self.purchase.original_transaction_id,
            expiration_millis=time.time() * 1000 - 100000000,
            product_name=self.product.name,
        )
        verification_result = (
            StoreNotificationVerificationResult.from_verification_result(
                **verification_result_data
            )
        )
        self._set_verification_mock(verification_result)
        apple_message = {}
        handler = AppleNotificationHandler(apple_message)
        handler.handle()
        subscription = UserSubscription.objects.get(id=subscription.id)
        self.assertEqual(subscription.status, SubscriptionStatus.EXPIRED)
        self.assertFalse(self.user.has_active_subscription)

    def test_refund_reversed_in_period(self):
        subscription = baker.make(
            UserSubscription,
            user_id=self.user.id,
            buyable_id=self.product.id,
            purchase_id=self.purchase.id,
            expiration_date=datetime.utcnow() + relativedelta(minutes=30),
            start_date=datetime.utcnow() - relativedelta(days=30),
            status=SubscriptionStatus.EXPIRED.value,
            used_trial_days=7,
        )
        verification_result_data = self._create_verified_data(
            notification_type=AppStoreNotificationType.REFUND_REVERSED,
            notification_subtype=AppStoreNotificationSubtype.NONE,
            transaction_id=self.payment_transaction.transaction_id,
            original_transaction_id=self.purchase.original_transaction_id,
            expiration_millis=time.time() * 1000 + 1000000000,
            product_name=self.product.name,
        )
        verification_result = (
            StoreNotificationVerificationResult.from_verification_result(
                **verification_result_data
            )
        )
        self._set_verification_mock(verification_result)
        apple_message = {}
        handler = AppleNotificationHandler(apple_message)
        handler.handle()
        subscription = UserSubscription.objects.get(id=subscription.id)
        self.assertEqual(subscription.status, SubscriptionStatus.ACTIVE)
        self.assertTrue(self.user.has_active_subscription)

    def test_refund_reversed_out_period(self):
        subscription = baker.make(
            UserSubscription,
            user_id=self.user.id,
            buyable_id=self.product.id,
            purchase_id=self.purchase.id,
            expiration_date=datetime.utcnow() - relativedelta(minutes=30),
            start_date=datetime.utcnow() - relativedelta(days=30),
            status=SubscriptionStatus.EXPIRED.value,
            used_trial_days=7,
        )
        verification_result_data = self._create_verified_data(
            notification_type=AppStoreNotificationType.REFUND_REVERSED,
            notification_subtype=AppStoreNotificationSubtype.NONE,
            transaction_id=self.payment_transaction.transaction_id,
            original_transaction_id=self.purchase.original_transaction_id,
            expiration_millis=time.time() * 1000 - 1000000000,
            product_name=self.product.name,
        )
        verification_result = (
            StoreNotificationVerificationResult.from_verification_result(
                **verification_result_data
            )
        )
        self._set_verification_mock(verification_result)
        apple_message = {}
        handler = AppleNotificationHandler(apple_message)
        handler.handle()
        subscription = UserSubscription.objects.get(id=subscription.id)
        self.assertEqual(subscription.status, SubscriptionStatus.EXPIRED)
        self.assertFalse(self.user.has_active_subscription)

    def test_renewal_extended(self):
        subscription = baker.make(
            UserSubscription,
            user_id=self.user.id,
            buyable_id=self.product.id,
            purchase_id=self.purchase.id,
            expiration_date=datetime.utcnow() + relativedelta(days=1),
            start_date=datetime.utcnow() - relativedelta(days=30),
            status=SubscriptionStatus.EXPIRED.value,
            used_trial_days=7,
        )
        verification_result_data = self._create_verified_data(
            notification_type=AppStoreNotificationType.RENEWAL_EXTENDED,
            notification_subtype=AppStoreNotificationSubtype.NONE,
            transaction_id=self.payment_transaction.transaction_id,
            original_transaction_id=self.purchase.original_transaction_id,
            expiration_millis=time.time() * 1000 + 10000000000,
            product_name=self.product.name,
        )
        verification_result = (
            StoreNotificationVerificationResult.from_verification_result(
                **verification_result_data
            )
        )
        self._set_verification_mock(verification_result)
        apple_message = {}
        self.assertLess(
            subscription.expiration_date, datetime.utcnow() + relativedelta(days=2)
        )
        handler = AppleNotificationHandler(apple_message)
        handler.handle()
        subscription = UserSubscription.objects.get(id=subscription.id)
        self.assertEqual(subscription.status, SubscriptionStatus.ACTIVE)
        self.assertGreater(
            subscription.expiration_date, datetime.utcnow() + relativedelta(days=10)
        )
        self.assertTrue(self.user.has_active_subscription)

    def test_renewal_extension_summary(self):
        verification_result_data = self._create_verified_data(
            notification_type=AppStoreNotificationType.RENEWAL_EXTENSION,
            notification_subtype=AppStoreNotificationSubtype.SUMMARY,
            transaction_id=self.payment_transaction.transaction_id,
            original_transaction_id=self.purchase.original_transaction_id,
            expiration_millis=time.time() * 1000 + 10000000000,
            product_name=self.product.name,
        )
        verification_result = (
            StoreNotificationVerificationResult.from_verification_result(
                **verification_result_data
            )
        )
        self._set_verification_mock(verification_result)
        apple_message = {}
        handler = AppleNotificationHandler(apple_message)
        handler.handle()

    def test_renewal_extension_failure(self):
        verification_result_data = self._create_verified_data(
            notification_type=AppStoreNotificationType.RENEWAL_EXTENSION,
            notification_subtype=AppStoreNotificationSubtype.FAILURE,
            transaction_id=self.payment_transaction.transaction_id,
            original_transaction_id=self.purchase.original_transaction_id,
            expiration_millis=time.time() * 1000 + 10000000000,
            product_name=self.product.name,
        )
        verification_result = (
            StoreNotificationVerificationResult.from_verification_result(
                **verification_result_data
            )
        )
        self._set_verification_mock(verification_result)
        apple_message = {}
        handler = AppleNotificationHandler(apple_message)
        handler.handle()

    @patch("vendor.notification_handlers.subscription_notification_handlers.log")
    def test_revoke(self, m_logger):
        verification_result_data = self._create_verified_data(
            notification_type=AppStoreNotificationType.REVOKE,
            notification_subtype=AppStoreNotificationSubtype.NONE,
            transaction_id=self.payment_transaction.transaction_id,
            original_transaction_id=self.purchase.original_transaction_id,
            expiration_millis=time.time() * 1000 + 10000000000,
            product_name=self.product.name,
        )
        verification_result = (
            StoreNotificationVerificationResult.from_verification_result(
                **verification_result_data
            )
        )
        self._set_verification_mock(verification_result)
        apple_message = {}
        handler = AppleNotificationHandler(apple_message)
        handler.handle()
        m_logger.info.assert_has_calls(
            [
                call(
                    "Subscription revoked. This may indicate that the user closed the family share",
                    vendor=PaymentVendor.APPLE,
                    payment_transaction_id=self.payment_transaction.id,
                    vendor_transaction_id=self.payment_transaction.transaction_id,
                    notification_type=verification_result.notification_type.value,
                    notification_subtype=verification_result.subtype.value,
                    notification_id=verification_result.notification_id,
                )
            ]
        )

    @patch("vendor.notification_handlers.subscription_notification_handlers.log")
    def test_initial_subscription(self, m_logger):
        verification_result_data = self._create_verified_data(
            notification_type=AppStoreNotificationType.SUBSCRIBED,
            notification_subtype=AppStoreNotificationSubtype.INITIAL_BUY,
            transaction_id=None,
            original_transaction_id=self.purchase.original_transaction_id,
            expiration_millis=time.time() * 1000 + 10000000000,
            product_name=self.product.name,
        )
        verification_result = (
            StoreNotificationVerificationResult.from_verification_result(
                **verification_result_data
            )
        )
        self._set_verification_mock(verification_result)
        apple_message = {}
        handler = AppleNotificationHandler(apple_message)
        handler.handle()
        m_logger.error.assert_called_with(
            "Notified subscription purchase doesn't exist",
            vendor=PaymentVendor.APPLE,
            original_payment_transaction_id=self.payment_transaction.id,
            vendor_original_transaction_id=self.purchase.original_transaction_id,
            notification_type=AppStoreNotificationType.SUBSCRIBED.value,
            notification_subtype=AppStoreNotificationSubtype.INITIAL_BUY.value,
            notification_id=verification_result.notification_id,
        )

    @patch("vendor.notification_handlers.subscription_notification_handlers.log")
    def test_resubscribed_no_payment_transaction(self, m_logger):
        verification_result_data = self._create_verified_data(
            notification_type=AppStoreNotificationType.SUBSCRIBED,
            notification_subtype=AppStoreNotificationSubtype.RESUBSCRIBE,
            transaction_id=self.payment_transaction.transaction_id,
            original_transaction_id=self.purchase.original_transaction_id,
            expiration_millis=time.time() * 1000 + 10000000000,
            product_name=self.product.name,
        )
        verification_result = (
            StoreNotificationVerificationResult.from_verification_result(
                **verification_result_data
            )
        )
        self._set_verification_mock(verification_result)
        apple_message = {}
        handler = AppleNotificationHandler(apple_message)
        handler.handle()
        m_logger.error.assert_called_with(
            "Notified subscription purchase doesn't exist",
            vendor=PaymentVendor.APPLE.value,
            payment_transaction_id=self.payment_transaction.id,
            vendor_transaction_id=self.payment_transaction.transaction_id,
            notification_type=verification_result.notification_type.value,
            notification_subtype=verification_result.subtype.value,
            notification_id=verification_result.notification_id,
        )

    def test_notification_test(self):
        verification_result_data = self._create_verified_data(
            notification_type=AppStoreNotificationType.REVOKE,
            notification_subtype=AppStoreNotificationSubtype.NONE,
            transaction_id=self.payment_transaction.transaction_id,
            original_transaction_id=self.purchase.original_transaction_id,
            expiration_millis=time.time() * 1000 + 10000000000,
            product_name=self.product.name,
        )
        verification_result = (
            StoreNotificationVerificationResult.from_verification_result(
                **verification_result_data
            )
        )
        self._set_verification_mock(verification_result)
        apple_message = {}
        handler = AppleNotificationHandler(apple_message)
        handler.handle()
