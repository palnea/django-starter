import uuid
from typing import List, Dict

from django.contrib.auth.base_user import AbstractBaseUser
from django.contrib.auth.models import PermissionsMixin
from django.contrib.auth.validators import UnicodeUsernameValidator
from django.db import models
from django.db.models import Q, Case, When, Value, CharField
from django.utils.functional import cached_property
from django.utils.translation import gettext_lazy as _
from django_softdelete.models import SoftDeleteModel
from phonenumber_field.modelfields import PhoneNumberField
from rest_framework import status

from authy.managers import CustomUserManager
from common.custom_exceptions.custom_exception import CustomException
from common.models import Locale
from common.response.response_information_codes.error_code import ErrorCode
from subscription.models import UserSubscription
from subscription.types import SubscriptionStatus
from user.types import UserCreationType
from user.validators import UserValidator
from utils.converters import ModelConverter
from common.fields import DateTimeWithoutTZField


class User(AbstractBaseUser, SoftDeleteModel, PermissionsMixin):
    username_validator = UnicodeUsernameValidator()

    id = models.UUIDField(
        unique=True, primary_key=True, default=uuid.uuid4, editable=False
    )
    phone = PhoneNumberField(null=True, blank=True)
    phone_verified = models.BooleanField(null=False, blank=False, default=False)
    email = models.EmailField(null=True, blank=True)
    email_verified = models.BooleanField(null=False, blank=False, default=False)

    # User profile fields
    fullname = models.CharField(max_length=255, blank=True)
    locale = models.ForeignKey(
        Locale,
        on_delete=models.CASCADE,
        related_name="users",
        null=True,
        blank=True,
    )
    creation_type = models.CharField(
        max_length=16, choices=UserCreationType.choices, null=False, blank=False
    )

    # Permission fields
    is_active = models.BooleanField(
        _("active"),
        default=True,
        help_text=_(
            "Designates whether this user should be treated as active. "
            "Unselect this instead of deleting accounts."
        ),
    )
    is_staff = models.BooleanField(default=False)

    # Timestamps
    created = DateTimeWithoutTZField(auto_now_add=True, editable=False)
    updated = DateTimeWithoutTZField(auto_now=True, editable=False)
    deleted_at = DateTimeWithoutTZField(blank=True, null=True)

    USERNAME_FIELD = "email"
    REQUIRED_FIELDS = []

    objects = CustomUserManager()

    def save(self, *args, **kwargs):
        if self.locale_id is None:
            self.locale = Locale.get_default()
        super().save(*args, **kwargs)

    def __str__(self):
        return self.email or self.phone_as_international or str(self.id)

    class Meta:
        db_table = "user"
        constraints = [
            models.UniqueConstraint(
                fields=["phone"],
                condition=Q(deleted_at__isnull=True)
                & Q(phone__isnull=False)
                & ~Q(phone=""),
                name="user_unique_phone",
            ),
            models.UniqueConstraint(
                fields=["email"],
                condition=Q(deleted_at__isnull=True)
                & Q(email__isnull=False)
                & ~Q(email=""),
                name="user_unique_email",
            ),
            models.CheckConstraint(
                check=(Q(email__isnull=False) & ~Q(email__exact=""))
                | (Q(phone__isnull=False) & ~Q(phone__exact="")),
                name="user_at_least_email_or_phone_not_null",
            ),
        ]
        indexes = [models.Index(fields=["created"])]

    @property
    def phone_as_international(self):
        return self.phone.as_international if self.phone else None

    @cached_property
    def active_subscription(self) -> UserSubscription:
        active_statuses = filter(
            lambda choice: choice.is_active, [choice for choice in SubscriptionStatus]
        )
        return (
            self.subscriptions.filter(status__in=active_statuses)
            .order_by("-id")
            .first()
        )

    @cached_property
    def last_or_active_subscription(self) -> UserSubscription:
        subscriptions = (
            self.subscriptions.select_related("buyable")
            .annotate(
                priority=Case(
                    When(status="active", then=Value(1)),
                    default=Value(2),
                    output_field=CharField(),
                )
            )
            .order_by("priority", "-created")
        )

        return subscriptions.first()

    @property
    def has_active_subscription(self):
        return self.active_subscription is not None

    def to_dict(
        self,
        fields: List = None,
        exclude: List = None,
        detailed_fields: Dict = None,
        fields_as: Dict = None,
    ):
        user_dict = ModelConverter.model_to_dict(
            self,
            fields=fields,
            exclude=exclude,
            detailed_fields=detailed_fields,
            fields_as=fields_as,
        )

        if user_dict.get("phone"):
            user_dict["phone"] = user_dict["phone"].as_international.replace(" ", "")
        return user_dict

    @staticmethod
    def create_with_password(data: Dict[str, any]):
        """Creates a user with password."""
        errors, validated_data = UserValidator(data).validate_create()
        if errors:
            raise CustomException.business_logic_error(
                title=_("Validation error occured. Please check the fields."),
                detail=str(errors),
                code=ErrorCode.GENERAL_VALIDATION_ERROR,
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )

        password = validated_data.pop("password")
        user = User.objects.create(
            **validated_data,
            creation_type=UserCreationType.PERSONAL,
        )
        user.set_password(password)
        user.save()
        return user
