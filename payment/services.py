import json
from typing import Dict

from django.db import transaction
from rest_framework import status
from structlog import get_logger

import settings
from common.custom_exceptions.custom_exception import CustomException
from common.response.response_information_codes.error_code import ErrorCode
from payment.constants import SUBSCRIPTION_STRATEGY_MAPPER
from payment.types import BuyableType
from payment.verifiers.appstore import AppStoreValidator
from payment.verifiers.errors import InAppPyValidationError
from user.models import User
from django.utils.translation import gettext_lazy as _

log = get_logger(__name__)


def validate_on_apple(receipt: str) -> (Dict, bool):
    validator = AppStoreValidator(
        settings.APPLE_BUNDLE_ID,
        auto_retry_wrong_env_request=settings.AUTO_RETRY_WRONG_ENVIRONMENT_REQUEST,
    )

    try:
        validation_result = validator.validate(
            receipt, "optional-shared-secret", exclude_old_transactions=True
        )
        return validation_result, True
    except InAppPyValidationError as ex:
        # handle validation error
        log.error(
            "Apple receipt validation failed.",
            transaction_id=json.loads(receipt).get("transactionID", None),
            in_app_py_validation_error=ex,
        )
        response_from_apple = (
            ex.raw_response
        )  # contains actual response from AppStore service.
        return response_from_apple, False


class PaymentService:
    @staticmethod
    @transaction.atomic
    def make_purchase(request, data: Dict):
        StrategyClass = SUBSCRIPTION_STRATEGY_MAPPER.get(data.get("store", None))

        try:
            purchase_strategy = StrategyClass(
                request, data.get("user", None), receipt=data.get("receipt", "{}")
            )
            _, is_valid = purchase_strategy.verify()
            if not is_valid:
                # New structured error format - provides better business logic error
                raise CustomException.business_logic_error(
                    title=_("Receipt Verification Failed"),
                    detail=f"The {data.get('store', 'store')} receipt could not be verified. Please check your receipt and try again.",
                    code=ErrorCode.INVALID_RECEIPT,
                    instance="/api/v1/purchases",
                    extra_data={
                        "store": data.get("store", None),
                        "receipt_status": "verification_failed",
                    },
                )
            purchase_strategy.prepare_transaction_creation_for_receipt()
        except Exception as e:
            log.error(
                "Purchase preparation failed",
                exception=str(e),
                account_id=request.user.id,
                request_data=str(request.data),
            )
            raise e

        purchase_strategy.create_transaction()

    @staticmethod
    def check_active_subscription(user: User):
        active_subscription_buyable = (
            user.active_subscription.buyable if user.active_subscription else None
        )
        if (
                active_subscription_buyable
                and active_subscription_buyable.type != BuyableType.ONE_TIME_PURCHASE
        ):
            # New structured error format - provides better business logic error
            raise CustomException.business_logic_error(
                title=_("Active Subscription Exists"),
                detail=_(
                    "You already have an active subscription. Please cancel your current subscription before purchasing a new one."
                ),
                code=ErrorCode.ACTIVE_SUBSCRIPTION_EXISTS,
                status_code=status.HTTP_409_CONFLICT,
                instance="/api/v1/subscriptions",
                extra_data={
                    "existing_subscription_type": active_subscription_buyable.type,
                    "subscription_id": (
                        user.active_subscription.id
                        if user.active_subscription
                        else None
                    ),
                },
            )
