from typing import List, TYPE_CHECKING

from django.core.validators import MinValueValidator
from django.db import models
from django.db.models import Q
from django.utils.functional import cached_property
from django.utils.translation import gettext_lazy as _
from django_softdelete.models import SoftDeleteManager, SoftDeleteModel
from moneyed import Money, list_all_currencies
from rest_framework import status

from common.custom_exceptions.custom_exception import CustomException
from common.response.response_information_codes.error_code import ErrorCode
from payment.types import PaymentStatus, SubscriptionPeriod, BuyableType
from user.models import User
from common.fields import DateTimeWithoutTZField

if TYPE_CHECKING:
    from user.models import User


# Create your models here.


class Buyable(SoftDeleteModel):
    name = models.CharField(max_length=64, blank=False, null=False)
    title = models.ForeignKey(
        "common.Translation",
        on_delete=models.CASCADE,
        related_name="titled_buyables",
        null=False,
    )
    description = models.ForeignKey(
        "common.Translation",
        on_delete=models.CASCADE,
        related_name="described_buyables",
        null=False,
    )
    price = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    currency = models.CharField(
        max_length=8,
        choices=[(value.code, value.code) for value in list_all_currencies()],
        null=False,
        blank=False,
        default="TRY",
    )
    period = models.CharField(
        max_length=64,
        choices=SubscriptionPeriod.choices,
        default=SubscriptionPeriod.MONTHLY,
    )
    type = models.CharField(
        max_length=64,
        choices=BuyableType.choices,
        default=BuyableType.PERSONAL_SUBSCRIPTION,
    )
    trial_days = models.IntegerField(validators=[MinValueValidator(0)], default=0)
    special_offer_root = models.ForeignKey(
        "payment.Buyable",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="special_offers",
        limit_choices_to={"special_offer_root__isnull": True},
    )
    is_active = models.BooleanField(null=False, blank=False, default=False)
    created = DateTimeWithoutTZField(auto_now_add=True, editable=False)
    updated = DateTimeWithoutTZField(auto_now=True, editable=False)
    deleted_at = DateTimeWithoutTZField(blank=True, null=True)

    class Meta:
        db_table = "buyable"
        constraints = [
            models.CheckConstraint(
                check=Q(type=BuyableType.ONE_TIME_PURCHASE)
                | (
                    ~Q(type=BuyableType.ONE_TIME_PURCHASE.value)
                    & Q(period__isnull=False)
                ),
                name="subscription_period_not_null_constraint",
            ),
            models.CheckConstraint(
                check=Q(type=BuyableType.ONE_TIME_PURCHASE)
                | (
                    ~Q(type=BuyableType.ONE_TIME_PURCHASE.value)
                    & Q(trial_days__isnull=False)
                ),
                name="subscription_trial_days_not_null_constraint",
            ),
            models.UniqueConstraint(
                fields=["name"],
                condition=Q(deleted_at__isnull=True),
                name="unique_buyable_name_key_if_not_deleted",
            ),
        ]

    def get_store_price(self, store: str, country_code: str) -> Money:
        return Money(self.price, currency=self.currency)


class PaymentTransaction(SoftDeleteModel):
    purchase = models.ForeignKey(
        "payment.Purchase",
        on_delete=models.DO_NOTHING,
        related_name="payment_transactions",
    )
    list_amount = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    charge_amount = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    credit_amount = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    payment_vendor = models.CharField(max_length=64)
    payment_method = models.CharField(max_length=64)
    currency = models.CharField(
        max_length=3,
        choices=[(value.code, value.code) for value in list_all_currencies()],
        blank=False,
        null=False,
    )
    tax_rate = models.DecimalField(max_digits=5, decimal_places=3, default=0)
    payer_id = models.CharField(max_length=255, blank=True, null=True)
    ip_address = models.CharField(max_length=64, blank=True)
    status = models.CharField(
        max_length=32,
        blank=False,
        null=False,
        choices=PaymentStatus.choices,
        default=PaymentStatus.INITIAL,
    )
    transaction_id = models.CharField(max_length=255, blank=True, null=True)
    receipt = models.JSONField(null=True, blank=True)
    raw_product_data = models.JSONField(null=False, blank=False)
    created = DateTimeWithoutTZField(auto_now_add=True, editable=False)
    updated = DateTimeWithoutTZField(auto_now=True, editable=False)
    deleted_at = DateTimeWithoutTZField(blank=True, null=True)

    class Meta:
        db_table = "payment_transaction"
        constraints = [
            models.UniqueConstraint(
                fields=["payment_vendor", "transaction_id"],
                condition=Q(deleted_at__isnull=True),
                name="unique_payment_transaction_payment_vendor_key_transaction_id_if_not_deleted",
            )
        ]

    @property
    def charge_amount_money(self):
        return Money(self.charge_amount, self.currency)

    @property
    def list_amount_money(self):
        return Money(self.list_amount, self.currency)


class PurchaseManager(SoftDeleteManager):
    def create(self, buyables: List[Buyable], **obj_data):
        # Check if subscription buyable is passed alone
        if (
            not buyables
            or (
                any(
                    map(
                        lambda p: p.type != BuyableType.ONE_TIME_PURCHASE.value,
                        buyables,
                    )
                )
                and len(buyables)
            )
            > 1
        ):
            raise CustomException.business_logic_error(
                title=_("Invalid Subscription Configuration"),
                detail=_("You cannot add additional buyables to subscriptions."),
                code=ErrorCode.AUTHENTICATION_FAILED,
                status_code=status.HTTP_400_BAD_REQUEST,
            )

        # Now call the super method which does the actual creation
        entity = super().create(**obj_data)
        entity.buyables.add(*buyables)
        return entity


class Purchase(SoftDeleteModel):
    user = models.ForeignKey(
        User, on_delete=models.DO_NOTHING, related_name="purchases"
    )
    buyables = models.ManyToManyField(
        Buyable, through="payment.PurchasedBuyable", related_name="purchases"
    )
    stored_payment_method_id = models.CharField(max_length=64, blank=True, null=True)
    vendor = models.CharField(max_length=64, null=True, blank=True)
    original_transaction_id = models.CharField(max_length=255, blank=True, null=True)
    created = DateTimeWithoutTZField(auto_now_add=True, editable=False)
    updated = DateTimeWithoutTZField(auto_now=True, editable=False)
    deleted_at = DateTimeWithoutTZField(blank=True, null=True)

    objects = PurchaseManager()

    class Meta:
        db_table = "purchase"

    @cached_property
    def original_payment_transaction(self) -> PaymentTransaction:
        return (
            self.payment_transactions.filter(status=PaymentStatus.SUCCEEDED)
            .order_by("-created")
            .first()
        )


class PurchasedBuyable(SoftDeleteModel):
    purchase = models.ForeignKey(
        Purchase, on_delete=models.CASCADE, related_name="purchase_buyables"
    )
    buyable = models.ForeignKey(
        Buyable, on_delete=models.CASCADE, related_name="purchase_buyables"
    )
    quantity = models.IntegerField(
        validators=[MinValueValidator(1)], null=False, blank=False, default=1
    )
    created = DateTimeWithoutTZField(auto_now_add=True, editable=False)
    updated = DateTimeWithoutTZField(auto_now=True, editable=False)
    deleted_at = DateTimeWithoutTZField(blank=True, null=True)

    class Meta:
        db_table = "purchase_buyable"
