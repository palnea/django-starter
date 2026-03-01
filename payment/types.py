from typing import Union

from django.db import models


class PaymentStatus(models.TextChoices):
    INITIAL = "initial"
    PENDING = "pending"
    STALE = "stale"
    CANCELED = "canceled"
    REVERTED = "reverted"
    FAILED = "failed"
    SUCCEEDED = "succeeded"


class SubscriptionPeriod(models.TextChoices):
    MONTHLY = "monthly"
    SEMI_ANNUAL = "semi_annual"
    ANNUAL = "annual"

    @property
    def primacy(self):
        return {
            SubscriptionPeriod.MONTHLY.value: 1,
            SubscriptionPeriod.SEMI_ANNUAL.value: 2,
            SubscriptionPeriod.ANNUAL.value: 3,
        }.get(self.value, 0)

    def __lt__(self, other):
        self_level = self.primacy
        other_level = other.primacy
        return self_level < other_level

    def __gt__(self, other):
        self_level = self.primacy
        other_level = other.primacy
        return self_level > other_level

    def __le__(self, other):
        self_level = self.primacy
        other_level = other.primacy
        return self_level <= other_level

    def __ge__(self, other):
        self_level = self.primacy
        other_level = other.primacy
        return self_level >= other_level

    # def __eq__(self, other):
    #     self_level = self.primacy
    #     other_level = other.primacy
    #     return self_level == other_level

    def __ne__(self, other):
        self_level = self.primacy
        other_level = other.primacy
        return self_level != other_level


class BuyableType(models.TextChoices):
    CORPORATE_SUBSCRIPTION = "corporate_subscription"
    PERSONAL_SUBSCRIPTION = "personal_subscription"
    ONE_TIME_PURCHASE = "one_time_purchase"


class PaymentVendor(models.TextChoices):
    FREE = "Free"
    APPLE = "AppleAppStore"
    GOOGLE = "GooglePlay"
    QONVERSION = "Qonversion"

    def __eq__(self, other: Union[str, "PaymentVendor"]):
        if isinstance(other, str):
            return self.value == other
        elif isinstance(other, PaymentVendor):
            return self.value == other.value

    def __hash__(self):
        return hash(self.value)


class PlatformType(models.TextChoices):
    GOOGLE_FAMILY = "Google"
    IOS_COMPANY = "Apple"
    IOS_FAMILY = "ios"
    IOS_PHONE = "iphone"
    IOS_TABLET = "ipad"
    IOS_COUPON_CODE = "apple-discount-coupon-code"
    IOS_SYSTEM_NAME = "iPhone OS"
    IOS_SYSTEM_NAME_ALT = "iOS"

    def __eq__(self, other: Union[str, "PlatformType"]):
        if isinstance(other, str):
            return self.value == other
        elif isinstance(other, PaymentVendor):
            return self.value == other.value
