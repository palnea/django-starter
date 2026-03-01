from decimal import Decimal

from model_bakery.recipe import Recipe

from payment.models import PaymentTransaction, Buyable
from payment.types import PaymentStatus, PaymentVendor, SubscriptionPeriod, BuyableType

qonversion_payment_transaction = Recipe(
    PaymentTransaction,
    list_amount=Decimal("10.0"),
    charge_amount=Decimal("10.0"),
    credit_amount=Decimal("0.0"),
    payment_vendor=PaymentVendor.QONVERSION.value,
    payment_method="qonversion",
    currency="TRY",
    tax_rate=0,
    payer_id=None,
    ip_address="",
    status=PaymentStatus.SUCCEEDED,
    receipt=None,
    raw_product_data="raw_product_data",
)

google_payment_transaction = Recipe(
    PaymentTransaction,
    list_amount=Decimal("10.0"),
    charge_amount=Decimal("10.0"),
    credit_amount=Decimal("0.0"),
    payment_vendor=PaymentVendor.GOOGLE.value,
    payment_method="credit_card",
    currency="TRY",
    tax_rate=0,
    payer_id=None,
    ip_address="",
    status=PaymentStatus.SUCCEEDED,
    receipt=None,
    raw_product_data="raw_product_data",
)

apple_payment_transaction = Recipe(
    PaymentTransaction,
    list_amount=Decimal("10.0"),
    charge_amount=Decimal("10.0"),
    credit_amount=Decimal("0.0"),
    payment_vendor=PaymentVendor.APPLE.value,
    payment_method="credit_card",
    currency="TRY",
    tax_rate=0,
    payer_id=None,
    ip_address="",
    status=PaymentStatus.SUCCEEDED,
    receipt=None,
    raw_product_data="raw_product_data",
)

monthly_buyable = Recipe(
    Buyable,
    name="monthly",
    price=Decimal("110.0"),
    currency="TRY",
    period=SubscriptionPeriod.MONTHLY.value,
    type=BuyableType.PERSONAL_SUBSCRIPTION.value,
    trial_days=7,
    is_active=True,
)

annual_buyable = Recipe(
    Buyable,
    name="annual",
    price=Decimal("650.0"),
    currency="TRY",
    period=SubscriptionPeriod.ANNUAL.value,
    type=BuyableType.PERSONAL_SUBSCRIPTION.value,
    trial_days=30,
    is_active=True,
)
