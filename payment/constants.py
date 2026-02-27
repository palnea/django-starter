from payment.subscription.qonversion_strategy import QonversionPurchaseStrategy
from payment.subscription.strategies import (
    GooglePurchaseStrategy,
    ApplePurchaseStrategy,
)
from payment.types import PaymentVendor

SUBSCRIPTION_STRATEGY_MAPPER = {
    PaymentVendor.FREE: None,
    PaymentVendor.GOOGLE: GooglePurchaseStrategy,
    PaymentVendor.APPLE: ApplePurchaseStrategy,
    PaymentVendor.QONVERSION: QonversionPurchaseStrategy,
}
