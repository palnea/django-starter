import datetime
from itertools import chain

from dateutil.relativedelta import relativedelta
from django.db import models, transaction
from django.db.models import UniqueConstraint, Q
from django.utils.functional import cached_property
from django_softdelete.models import SoftDeleteModel

from payment.types import SubscriptionPeriod, BuyableType
from subscription.types import SubscriptionStatus
from utils.fields import DateTimeWithoutTZField


# Create your models here.
class UserSubscription(SoftDeleteModel):
    user = models.ForeignKey(
        "user.User",
        on_delete=models.CASCADE,
        null=False,
        related_name="subscriptions",
    )
    buyable = models.ForeignKey(
        "payment.Buyable",
        on_delete=models.CASCADE,
        null=False,
        related_name="user_subscriptions",
    )
    purchase = models.ForeignKey(
        "payment.Purchase",
        on_delete=models.DO_NOTHING,
        related_name="user_subscriptions",
        null=False,
    )
    expiration_date = DateTimeWithoutTZField(editable=True, null=False, blank=False)
    start_date = DateTimeWithoutTZField(
        editable=True, auto_now_add=True, null=False, blank=False
    )
    status = models.CharField(
        max_length=64,
        choices=SubscriptionStatus.choices,
        default=SubscriptionStatus.EXPIRED,
    )
    used_trial_days = models.IntegerField(default=0)
    created = DateTimeWithoutTZField(auto_now_add=True, editable=False)
    updated = DateTimeWithoutTZField(auto_now=True, editable=False)
    deleted_at = DateTimeWithoutTZField(blank=True, null=True)

    class Meta:
        db_table = "user_subscription"
        constraints = [
            UniqueConstraint(
                fields=["user"],
                condition=Q(status=SubscriptionStatus.ACTIVE)
                | Q(status=SubscriptionStatus.TRIAL),
                name="unique_user_active_subscription",
            )
        ]

    @transaction.atomic
    def save(
        self, force_insert=False, force_update=False, using=None, update_fields=None
    ):
        db_data = UserSubscription.objects.filter(
            id=self.id
        ).first()  # This can be done by an async handler (centry, kafka)
        if db_data:
            period = SubscriptionPeriod(db_data.buyable.period)
            opts = UserSubscription._meta
            fields = chain(opts.concrete_fields, opts.private_fields)
            different_fields = filter(
                lambda field: field.value_from_object(self)
                != field.value_from_object(db_data)
                and field.name != "expiration_date",
                fields,
            )
            if (
                len(list(different_fields)) > 0
                or db_data.expiration_date
                + UserSubscription.time_to_add_after_expiration(period)
                != self.expiration_date
            ):
                UserSubscriptionChangeRecord.objects.create(
                    user_subscription=self,
                    user=self.user,
                    buyable=self.buyable,
                    purchase=self.purchase,
                    expiration_date=self.expiration_date,
                    status=self.status,
                    used_trial_days=self.used_trial_days,
                )
        super().save(force_insert, force_update, using, update_fields)

    @cached_property
    def current_status(self):
        if (
            self.expiration_date < datetime.datetime.utcnow()
            and self.status != SubscriptionStatus.EXPIRED
        ):
            self.status = SubscriptionStatus.EXPIRED
            self.save()
        if (
            self.start_date > datetime.datetime.utcnow()
            and self.status != SubscriptionStatus.INITIAL
        ):
            self.status = SubscriptionStatus.INITIAL
            self.save()
        if (
            self.status == SubscriptionStatus.INITIAL
            and self.start_date < datetime.datetime.utcnow() < self.expiration_date
        ):
            self.status = SubscriptionStatus.ACTIVE
            self.save()
        return self.status

    @cached_property
    def is_active(self):
        return SubscriptionStatus.is_active_value(self.status)

    def renew(self, period=None, trial=False, from_now=False):
        if not period:
            period = SubscriptionPeriod(self.buyable.period)

        self.status = (
            SubscriptionStatus.ACTIVE if not trial else SubscriptionStatus.TRIAL
        )
        expiration_base_time = (
            datetime.datetime.utcnow() if from_now else self.expiration_date
        )
        self.expiration_date = (
            expiration_base_time + UserSubscription.time_to_add_after_expiration(period)
        )
        self.save()

    @staticmethod
    def time_to_add_after_expiration(period: SubscriptionPeriod):
        if period == SubscriptionPeriod.MONTHLY:
            return relativedelta(months=1)
        elif period == SubscriptionPeriod.SEMI_ANNUAL:
            return relativedelta(months=6)
        elif period == SubscriptionPeriod.ANNUAL:
            return relativedelta(years=1)

    def as_json(self):
        return {
            "id": self.id,
            "user_id": str(self.user_id),
            "expiration_date": str(self.expiration_date),
            "start_date": str(self.start_date),
            "status": self.current_status,
            "period": self.buyable.period,
            "type": self.buyable.type,
            "used_trial_days": self.used_trial_days,
            "created": str(self.created),
            "updated": str(self.updated),
            "deleted_at": str(self.deleted_at),
        }

    def safe_json(self):
        try:
            status = self.current_status
        except Exception:
            status = SubscriptionStatus.ACTIVE

        try:
            period = self.buyable.period
        except Exception:
            period = SubscriptionPeriod.MONTHLY.value

        try:
            type = self.buyable.type
        except Exception:
            type = BuyableType.PERSONAL_SUBSCRIPTION.value

        return {
            "id": self.id,
            "user_id": str(self.user_id),
            "expiration_date": str(self.expiration_date),
            "start_date": str(self.start_date),
            "status": status,
            "period": period,
            "type": type,
            "used_trial_days": self.used_trial_days,
            "created": str(self.created),
            "updated": str(self.updated),
            "deleted_at": str(self.deleted_at),
        }


class UserSubscriptionChangeRecord(models.Model):
    user_subscription = models.ForeignKey(
        UserSubscription, on_delete=models.CASCADE, related_name="change_history"
    )
    user = models.ForeignKey(
        "user.User",
        on_delete=models.CASCADE,
        null=False,
        related_name="subscription_changes",
    )
    buyable = models.ForeignKey(
        "payment.Buyable",
        on_delete=models.CASCADE,
        null=False,
        related_name="user_subscription_changes",
    )
    purchase = models.ForeignKey(
        "payment.Purchase",
        on_delete=models.DO_NOTHING,
        related_name="user_subscription_change",
        null=False,
    )
    expiration_date = DateTimeWithoutTZField(editable=True, null=False, blank=False)
    start_date = DateTimeWithoutTZField(
        editable=True, auto_now_add=True, null=False, blank=False
    )
    status = models.CharField(
        max_length=64,
        choices=SubscriptionStatus.choices,
        default=SubscriptionStatus.EXPIRED,
    )
    used_trial_days = models.IntegerField(default=0)
    created = DateTimeWithoutTZField(auto_now_add=True, editable=False)
    updated = DateTimeWithoutTZField(auto_now=True, editable=False)

    class Meta:
        db_table = "user_subscription_change_record"
