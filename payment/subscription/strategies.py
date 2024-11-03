import json
from decimal import Decimal
from typing import Dict

import jwt
from django.conf import settings
from django.db import IntegrityError, transaction
from django.utils.functional import cached_property
from moneyed import Currency
from rest_framework import status
from structlog import get_logger

from common.custom_exceptions.custom_exception import CustomException
from common.response.response_information_codes.error_code import ErrorCode
from payment.models import Buyable, Purchase, PaymentTransaction
from payment.signals import purchase_for_subscription_created
from payment.types import BuyableType, PaymentVendor, PlatformType, PaymentStatus
from payment.verifiers.errors import InAppPyValidationError
from payment.verifiers.googleplay import GooglePlayValidator
from subscription.models import UserSubscription
from user.models import User
from utils.converters import ValueConverter
from vendor.clients.appstore import AppStoreInAppPurchaseAPIClient, AppStoreConnectAPI

log = get_logger(__name__)


class MobilePurchaseStrategy:
    def __init__(self, request, user: User, receipt: str = None):
        self.request = request
        self.user = user
        self._receipt = receipt

        self._user_has_subscription = None
        self._should_create_transaction = False
        self.verified_response = None
        self.receipt_verification_result = None
        self._prepared_for_transaction = False
        self._platform = None
        self._vendor = None
        self._buyable: Buyable = None
        self._purchase: Purchase = None
        self._payment_transaction: PaymentTransaction = None

    @cached_property
    def receipt(self):
        receipt = (
            self._receipt.replace("\\", "")
            .replace('"{', "{")
            .replace('}"', "}")
            .replace('"[', "[")
            .replace(']"', "]")
        )
        return json.loads(receipt)

    def verify(self):
        pass

    def validate_receipt_data(self):
        pass

    def prepare_transaction_creation(self):
        pass

    @transaction.atomic
    def create_transaction(self):
        if not self.prepared_for_transaction:
            log.error(
                "Cannot call create transaction before prepare_transaction_creation",
                user=self.user.id,
                platform=self.platform,
                vendor=self.vendor,
            )
            raise CustomException(
                "Called create_transaction before prepare_for_transaction",
                code=ErrorCode.INTERNAL_SERVER_ERROR,
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )

        if self._purchase.id:
            purchase = self._purchase
        else:
            purchase = Purchase.objects.create(
                user=self.user,
                stored_payment_method_id=self._purchase.stored_payment_method_id,
                buyables=[self._buyable],
                vendor=self._purchase.vendor,
                original_transaction_id=self._purchase.original_transaction_id,
            )

        try:
            payment_transaction = PaymentTransaction.objects.create(
                purchase=purchase,
                list_amount=self._payment_transaction.list_amount,
                charge_amount=self._payment_transaction.charge_amount,
                credit_amount=self._payment_transaction.credit_amount,
                payment_vendor=self._payment_transaction.payment_vendor,
                payment_method=self._payment_transaction.payment_method,
                currency=self._payment_transaction.currency,
                tax_rate=self._payment_transaction.tax_rate,
                payer_id=self._payment_transaction.payer_id,
                ip_address=self._payment_transaction.ip_address,
                status=self._payment_transaction.status,
                transaction_id=self._payment_transaction.transaction_id,
                receipt=self._payment_transaction.receipt,
                raw_product_data=self._payment_transaction.raw_product_data,
            )
        except IntegrityError as e:
            # Cover the case of repeated requests
            if "unique_payment_transaction_payment_vendor_key_transaction_id" in str(e):
                return
            raise e

        if self._buyable.type != BuyableType.ONE_TIME_PURCHASE:
            purchase_for_subscription_created.send_robust(
                instance=payment_transaction, product=self._buyable, sender=None
            )

    @cached_property
    def active_subscription_of_user(self) -> UserSubscription:
        active_subscription_buyable = (
            self.user.active_subscription.buyable
            if self.user.active_subscription
            else None
        )
        if (
            active_subscription_buyable
            and active_subscription_buyable.type != BuyableType.ONE_TIME_PURCHASE
        ):
            return self.user.active_subscription

    @property
    def should_create_transaction(self) -> bool:
        return self._should_create_transaction

    @property
    def user_has_subscription(self) -> bool:
        return self.active_subscription_of_user is not None

    @property
    def prepared_for_transaction(self) -> bool:
        return self._prepared_for_transaction

    @property
    def platform(self) -> PlatformType:
        return self._platform

    @property
    def vendor(self) -> PaymentVendor:
        return self._vendor


class GooglePurchaseStrategy(MobilePurchaseStrategy):
    def __init__(self, request, user: User, receipt: str = None):
        if not receipt:
            receipt = request.data.get("receipt", "{}")

        super().__init__(request, user, receipt)
        self._vendor = PaymentVendor.GOOGLE
        self._platform = PlatformType.GOOGLE_FAMILY

        if not all(
            [
                self.receipt.get("Payload", {}).get("json", {}).get("purchaseToken"),
                self.receipt.get("Payload", {}).get("json", {}).get("productId"),
            ]
        ):
            raise CustomException(
                detail={"general": ["Google receipt data has missing fields."]},
                code=ErrorCode.INVALID_RECEIPT,
                status_code=status.HTTP_400_BAD_REQUEST,
            )

    def verify(self):
        purchase_token = self.receipt.get("Payload").get("json").get("purchaseToken")
        product_sku = self.receipt.get("Payload").get("json").get("productId")

        # api_credentials = {
        #     "type": settings.GOOGLE_PLAY_TYPE,
        #     "project_id": settings.GOOGLE_PLAY_PROJECT_ID,
        #     "private_key_id": settings.GOOGLE_PLAY_PRIVATE_KEY_ID,
        #     "private_key": settings.GOOGLE_PLAY_PRIVATE_KEY.replace("\\n", "\n"),
        #     "client_email": settings.GOOGLE_PLAY_CLIENT_EMAIL,
        #     "client_id": settings.GOOGLE_PLAY_CLIENT_ID,
        #     "auth_uri": settings.GOOGLE_PLAY_AUTH_URI,
        #     "token_uri": settings.GOOGLE_PLAY_TOKEN_URI,
        #     "auth_provider_x509_cert_url": settings.GOOGLE_PLAY_AUTH_PROVIDER_X509_CERT_URL,
        #     "client_x509_cert_url": settings.GOOGLE_PLAY_CLIENT_X509_CERT_URL,
        #     "universe_domain": settings.GOOGLE_PLAY_UNIVERSE_DOMAIN,
        # }
        #
        # verifier = GooglePlayVerifier(
        #     settings.GOOGLE_PLAY_PACKAGE_NAME, api_credentials
        # )
        #
        # result = verifier.verify_with_result(
        #     purchase_token, product_sku, is_subscription=True
        # )
        # self.verified_response = result.__dict__
        # self.receipt_verification_result = not result.is_expired

        # TODO uncomment above and delete blow until the second return
        price = (
            self.request.data.get("raw_product_data", {})
            .get("purchasedProduct", {})
            .get("metadata", {})
            .get("localizedPrice")
        )
        price_micros = int(price * 1000000)

        result = {
            "raw_response": {
                "currencyCode": self.request.data.get("raw_product_data", {})
                .get("purchasedProduct", {})
                .get("metadata", {})
                .get("isoCurrencyCode"),
                "priceAmountMicros": price_micros,
                "priceCurrencyCode": self.request.data.get("raw_product_data", {})
                .get("purchasedProduct", {})
                .get("metadata", {})
                .get("isoCurrencyCode"),
            }
        }
        self.verified_response = result
        return result, True

        return result.__dict__, not result.is_expired

    def validate_receipt_data(self) -> dict:
        if not self.receipt:
            raise CustomException(
                "Provided receipt cannot be empty or null",
                code=ErrorCode.EMPTY_OR_NULL_RECEIPT,
                status_code=status.HTTP_400_BAD_REQUEST,
            )

        validator = GooglePlayValidator(
            settings.GOOGLE_PLAY_PACKAGE_NAME, settings.GOOGLE_PLAY_RSA_KEY
        )

        try:
            validation_result = validator.validate(
                self._receipt,
                self.receipt.get("Payload", {}).get("signature"),
            )
        except InAppPyValidationError as e:
            raise CustomException(
                "Provided receipt is not valid",
                code=ErrorCode.INVALID_RECEIPT,
                status_code=status.HTTP_400_BAD_REQUEST,
            )
        return validation_result

    def prepare_transaction_creation_for_receipt(self):
        # self.validate_receipt_data() Cannot be used due to rsa validation failure
        if self.verified_response is None:
            raise CustomException(
                detail={"error": "Called prepare transaction before verification"},
                code=ErrorCode.VERIFICATION_PREREQUISITE_NOT_SATISFIED,
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )

        request_data = self.request.data
        buyable = Buyable.objects.get(name=request_data.get("product_key"))
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
                stored_payment_method_id=self.request.data.get(
                    "stored_payment_method", None
                ),
                vendor=self.vendor,
            )
        self._payment_transaction = PaymentTransaction(
            purchase=self._purchase,
            list_amount=buyable.get_store_price(
                store=self.vendor,
                country_code=self.verified_response.get("raw_response", {}).get(
                    "countryCode", None
                ),
            ).amount,
            charge_amount=ValueConverter.micros2decimal(
                int(
                    self.verified_response.get("raw_response", {}).get(
                        "priceAmountMicros"
                    )
                )
            ),
            credit_amount=0,
            payment_vendor=self.vendor,
            payment_method="credit_card",
            currency=Currency(
                self.verified_response.get("raw_response", {}).get("priceCurrencyCode"),
            ),
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


class ApplePurchaseStrategy(MobilePurchaseStrategy):
    def __init__(self, request, user: User, receipt: str = None):
        if not receipt:
            receipt = request.data.get("receipt", "{}")

        super().__init__(request, user, receipt)
        self._vendor = PaymentVendor.APPLE
        self._platform = PlatformType.IOS_FAMILY

        if not self.receipt.get("TransactionID"):
            raise CustomException(
                detail={"general": ["Apple receipt data has missing fields."]},
                code=ErrorCode.INVALID_RECEIPT,
                status_code=status.HTTP_400_BAD_REQUEST,
            )

    def _get_subscription_details(
        self, subscription_group_id: str, product_key: str, country_code: str
    ) -> Dict:
        if subscription_group_id is None or product_key is None or country_code is None:
            raise CustomException(
                detail={
                    "error": "Non of these attributes can be null. (subscription_group_id, product_key, country_code)",
                    "values": {
                        "subscription_group_id": subscription_group_id,
                        "product_key": product_key,
                        "country_code": country_code,
                    },
                }
            )

        connect_api_client = AppStoreConnectAPI(http_timeout=20)
        subscriptions = connect_api_client.list_subscriptions_in_subscription_group(
            subscription_group_id
        ).get("data", [])
        buyable = next(
            filter(
                lambda p: p.get("attributes", {}).get("productId", None) == product_key,
                subscriptions,
            ),
            None,
        )
        if buyable is None:
            raise CustomException(
                detail={
                    "error": f"No product can be gotten for product_key: {product_key}, subscription_group_id: {subscription_group_id}",
                    "subscription_list": subscriptions,
                },
                code=ErrorCode.INTERNAL_SERVER_ERROR,
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )
        product_id = buyable.get("id")
        price_info = connect_api_client.list_subscription_price(
            product_id=product_id, country_code=country_code
        )
        included_data = price_info.get("included", [])

        territory = next(
            filter(lambda t: t.get("type") == "territories", included_data), {}
        )
        currency = territory.get("attributes", {}).get("currency")
        if currency is None:
            raise CustomException(
                detail={
                    "error": f"No currency can be gotten for product_key: {product_key}, product_id: {product_id}, country_code: {country_code}",
                    "price_info": price_info,
                },
                code=ErrorCode.INTERNAL_SERVER_ERROR,
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )
        subscription_price_point = next(
            filter(
                lambda spp: spp.get("type") == "subscriptionPricePoints", included_data
            ),
            {},
        )
        price = subscription_price_point.get("attributes", {}).get(
            "customerPrice", None
        )
        if price is None:
            raise CustomException(
                detail={
                    "error": f"No price can be gotten for product_key: {product_key}, product_id: {product_id}, country_code: {country_code}",
                    "price_info": price_info,
                },
                code=ErrorCode.INTERNAL_SERVER_ERROR,
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )

        return {
            "product_id": product_id,
            "product_key": product_key,
            "subscription_group_id": subscription_group_id,
            "country_code": country_code,
            "currency": currency,
            "price": price,
        }

    def _get_transaction_details(self) -> Dict:
        apple_client = AppStoreInAppPurchaseAPIClient(
            sandbox=False,
            auto_retry_wrong_env_request=settings.AUTO_RETRY_WRONG_ENVIRONMENT_REQUEST,
            http_timeout=20,
        )

        transaction_data = apple_client.get_transaction_info(
            self.request.data.get("transaction_id")
        )
        if not transaction_data:
            return {}
        signed_transaction_info = transaction_data.get("signedTransactionInfo", None)

        transaction_info = jwt.decode(
            signed_transaction_info,
            algorithms=["RS256"],
            options={"verify_signature": False},
        )

        return transaction_info

    def verify(self):
        # transaction_info = self._get_transaction_details()
        # expires_at = transaction_info.get("expiresDate", 0)
        #
        # subscription_data = self._get_subscription_details(
        #     subscription_group_id=transaction_info["subscriptionGroupIdentifier"],
        #     product_key=transaction_info["productId"],
        #     country_code=transaction_info["storefront"],
        # )
        # self.verified_response = {
        #     "transaction_data": transaction_info,
        #     "subscription_data": subscription_data,
        # }
        # self.receipt_verification_result = time.time() * 1000 < expires_at

        # TODO uncomment above and delete blow until the second return
        result = {
            "transaction_data": {
                "originalTransactionId": self.request.data.get("transaction_id")
            },
            "subscription_data": {
                "country_code": self.request.data.get("raw_product_data", {})
                .get("purchasedProduct", {})
                .get("metadata", {})
                .get("isoCurrencyCode"),
                "price": self.request.data.get("raw_product_data", {})
                .get("purchasedProduct", {})
                .get("metadata", {})
                .get("localizedPrice"),
                "currency": self.request.data.get("raw_product_data", {})
                .get("purchasedProduct", {})
                .get("metadata", {})
                .get("isoCurrencyCode"),
            },
        }
        self.verified_response = result
        return result, True

        return self.verified_response, self.receipt_verification_result

    def prepare_transaction_creation_for_receipt(self):
        if self.verified_response is None:
            raise CustomException(
                detail={"error": "Called prepare transaction before verification"},
                code=ErrorCode.VERIFICATION_PREREQUISITE_NOT_SATISFIED,
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )

        request_data = self.request.data
        product = Buyable.objects.get(name=request_data.get("product_key"))
        transaction_id = request_data.get("transaction_id")
        raw_product_data = request_data.get("raw_product_data")

        self._buyable = product
        if self.user_has_subscription:
            self._purchase = Purchase.objects.filter(
                user=self.user,
                products__in=[self.active_subscription_of_user.buyable],
            ).first()

        if self._purchase is None:
            self._purchase = Purchase(
                user=self.user,
                stored_payment_method_id=self.request.data.get(
                    "stored_payment_method", None
                ),
                vendor=self.vendor,
                original_transaction_id=self.verified_response.get(
                    "transaction_data"
                ).get("originalTransactionId"),
            )
        self._payment_transaction = PaymentTransaction(
            purchase=self._purchase,
            list_amount=product.get_store_price(
                store=self.vendor,
                country_code=self.verified_response.get("subscription_data").get(
                    "country_code"
                ),
            ).amount,
            charge_amount=Decimal(
                self.verified_response.get("subscription_data").get("price")
            ),
            credit_amount=0,
            payment_vendor=self.vendor,
            payment_method="credit_card",
            currency=Currency(
                self.verified_response.get("subscription_data").get("currency")
            ),
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
