from decimal import Decimal

from django.utils.translation import gettext_lazy as _
from rest_framework import status
from structlog import get_logger

from common.custom_exceptions.custom_exception import CustomException
from common.response.response_information_codes.error_code import ErrorCode
from payment.models import Buyable, Purchase, PaymentTransaction
from payment.subscription.strategies import MobilePurchaseStrategy
from payment.types import PaymentVendor, PaymentStatus
from user.models import User
from vendor.clients.qonversion import QonversionClient

log = get_logger(__name__)


class QonversionPurchaseStrategy(MobilePurchaseStrategy):
    def __init__(self, request, user: User, receipt: str = None):
        if not receipt:
            receipt = request.data.get("receipt", "{}")

        super().__init__(request, user, receipt)
        self._vendor = PaymentVendor.QONVERSION
        self._platform = None

    def verify(self):
        client = QonversionClient()
        entitlements_data = client.get_user_entitlements(str(self.user.id))

        data = entitlements_data.get("data", [])
        product_key = self.request.data.get("product_key")

        matching_entitlement = None
        for entitlement in data:
            if entitlement.get("product", {}).get("product_id") == product_key:
                matching_entitlement = entitlement
                break

        if not matching_entitlement:
            raise CustomException.business_logic_error(
                title=_("Product Not Found"),
                detail=_("Product not found in user's Qonversion entitlements."),
                code=ErrorCode.INTERNAL_SERVER_ERROR,
                status_code=status.HTTP_400_BAD_REQUEST,
            )

        is_active = matching_entitlement.get("active", False)

        self.verified_response = {
            "entitlement": matching_entitlement,
            "product_key": product_key,
        }
        self.receipt_verification_result = is_active
        return self.verified_response, is_active

    def prepare_transaction_creation_for_receipt(self):
        if self.verified_response is None:
            raise CustomException.business_logic_error(
                title=_("Verification Required"),
                detail=_("Called prepare transaction before verification"),
                code=ErrorCode.VERIFICATION_PREREQUISITE_NOT_SATISFIED,
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )

        request_data = self.request.data
        product_key = request_data.get("product_key")
        buyable = Buyable.objects.get(name=product_key)
        transaction_id = request_data.get("transaction_id")
        raw_product_data = request_data.get("raw_product_data")

        self._buyable = buyable
        if self.user_has_subscription:
            self._purchase = Purchase.objects.filter(
                user=self.user,
                buyables__in=[self.active_subscription_of_user.buyable],
                vendor=self.vendor,
            ).first()

        if self._purchase is None:
            self._purchase = Purchase(
                user=self.user,
                stored_payment_method_id=request_data.get(
                    "stored_payment_method", None
                ),
                vendor=self.vendor,
                original_transaction_id=transaction_id,
            )

        price = Decimal(str(buyable.price))
        currency = buyable.currency

        self._payment_transaction = PaymentTransaction(
            purchase=self._purchase,
            list_amount=price,
            charge_amount=price,
            credit_amount=0,
            payment_vendor=self.vendor,
            payment_method="qonversion",
            currency=currency,
            tax_rate=0,
            payer_id=None,
            ip_address="",
            status=(
                PaymentStatus.SUCCEEDED
                if self.receipt_verification_result
                else PaymentStatus.FAILED
            ),
            transaction_id=transaction_id,
            receipt=self.receipt,
            raw_product_data=raw_product_data,
        )

        self._prepared_for_transaction = True
