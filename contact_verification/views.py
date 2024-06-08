from django.utils.translation import gettext_lazy as _
from rest_framework import status
from rest_framework.decorators import action
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.viewsets import GenericViewSet
from structlog import get_logger

from common.response.response_information_codes.message_code import MessageCode
from common.response.view_response import ViewResponse, log_view_response
from contact_verification.serializers import (
    ContactVerificationSerializer,
    CodeVerificationSerializer,
)
from contact_verification.services import (
    ContactVerificationService,
    CodeVerificationService,
)

log = get_logger(__name__)


# Create your views here.
class ContactVerificationViewSet(GenericViewSet):
    serializer_class = ContactVerificationSerializer
    permission_classes = [AllowAny]

    def create(self, request, *args, **kwargs):
        status_code = status.HTTP_201_CREATED
        serializer = self.serializer_class(data=request.data)
        serializer.is_valid(raise_exception=True)
        validated_data = serializer.validated_data

        content, message = ContactVerificationService.create_contact_verification(
            validated_data
        )
        view_response = ViewResponse(
            response_body=content,
            response_status=status_code,
            is_successful=True,
            response_information_code=MessageCode.GENERAL_SUCCESS,
            response_message=message,
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


class CodeVerificationViewSet(GenericViewSet):
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
