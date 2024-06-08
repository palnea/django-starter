from django.http import Http404
from drf_yasg.utils import swagger_auto_schema
from rest_framework.decorators import action
from rest_framework.permissions import IsAuthenticated, AllowAny
from rest_framework.viewsets import GenericViewSet, ModelViewSet
from structlog import get_logger
from django.utils.translation import gettext_lazy as _

from common.middlewares.global_context_middleware import GlobalContextMiddleware
from common.models import Translation
from common.permissions.generic_permissions import ContentPermission
from common.response.response_information_codes.message_code import MessageCode
from common.response.view_response import (
    log_view_response,
    ViewSuccessResponse,
    ViewResponse,
    ViewResponseNoContent,
)
from payment.models import Buyable
from payment.serializers import (
    ReceiptVerificationSerializer,
    BuyableSerializer,
)
from payment.services import PaymentService
from utils.built_in_overrides import flat_map
from vendor.notification_handlers.subscription_notification_handlers import (
    GoogleNotificationHandler,
    AppleNotificationHandler,
)

log = get_logger(__name__)


# Create your views here.
class PaymentViewSet(GenericViewSet):
    permission_classes = [IsAuthenticated]
    serializer_class = ReceiptVerificationSerializer

    @action(detail=False, methods=["post"])
    def make_purchase(self, request, *args, **kwargs):
        self.serializer_class = ReceiptVerificationSerializer
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        PaymentService.make_purchase(request, serializer.validated_data)

        view_response = ViewSuccessResponse()
        log_view_response(
            struct_logger=log,
            view_name=self.__class__.__name__,
            method_name="create",
            request_body=request.data,
            request_path=request.get_full_path(),
            request_method=request.method,
            view_response=view_response,
        )
        return view_response.rest_response


class BuyableViewSet(ModelViewSet):
    permission_classes = [ContentPermission]
    serializer_class = BuyableSerializer
    queryset = (
        Buyable.objects.all().select_related("title").select_related("description")
    )
    lookup_field = "id"

    def retrieve(self, request, *args, **kwargs):
        response = super().retrieve(request, *args, **kwargs)
        language_code = GlobalContextMiddleware.get_global_context().language_code
        translation_id_text_map = Translation.get_list_of_texts_from_id_list(
            [response.data.get("title_id"), response.data.get("description_id")],
            language_code,
        )
        result = {
            **response.data,
            "special_offer_root": (
                {
                    **response.data.get("special_offer_root", {}),
                    "title": translation_id_text_map.get(
                        response.data.get("special_offer_root", {}).get("title_id")
                    ),
                    "description": translation_id_text_map.get(
                        response.data.get("special_offer_root", {}).get(
                            "description_id"
                        )
                    ),
                }
                if response.data.get("special_offer_root")
                else None
            ),
            "title": translation_id_text_map.get(response.data.get("title_id")),
            "description": translation_id_text_map.get(
                response.data.get("description_id")
            ),
        }
        view_response = ViewResponse(
            response_body=result,
            response_status=response.status_code,
            is_successful=True,
            response_information_code=MessageCode.RETRIEVE_CONTENT_SUCCESS,
        )
        log_view_response(
            struct_logger=log,
            view_name=self.__class__.__name__,
            method_name="retrieve",
            request_body=request.data,
            request_path=request.get_full_path(),
            request_method=request.method,
            view_response=view_response,
        )
        return view_response.rest_response

    def list(self, request, *args, **kwargs):
        response = super().list(request, *args, **kwargs)
        translations = flat_map(
            lambda p: [
                p.get("description_id"),
                p.get("title_id"),
                (
                    p.get("special_offer_root", {}).get("title_id")
                    if p.get("special_offer_root")
                    else None
                ),
                (
                    p.get("special_offer_root", {}).get("description_id")
                    if p.get("special_offer_root")
                    else None
                ),
            ],
            response.data,
        )
        translation_id_text_map = Translation.get_list_of_texts_from_id_list(
            translations, GlobalContextMiddleware.get_global_context().language_code
        )
        result = [
            {
                **buyable,
                "special_offer_root": (
                    {
                        **buyable.get("special_offer_root", {}),
                        "title": translation_id_text_map.get(
                            buyable.get("special_offer_root", {}).get("title_id")
                        ),
                        "description": translation_id_text_map.get(
                            buyable.get("special_offer_root", {}).get("description_id")
                        ),
                    }
                    if buyable.get("special_offer_root")
                    else None
                ),
                "title": translation_id_text_map.get(buyable.get("title_id")),
                "description": translation_id_text_map.get(
                    buyable.get("description_id")
                ),
            }
            for buyable in response.data
        ]
        view_response = ViewResponse(
            response_body=result,
            response_status=response.status_code,
            is_successful=True,
            response_information_code=MessageCode.LIST_CONTENT_SUCCESS,
        )
        log_view_response(
            struct_logger=log,
            view_name=self.__class__.__name__,
            method_name="list",
            request_body=request.data,
            request_path=request.get_full_path(),
            request_method=request.method,
            view_response=view_response,
        )
        return view_response.rest_response

    def create(self, request, *args, **kwargs):
        response = super().create(request, *args, **kwargs)
        view_response = ViewResponse(
            response_body=response.data,
            response_status=response.status_code,
            is_successful=True,
            response_information_code=MessageCode.CREATE_CONTENT_SUCCESS,
            response_message=_("Created successfully!"),
        )
        log_view_response(
            struct_logger=log,
            view_name=self.__class__.__name__,
            method_name="create",
            request_body=request.data,
            request_path=request.get_full_path(),
            request_method=request.method,
            view_response=view_response,
        )
        return view_response.rest_response

    def partial_update(self, request, *args, **kwargs):
        response = super().partial_update(request, *args, **kwargs)
        view_response = ViewResponse(
            response_body=response.data,
            response_status=response.status_code,
            is_successful=True,
            response_information_code=MessageCode.UPDATE_CONTENT_SUCCESS,
            response_message=_("Updated successfully!"),
        )
        log_view_response(
            struct_logger=log,
            view_name=self.__class__.__name__,
            method_name="partial_update",
            request_body=request.data,
            request_path=request.get_full_path(),
            request_method=request.method,
            view_response=view_response,
        )
        return view_response.rest_response

    def destroy(self, request, *args, **kwargs):
        try:
            super().destroy(request, *args, **kwargs)
            view_response = ViewResponseNoContent(
                response_message=_("Deleted successfully!")
            )
        except Http404:
            view_response = ViewResponseNoContent(
                response_message=_("Deleted successfully!")
            )
        log_view_response(
            struct_logger=log,
            view_name=self.__class__.__name__,
            method_name="destroy",
            request_body=request.data,
            request_path=request.get_full_path(),
            request_method=request.method,
            view_response=view_response,
        )
        return view_response.rest_response


class GooglePlayWebhookViewSet(GenericViewSet):
    permission_classes = [AllowAny]

    @swagger_auto_schema(auto_schema=None)
    def create(self, request, *args, **kwargs):
        log.info("Google Play webhook is received", request=str(request.data))
        try:
            handler = GoogleNotificationHandler(request.data)
            handler.handle()
        except Exception as e:
            log.error(
                "Unhandled Google notification",
                request_data=request.data,
                exception=str(e),
            )
        view_response = ViewSuccessResponse()
        return view_response.rest_response


class AppStoreWebhookViewSet(GenericViewSet):
    permission_classes = [AllowAny]

    @swagger_auto_schema(auto_schema=None)
    def create(self, request, *args, **kwargs):
        log.info("App Store webhook is received", request=str(request.data))
        try:
            handler = AppleNotificationHandler(request.data)
            handler.handle()
        except Exception as e:
            log.error(
                "Unhandled App Store notification",
                request_data=request.data,
                exception=str(e),
            )
        view_response = ViewSuccessResponse()
        return view_response.rest_response
