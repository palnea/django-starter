import time
from datetime import datetime
from decimal import Decimal
from typing import Dict, Union

from django.db import transaction
from django.utils.functional import cached_property
from django.utils.translation import gettext_lazy as _
from rest_framework import status
from structlog import get_logger

from common.custom_exceptions.custom_exception import CustomException
from common.response.response_information_codes.error_code import ErrorCode
from payment.models import PaymentTransaction, Purchase, Buyable
from payment.signals import purchase_for_subscription_created
from payment.types import PaymentVendor, PaymentStatus
from subscription.models import UserSubscription
from subscription.types import SubscriptionStatus
from user.models import User
from vendor.clients.googleplay import GooglePlayClient
from vendor.types import (
    GooglePlayNotificationSubtype,
    AppStoreNotificationType,
    GooglePlayNotificationType,
    StoreNotificationVerificationResult,
    AppStoreNotificationSubtype,
)
from vendor.verifiers.app_store_notification_verifier import (
    AppStoreNotificationVerifier,
)
from vendor.verifiers.google_play_notification_verifier import (
    GooglePlayNotificationVerifier,
)

log = get_logger(__name__)


class VendorNotificationHandler:
    def __init__(self, request_body: Dict, **kwargs):
        self._request_body: Dict = request_body
        self._verified_data: Union[StoreNotificationVerificationResult, None] = None
        self._product_subscription: Union[UserSubscription, None] = None
        self._payment_transaction: Union[PaymentTransaction, None] = None
        self._vendor: Union[PaymentVendor, None] = None
        self.METHOD_MAPPER = {}

    def none(self):
        pass

    def handle(self):
        subtype_method_mapper = self.METHOD_MAPPER.get(
            self._verified_data.notification_type, {}
        )
        if callable(subtype_method_mapper):
            result = subtype_method_mapper()
        else:
            result = subtype_method_mapper.get(self._verified_data.subtype, self.none)()
        log.info(
            "Webhook is handled",
            vendor=self._vendor,
            verified_data=str(self._verified_data),
        )
        return result

    @property
    def product_subscription(self) -> UserSubscription:
        if self._product_subscription:
            return self._product_subscription
        if self.original_payment_transaction is None:
            raise CustomException(
                detail={"error": _("Payment transaction not created yet")},
                code=ErrorCode.INTERNAL_SERVER_ERROR,
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )
        if self._vendor is None:
            raise CustomException(
                detail={"error": _("Reached user subscription before setting vendor")},
                code=ErrorCode.INTERNAL_SERVER_ERROR,
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )
        self._product_subscription = (
            UserSubscription.objects.filter(
                purchase=self.original_payment_transaction.purchase,
                buyable=self.product,
            )
            .order_by("-id")
            .first()
        )
        return self._product_subscription

    @cached_property
    def user(self) -> User:
        user = self.payment_transaction.purchase.user
        return user

    @cached_property
    def product(self):
        if not self._verified_data:
            raise CustomException(
                detail={
                    "verified_data": _(
                        "Verification should be done before reaching product"
                    )
                },
                code=ErrorCode.VERIFICATION_PREREQUISITE_NOT_SATISFIED,
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )
        return self.get_product()

    def get_product(self):
        raise NotImplementedError()

    def get_payment_transaction(self) -> PaymentTransaction:
        raise NotImplementedError()

    def get_original_payment_transaction(self) -> PaymentTransaction:
        raise NotImplementedError()

    @property
    def payment_transaction(self) -> PaymentTransaction:
        if self._payment_transaction:
            return self._payment_transaction
        if self._vendor is None:
            raise CustomException(
                detail={
                    "error": _("Reached payment transaction before setting vendor")
                },
                code=ErrorCode.INTERNAL_SERVER_ERROR,
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )
        self._payment_transaction = self.get_payment_transaction()
        return self._payment_transaction

    @cached_property
    def original_payment_transaction(self) -> PaymentTransaction:
        if self._vendor is None:
            raise CustomException(
                detail={
                    "error": _("Reached payment transaction before setting vendor")
                },
                code=ErrorCode.INTERNAL_SERVER_ERROR,
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )
        return self.get_original_payment_transaction()

    def renew_subscription(self):
        self.product_subscription.renew()

    def renew_subscription_from_now(self):
        self.product_subscription.renew(from_now=True)

    def update_expiration_time(self, date: datetime):
        subscription = self.product_subscription
        subscription.expiration_date = date
        if (
            subscription.current_status == SubscriptionStatus.EXPIRED
            and date > datetime.utcnow()
        ):
            subscription.status = SubscriptionStatus.ACTIVE
        subscription.save()

    def ensure_expiration(self):
        subscription = self.product_subscription
        if subscription.current_status != SubscriptionStatus.EXPIRED:
            subscription.expiration_date = datetime.utcnow()
            subscription.status = SubscriptionStatus.EXPIRED
            subscription.save()

    def ensure_active(self):
        subscription = self.product_subscription
        if subscription.current_status != SubscriptionStatus.ACTIVE:
            subscription.status = SubscriptionStatus.ACTIVE
            subscription.save()

    def ensure_active_if_not_expired(self):
        if self.product_subscription.expiration_date > datetime.utcnow():
            self.ensure_active()


class GoogleNotificationHandler(VendorNotificationHandler):
    def __init__(self, request_body: Dict):
        super().__init__(request_body=request_body)
        self._verified_data = GooglePlayNotificationVerifier.parse(request_body)
        self._vendor = PaymentVendor.GOOGLE
        self.METHOD_MAPPER = {
            GooglePlayNotificationType.SUBSCRIPTION_NOTIFICATION: {
                GooglePlayNotificationSubtype.NONE: self.none,
                GooglePlayNotificationSubtype.SUBSCRIPTION_RECOVERED: self.create_transaction_and_extend_subscription_from_now,
                GooglePlayNotificationSubtype.SUBSCRIPTION_RENEWED: self.create_transaction_and_extend_subscription,
                GooglePlayNotificationSubtype.SUBSCRIPTION_CANCELED: self.cancel_subscription,
                GooglePlayNotificationSubtype.SUBSCRIPTION_PURCHASED: self.ensure_subscription,
                GooglePlayNotificationSubtype.SUBSCRIPTION_ON_HOLD: self.suspend_subscription,
                GooglePlayNotificationSubtype.SUBSCRIPTION_IN_GRACE_PERIOD: self.ensure_active,
                GooglePlayNotificationSubtype.SUBSCRIPTION_RESTARTED: self.renew_subscription,
                GooglePlayNotificationSubtype.SUBSCRIPTION_PRICE_CHANGE_CONFIRMED: self.change_purchase_amount,
                GooglePlayNotificationSubtype.SUBSCRIPTION_DEFERRED: self.extend_expiration,
                GooglePlayNotificationSubtype.SUBSCRIPTION_PAUSED: self.suspend_subscription,
                GooglePlayNotificationSubtype.SUBSCRIPTION_PAUSE_SCHEDULE_CHANGED: self.renew_subscription,
                GooglePlayNotificationSubtype.SUBSCRIPTION_REVOKED: self.ensure_expiration,
                GooglePlayNotificationSubtype.SUBSCRIPTION_EXPIRED: self.ensure_expiration,
            }
        }

    def get_payment_transaction(self) -> [None, PaymentTransaction]:
        """
        This is not applicable for Google Play since it sends the original purchase token
        Google sends a new payment transaction only when a new subscription is done
        """
        return None

    def get_original_payment_transaction(self) -> PaymentTransaction:
        return (
            PaymentTransaction.objects.filter(
                payment_vendor=self._vendor,
                transaction_id=self.purchase_token,
            )
            .select_related("purchase")
            .first()
        )

    def get_product(self):
        product_name = self._verified_data.data.get("subscriptionNotification", {}).get(
            "subscriptionId"
        )
        return Buyable.objects.filter(name=product_name).first()

    @property
    def purchase_token(self) -> str:
        return self._verified_data.data.get("subscriptionNotification", {}).get(
            "purchaseToken"
        )

    def create_new_payment_transaction(
        self, transaction_id: str, purchase: Purchase, from_original: bool = False
    ):
        """
        Create a new payment transaction by concatenating current time with
        original purchaseToken if original is True
        """
        # Get attached subscription -> this also can lead to have a different kid of table configuration of user_subscription
        # instead of having user and product fields maybe we can have purchase field**
        payment_transaction = PaymentTransaction.objects.create(
            purchase=purchase,
            list_amount=self.original_payment_transaction.list_amount,
            charge_amount=self.original_payment_transaction.charge_amount,
            credit_amount=self.original_payment_transaction.credit_amount,
            payment_vendor=self.original_payment_transaction.payment_vendor,
            payment_method=self.original_payment_transaction.payment_method,
            currency=self.original_payment_transaction.currency,
            tax_rate=self.original_payment_transaction.tax_rate,
            payer_id=self.original_payment_transaction.payer_id,
            ip_address=self.original_payment_transaction.ip_address,
            status=PaymentStatus.SUCCEEDED,
            transaction_id=(
                f"{int(time.time())}-" + transaction_id
                if from_original
                else transaction_id
            ),
            receipt=None,
            raw_product_data=self._request_body,
        )
        return payment_transaction

    def create_transaction_and_extend_subscription_from_now(self):
        """
        A subscription is suspended due to payment failure
        This method recovers it and extends the subscription expiration
        one full period later than today
        """
        transaction_id = self.purchase_token
        self.create_new_payment_transaction(
            transaction_id, self.original_payment_transaction.purchase, True
        )
        self.product_subscription.renew(from_now=True)

    def create_transaction_and_extend_subscription(self):
        transaction_id = self.purchase_token
        self.create_new_payment_transaction(
            transaction_id, self.original_payment_transaction.purchase, True
        )
        self.product_subscription.renew()

    def cancel_subscription(self):
        self.product_subscription.status = SubscriptionStatus.CANCELED
        self.product_subscription.save()

    def ensure_subscription(self):
        if self.product_subscription is None:
            log.error(
                "Notified subscription purchase doesn't exist",
                vendor=self._vendor.value,
                payment_transaction_id=self.original_payment_transaction.id,
                vendor_transaction_id=self.purchase_token,
                notification_type=self._verified_data.notification_type.value,
                notification_subtype=self._verified_data.subtype.value,
                notification_id=self._verified_data.notification_id,
            )

    def suspend_subscription(self):
        product_subscription = self.product_subscription
        product_subscription.status = SubscriptionStatus.SUSPENDED
        product_subscription.save()

    def change_purchase_amount(self):
        google_subscription = GooglePlayClient().get_subscription_info(
            self.original_payment_transaction.purchase.buyables.first(),
            self._verified_data.data.get("subscriptionNotification", {}).get(
                "purchaseToken"
            ),
        )
        new_purchase_price = google_subscription.get("priceChange", {}).get("newPrice")
        price_micros: str = new_purchase_price.get("priceMicros")
        price_currency: str = new_purchase_price.get("currency")
        price_in_decimal: Decimal = Decimal(int(price_micros) / 1000000.0)
        log.info(
            "User accepted price change",
            price=price_in_decimal,
            currency=price_currency,
            vendor=self._vendor.value,
            payment_transaction_id=self.original_payment_transaction.id,
            vendor_transaction_id=self.purchase_token,
            notification_type=self._verified_data.notification_type.value,
            notification_subtype=self._verified_data.subtype.value,
            notification_id=self._verified_data.notification_id,
        )

    def extend_expiration(self):  # must get expiration time from store
        google_subscription = GooglePlayClient().get_subscription_info(
            self.original_payment_transaction.purchase.buyables.first(),
            self._verified_data.data.get("subscriptionNotification", {}).get(
                "purchaseToken"
            ),
        )
        new_expiration_time_millis = int(google_subscription.get("expiryTimeMillis"))
        expiration_time = datetime.fromtimestamp(new_expiration_time_millis / 1000.0)
        self.update_expiration_time(expiration_time)


class AppleNotificationHandler(VendorNotificationHandler):
    def __init__(self, request_body: Dict):
        super().__init__(request_body=request_body)
        self._verified_data = AppStoreNotificationVerifier.parse(request_body)
        self._vendor = PaymentVendor.APPLE
        self.METHOD_MAPPER = {
            AppStoreNotificationType.NONE: self.none,
            AppStoreNotificationType.CONSUMPTION_REQUEST: self.none,
            AppStoreNotificationType.DID_CHANGE_RENEWAL_PREF: {
                AppStoreNotificationSubtype.NONE: self.cancel_downgrade,
                AppStoreNotificationSubtype.UPGRADE: self.upgrade,
                AppStoreNotificationSubtype.DOWNGRADE: self.downgrade,
            },
            AppStoreNotificationType.DID_CHANGE_RENEWAL_STATUS: self.none,
            AppStoreNotificationType.DID_FAIL_TO_RENEW: self.did_fail_to_renew,
            AppStoreNotificationType.DID_RENEW: self.did_renew,
            AppStoreNotificationType.EXPIRED: self.expired,
            AppStoreNotificationType.GRACE_PERIOD_EXPIRED: self.grace_period_expired,
            AppStoreNotificationType.OFFER_REDEEMED: {
                AppStoreNotificationSubtype.INITIAL_BUY: self.offer_initial_buy,
                AppStoreNotificationSubtype.RESUBSCRIBE: self.offer_resubscribe,
                AppStoreNotificationSubtype.UPGRADE: self.offer_upgrade,
                AppStoreNotificationSubtype.DOWNGRADE: self.offer_downgrade,
                AppStoreNotificationSubtype.NONE: self.offer_redeemed,
            },
            AppStoreNotificationType.PRICE_INCREASE: {
                AppStoreNotificationSubtype.PENDING: self.none,
                AppStoreNotificationSubtype.ACCEPTED: self.price_increase_accepted,
            },
            AppStoreNotificationType.REFUND: self.refund,
            AppStoreNotificationType.REFUND_DECLINED: self.refund_declined,
            AppStoreNotificationType.REFUND_REVERSED: self.reversed,
            AppStoreNotificationType.RENEWAL_EXTENDED: self.renewal_extended,
            AppStoreNotificationType.RENEWAL_EXTENSION: {
                AppStoreNotificationSubtype.SUMMARY: self.renewal_summary,
                AppStoreNotificationSubtype.FAILURE: self.renewal_failure,
            },
            AppStoreNotificationType.REVOKE: self.revoke,
            AppStoreNotificationType.SUBSCRIBED: {
                AppStoreNotificationSubtype.INITIAL_BUY: self.just_subscribed,
                AppStoreNotificationSubtype.RESUBSCRIBE: self.resubscribe,
            },
            AppStoreNotificationType.TEST: self.test,
        }

    def get_payment_transaction(self) -> Union[PaymentTransaction, None]:
        return (
            PaymentTransaction.objects.filter(
                payment_vendor=self._vendor,
                transaction_id=self.transaction_id,
            )
            .select_related("purchase")
            .first()
        )

    def get_original_payment_transaction(self) -> Union[PaymentTransaction, None]:
        purchase = Purchase.objects.filter(
            vendor=self._vendor,
            original_transaction_id=self.original_transaction_id,
        ).first()
        return (
            purchase.payment_transactions.order_by("-id").first() if purchase else None
        )

    def get_product(self):
        product_name = self._verified_data.data.get("signedTransactionInfo", {}).get(
            "productId"
        )
        return Buyable.objects.filter(name=product_name).first()

    def ensure_active_if_not_expired(self):
        if self.expiration_datetime > datetime.utcnow():
            subscription = self.product_subscription
            subscription.expiration_date = self.expiration_datetime
            subscription.status = SubscriptionStatus.ACTIVE
            subscription.save()

    @property
    def transaction_id(self) -> str:
        return self._verified_data.data.get("signedTransactionInfo", {}).get(
            "transactionId"
        )

    @property
    def original_transaction_id(self) -> [str, None]:
        return self._verified_data.data.get("signedTransactionInfo", {}).get(
            "originalTransactionId", None
        )

    @property
    def expiration_datetime(self):
        expiration_time_in_millis = self._verified_data.data.get(
            "signedTransactionInfo", {}
        ).get("expiresDate")
        expiration_datetime = datetime.fromtimestamp(expiration_time_in_millis / 1000.0)
        return expiration_datetime

    @transaction.atomic
    def upgrade(self):
        # check if active subscription for product

        if (
            self.product_subscription
            and self.product_subscription.status != SubscriptionStatus.EXPIRED
        ):
            product_subscription = self.product_subscription

            product_subscription.expiration_date = self.expiration_datetime
            product_subscription.save()

        # get active subscription of user
        if self.user.active_subscription:
            subscription = self.user.active_subscription
            subscription.status = SubscriptionStatus.EXPIRED
            subscription.save()

        payment_transaction = PaymentTransaction.objects.get(
            payment_vendor=self._vendor,
            transaction_id=self.transaction_id,
        )
        if payment_transaction:
            purchase_for_subscription_created.send_robust(
                instance=payment_transaction, product=self.product, sender=None
            )
        else:
            purchase = self.original_payment_transaction.purchase
            current_time = datetime.utcnow()
            UserSubscription.objects.create(
                user=self.user,
                buyable=self.product,
                purchase=purchase,
                expiration_date=self.expiration_datetime,
                start_date=current_time,
                status=SubscriptionStatus.ACTIVE,
                used_trial_days=0,
            )

    def downgrade(self):
        product_subscription = self.product_subscription
        if product_subscription:
            status = product_subscription.status
            product_subscription.expiration_date = self.expiration_datetime
            current_status = (
                product_subscription.current_status
            )  # will update status automatically
            if status == current_status:
                product_subscription.save()
            return

        purchase = self.original_payment_transaction.purchase
        UserSubscription.objects.create(
            user=self.user,
            buyable=self.product,
            purchase=purchase,
            expiration_date=self.expiration_datetime,
            start_date=self.user.active_subscription.expiration_date,
            status=SubscriptionStatus.INITIAL,
            used_trial_days=0,
        )

    def cancel_downgrade(self):
        product_subscription = self.product_subscription
        UserSubscription.objects.filter(id=product_subscription.id).delete()

    def offer_initial_buy(self):
        pass

    def offer_resubscribe(self):
        pass

    def offer_upgrade(self):
        pass

    def offer_downgrade(self):
        pass

    def offer_redeemed(self):
        pass

    def did_fail_to_renew(self):
        self.ensure_expiration()

    def did_renew(self):
        payment_transaction = self.payment_transaction
        if not payment_transaction:
            PaymentTransaction.objects.create(
                purchase=self.original_payment_transaction.purchase,
                list_amount=self.original_payment_transaction.list_amount,
                charge_amount=self.original_payment_transaction.charge_amount,
                credit_amount=0,
                payment_vendor=self.original_payment_transaction.payment_vendor,
                payment_method=self.original_payment_transaction.payment_method,
                currency=self.original_payment_transaction.currency,
                tax_rate=self.original_payment_transaction.tax_rate,
                payer_id=self.original_payment_transaction.payer_id,
                ip_address=self.original_payment_transaction.ip_address,
                status=PaymentStatus.SUCCEEDED,
                transaction_id=self.transaction_id,
                receipt=None,
                raw_product_data=self._request_body,
            )
        self.update_expiration_time(self.expiration_datetime)

    def expired(self):
        self.ensure_expiration()

    def grace_period_expired(self):
        self.ensure_expiration()

    def price_increase_accepted(self):
        log.info(
            "User accepted price increase",
            vendor=self._vendor.value,
            payment_transaction_id=self.payment_transaction.id,
            vendor_transaction_id=self.transaction_id,
            notification_type=self._verified_data.notification_type.value,
            notification_subtype=self._verified_data.subtype.value,
            notification_id=self._verified_data.notification_id,
        )

    def refund(self):
        log.info(
            "User refunded purchase",
            vendor=self._vendor.value,
            payment_transaction_id=self.payment_transaction.id,
            vendor_original_transaction_id=self.original_payment_transaction.purchase.original_transaction_id,
            notification_type=self._verified_data.notification_type.value,
            notification_subtype=self._verified_data.subtype.value,
            notification_id=self._verified_data.notification_id,
            notification_data=str(self._verified_data.data),
        )
        self.ensure_expiration()

    def refund_declined(self):
        self.ensure_active_if_not_expired()
        log.info(
            "User refund declined",
            vendor=self._vendor.value,
            payment_transaction_id=self.payment_transaction.id,
            vendor_original_transaction_id=self.original_payment_transaction.purchase.original_transaction_id,
            notification_type=self._verified_data.notification_type.value,
            notification_subtype=self._verified_data.subtype.value,
            notification_id=self._verified_data.notification_id,
            notification_data=str(self._verified_data.data),
        )

    def reversed(self):
        self.ensure_active_if_not_expired()
        log.info(
            "User refund reversed",
            vendor=self._vendor.value,
            payment_transaction_id=self.payment_transaction.id,
            vendor_original_transaction_id=self.original_payment_transaction.purchase.original_transaction_id,
            notification_type=self._verified_data.notification_type.value,
            notification_subtype=self._verified_data.subtype.value,
            notification_id=self._verified_data.notification_id,
            notification_data=str(self._verified_data.data),
        )

    def renewal_extended(self):
        self.update_expiration_time(self.expiration_datetime)

    def renewal_summary(self):
        pass

    def renewal_failure(self):
        pass

    def just_subscribed(self):
        # Ensure subscription
        if self.product_subscription is None:
            log.error(
                "Notified subscription purchase doesn't exist",
                vendor=self._vendor.value,
                original_payment_transaction_id=self.original_payment_transaction.id,
                vendor_original_transaction_id=self.original_payment_transaction.purchase.original_transaction_id,
                notification_type=self._verified_data.notification_type.value,
                notification_subtype=self._verified_data.subtype.value,
                notification_id=self._verified_data.notification_id,
            )

    def resubscribe(self):
        if self.product_subscription is None:
            log.error(
                "Notified subscription purchase doesn't exist",
                vendor=self._vendor.value,
                payment_transaction_id=self.payment_transaction.id,
                vendor_transaction_id=self.transaction_id,
                notification_type=self._verified_data.notification_type.value,
                notification_subtype=self._verified_data.subtype.value,
                notification_id=self._verified_data.notification_id,
            )

    def revoke(self):
        log.info(
            "Subscription revoked. This may indicate that the user closed the family share",
            vendor=self._vendor.value,
            payment_transaction_id=self.payment_transaction.id,
            vendor_transaction_id=self.transaction_id,
            notification_type=self._verified_data.notification_type.value,
            notification_subtype=self._verified_data.subtype.value,
            notification_id=self._verified_data.notification_id,
        )

    def test(self):
        pass
