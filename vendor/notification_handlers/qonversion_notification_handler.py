from datetime import datetime
from typing import Dict, Union

from django.utils.functional import cached_property
from structlog import get_logger

from payment.models import PaymentTransaction, Purchase, Buyable
from payment.signals import purchase_for_subscription_created
from payment.types import PaymentVendor, PaymentStatus
from subscription.types import SubscriptionStatus
from user.models import User
from vendor.notification_handlers.subscription_notification_handlers import (
    VendorNotificationHandler,
)
from vendor.types import QonversionNotificationType
from vendor.verifiers.qonversion_notification_verifier import (
    QonversionNotificationVerifier,
)

log = get_logger(__name__)


class QonversionNotificationHandler(VendorNotificationHandler):
    def __init__(self, request_body: Dict):
        super().__init__(request_body=request_body)
        self._verified_data = QonversionNotificationVerifier.parse(request_body)
        self._vendor = PaymentVendor.QONVERSION
        self.METHOD_MAPPER = {
            QonversionNotificationType.SUBSCRIPTION_STARTED: self.initial_purchase,
            QonversionNotificationType.SUBSCRIPTION_RENEWED: self.renewal,
            QonversionNotificationType.SUBSCRIPTION_CANCELED: self.cancel_subscription,
            QonversionNotificationType.SUBSCRIPTION_EXPIRED: self.ensure_expiration,
            QonversionNotificationType.SUBSCRIPTION_BILLING_RETRY: self.billing_issue,
            QonversionNotificationType.SUBSCRIPTION_UPGRADED: self.product_change,
            QonversionNotificationType.SUBSCRIPTION_DOWNGRADED: self.product_change,
            QonversionNotificationType.SUBSCRIPTION_PRODUCT_CHANGED: self.product_change,
            QonversionNotificationType.SUBSCRIPTION_REFUNDED: self.refund,
            QonversionNotificationType.TRIAL_CONVERTED: self.trial_converted,
            QonversionNotificationType.TRIAL_CANCELED: self.cancel_subscription,
            QonversionNotificationType.TRIAL_EXPIRED: self.ensure_expiration,
            QonversionNotificationType.TRIAL_STILL_ACTIVE: self.none,
            QonversionNotificationType.TRIAL_BILLING_RETRY: self.billing_issue,
            QonversionNotificationType.IN_APP_PURCHASE: self.in_app_purchase,
            QonversionNotificationType.IN_APP_REFUNDED: self.refund,
            QonversionNotificationType.REFUND_DECLINED: self.ensure_active_if_not_expired,
            QonversionNotificationType.NONE: self.none,
            QonversionNotificationType.UNKNOWN: self.none,
        }

    # -- Data access properties --

    @property
    def app_user_id(self) -> str:
        data = self._verified_data.data
        return data.get("custom_user_id") or data.get("user_id", "")

    @property
    def transaction_id(self) -> str:
        transaction = self._verified_data.data.get("transaction", {})
        return transaction.get("id", "")

    @property
    def original_transaction_id(self) -> str:
        transaction = self._verified_data.data.get("transaction", {})
        return transaction.get("original_id", "")

    @property
    def product_id(self) -> str:
        return self._verified_data.data.get("product_id", "")

    @property
    def expiration_datetime(self) -> Union[datetime, None]:
        transaction = self._verified_data.data.get("transaction", {})
        expires_at = transaction.get("expires_at")
        if expires_at:
            return datetime.utcfromtimestamp(expires_at)
        return None

    @property
    def price(self):
        return self._verified_data.data.get("price")

    @property
    def currency(self) -> str:
        return self._verified_data.data.get("currency", "")

    # -- Lookups --

    def resolve_user(self) -> User:
        custom_user_id = self._verified_data.data.get("custom_user_id", "")
        if custom_user_id:
            try:
                return User.objects.get(id=custom_user_id)
            except User.DoesNotExist:
                pass

        user_id = self._verified_data.data.get("user_id", "")
        if user_id:
            try:
                return User.objects.get(id=user_id)
            except User.DoesNotExist:
                pass

        log.error(
            "Cannot resolve user from Qonversion webhook",
            custom_user_id=custom_user_id,
            user_id=user_id,
        )
        raise User.DoesNotExist(
            f"Cannot resolve user: custom_user_id={custom_user_id}, user_id={user_id}"
        )

    def get_product(self) -> Buyable:
        return Buyable.objects.filter(name=self.product_id).first()

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

    # -- Event handlers --

    def initial_purchase(self):
        if self.product_subscription is None:
            log.error(
                "Notified subscription purchase doesn't exist",
                vendor=self._vendor.value,
                app_user_id=self.app_user_id,
                product_id=self.product_id,
                notification_type=self._verified_data.notification_type.value,
                notification_id=self._verified_data.notification_id,
            )

    def renewal(self):
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
        if self.expiration_datetime:
            self.update_expiration_time(self.expiration_datetime)
        else:
            self.product_subscription.renew()

    def cancel_subscription(self):
        self.product_subscription.status = SubscriptionStatus.CANCELED
        self.product_subscription.save()

    def billing_issue(self):
        product_subscription = self.product_subscription
        product_subscription.status = SubscriptionStatus.SUSPENDED
        product_subscription.save()

    def product_change(self):
        self.ensure_expiration()
        new_product_id = self._verified_data.data.get("new_product_id")
        if not new_product_id:
            new_product_id = self.product_id
        if new_product_id:
            new_product = Buyable.objects.filter(name=new_product_id).first()
            if new_product and self.original_payment_transaction:
                purchase_for_subscription_created.send_robust(
                    instance=self.original_payment_transaction,
                    product=new_product,
                    sender=None,
                )

    def refund(self):
        log.info(
            "Qonversion refund event received",
            vendor=self._vendor.value,
            app_user_id=self.app_user_id,
            product_id=self.product_id,
            notification_type=self._verified_data.notification_type.value,
            notification_id=self._verified_data.notification_id,
        )
        self.ensure_expiration()

    def trial_converted(self):
        log.info(
            "Qonversion trial converted event received",
            vendor=self._vendor.value,
            app_user_id=self.app_user_id,
            product_id=self.product_id,
            notification_type=self._verified_data.notification_type.value,
            notification_id=self._verified_data.notification_id,
        )

    def in_app_purchase(self):
        log.info(
            "Qonversion in-app purchase event received",
            vendor=self._vendor.value,
            app_user_id=self.app_user_id,
            product_id=self.product_id,
            notification_type=self._verified_data.notification_type.value,
            notification_id=self._verified_data.notification_id,
        )
