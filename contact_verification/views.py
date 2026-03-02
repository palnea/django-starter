from django.utils.translation import gettext_lazy as _
from rest_framework import status
from rest_framework.decorators import action
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.viewsets import GenericViewSet
from structlog import get_logger

from common.middlewares.global_context_middleware import GlobalContextMiddleware
from common.response.response_information_codes.message_code import MessageCode
from common.response.view_response import (
    ViewResponse,
    ViewSuccessResponse,
)
from common.view_mixins import LoggingMixin
from contact_verification.serializers import (
    ContactVerificationSerializer,
    CodeVerificationSerializer,
    VerifyContactSerializer,
)
from contact_verification.services import (
    ContactVerificationService,
    CodeVerificationService,
)

log = get_logger(__name__)


# Create your views here.
class ContactVerificationViewSet(LoggingMixin, GenericViewSet):
    serializer_class = ContactVerificationSerializer
    permission_classes = [AllowAny]

    def get_serializer_class(self):
        if self.action == "verify":
            return VerifyContactSerializer
        return self.serializer_class

    def create(self, request, *args, **kwargs):
        status_code = status.HTTP_201_CREATED
        serializer = self.serializer_class(data=request.data)
        serializer.is_valid(raise_exception=True)
        validated_data = serializer.validated_data

        context = GlobalContextMiddleware.get_global_context()
        content, message, _ = ContactVerificationService.create_contact_verification(
            validated_data,
            language_code=context.language_code,
            user=context.user,
        )
        view_response = ViewResponse(
            response_body=content,
            response_status=status_code,
            is_successful=True,
            response_information_code=MessageCode.GENERAL_SUCCESS,
            response_message=message,
        )

        return view_response.rest_response

    @action(detail=False, methods=["post"])
    def verify(self, request, *args, **kwargs):
        status_code = status.HTTP_200_OK
        serializer_class = self.get_serializer_class()
        serializer = serializer_class(data=request.data)
        serializer.is_valid(raise_exception=True)
        validated_data = serializer.validated_data

        ContactVerificationService.verify_contact(validated_data)
        view_response = ViewSuccessResponse(
            response_status=status_code,
            response_information_code=MessageCode.GENERAL_SUCCESS,
        )

        return view_response.rest_response


class CodeVerificationViewSet(LoggingMixin, GenericViewSet):
    serializer_class = CodeVerificationSerializer
    permission_classes = [IsAuthenticated]

    @action(detail=False, methods=["post"])
    def verify_email(self, request, *args, **kwargs):
        status_code = status.HTTP_201_CREATED
        serializer = self.serializer_class(data=request.data)
        serializer.is_valid(raise_exception=True)
        validated_data = serializer.validated_data

        token_payload = request.auth.payload
        content = CodeVerificationService.verify_code(
            code=validated_data.get("code"), email=token_payload.get("email")
        )
        view_response = ViewResponse(
            response_body=content,
            response_status=status_code,
            is_successful=True,
            response_information_code=MessageCode.REGISTRATION_SUCCESS,
            response_message=_("Success"),
        )

        return view_response.rest_response

    @action(detail=False, methods=["post"])
    def verify_phone(self, request, *args, **kwargs):
        status_code = status.HTTP_201_CREATED
        serializer = self.serializer_class(data=request.data)
        serializer.is_valid(raise_exception=True)
        validated_data = serializer.validated_data

        token_payload = request.auth.payload
        content = CodeVerificationService.verify_code(
            code=validated_data.get("code"), phone=token_payload.get("phone")
        )
        view_response = ViewResponse(
            response_body=content,
            response_status=status_code,
            is_successful=True,
            response_information_code=MessageCode.REGISTRATION_SUCCESS,
            response_message=_("Success"),
        )

        return view_response.rest_response
