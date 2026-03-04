from django.utils.translation import gettext_lazy as _
from drf_spectacular.utils import extend_schema
from rest_framework import status
from rest_framework.decorators import action
from rest_framework.generics import GenericAPIView
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.views import APIView
from rest_framework.viewsets import GenericViewSet
from rest_framework_simplejwt.views import TokenRefreshView
from structlog import get_logger

from common.middlewares.global_context_middleware import GlobalContextMiddleware
from common.response.response_information_codes.message_code import MessageCode
from common.response.view_response import (
    ViewResponse,
    ViewSuccessResponse,
)
from common.view_mixins import LoggingMixin
from .serializers import (
    UserLoginSerializer,
    UserRegisterSerializer,
    UpdatePasswordSerializer,
    CustomTokenRefreshSerializer,
    ResetPasswordSerializer,
    GoogleSocialAuthSerializer,
    FacebookSocialAuthSerializer,
    AppleSocialAuthSerializer,
)
from common.throttles import AuthRateThrottle
from .services import RegistrationService, PasswordService

log = get_logger(__name__)


class UserLoginView(LoggingMixin, APIView):
    serializer_class = UserLoginSerializer
    permission_classes = (AllowAny,)
    throttle_classes = [AuthRateThrottle]

    @extend_schema(request=UserLoginSerializer)
    def post(self, request):
        serializer = self.serializer_class(data=request.data)
        valid = serializer.is_valid(raise_exception=True)

        if valid:
            status_code = status.HTTP_200_OK

            content = {**serializer.validated_data}

            view_response = ViewResponse(
                response_body=content,
                response_status=status_code,
                is_successful=True,
                response_information_code=MessageCode.USER_LOGIN_SUCCESS,
                response_message=_("Logged in successfully."),
            )

            return view_response.rest_response


class UserRegisterView(LoggingMixin, APIView):
    serializer_class = UserRegisterSerializer
    permission_classes = (AllowAny,)
    throttle_classes = [AuthRateThrottle]

    @extend_schema(request=UserRegisterSerializer)
    def post(self, request):
        serializer = self.serializer_class(data=request.data)
        valid = serializer.is_valid(raise_exception=True)
        context = GlobalContextMiddleware.get_global_context()
        content = RegistrationService.register(
            serializer.validated_data,
            language_code=context.language_code,
        )

        if valid:
            status_code = status.HTTP_200_OK

            view_response = ViewResponse(
                response_body=content,
                response_status=status_code,
                is_successful=True,
                response_information_code=MessageCode.REGISTRATION_SUCCESS,
                response_message=_("Registered successfully."),
            )

            return view_response.rest_response


class PasswordViewSet(LoggingMixin, GenericViewSet):
    permission_classes = [AllowAny]
    serializer_class = ResetPasswordSerializer
    throttle_classes = [AuthRateThrottle]

    @action(detail=False, methods=["post"])
    def reset_password(self, request, *args, **kwargs):
        PasswordService.reset_password(request.data)
        view_response = ViewSuccessResponse()

        return view_response.rest_response


class UpdatePasswordViewSet(LoggingMixin, GenericViewSet):
    permission_classes = [IsAuthenticated]
    serializer_class = UpdatePasswordSerializer

    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        view_response = ViewSuccessResponse()

        return view_response.rest_response


class CustomTokenRefreshView(TokenRefreshView):
    serializer_class = CustomTokenRefreshSerializer


class GoogleSocialAuthView(LoggingMixin, GenericAPIView):
    permission_classes = [AllowAny]
    serializer_class = GoogleSocialAuthSerializer
    throttle_classes = [AuthRateThrottle]

    def post(self, request):
        """POST with "auth_token".

        Send an idtoken as from google to get user information
        """
        status_code = status.HTTP_200_OK
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        response_body = (serializer.validated_data)["auth_token"]

        view_response = ViewResponse(
            response_body=response_body,
            response_status=status_code,
            is_successful=True,
            response_information_code=MessageCode.BASE_LOGIN_SUCCESS,
        )
        return view_response.rest_response


class FacebookSocialAuthView(LoggingMixin, GenericAPIView):
    permission_classes = [AllowAny]
    serializer_class = FacebookSocialAuthSerializer
    throttle_classes = [AuthRateThrottle]

    def post(self, request):
        """POST with "auth_token".

        Send an access token as from facebook to get user information
        """

        status_code = status.HTTP_200_OK
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        response_body = (serializer.validated_data)["auth_token"]
        view_response = ViewResponse(
            response_body=response_body,
            response_status=status_code,
            is_successful=True,
            response_information_code=MessageCode.BASE_LOGIN_SUCCESS,
        )
        return view_response.rest_response


class AppleSocialAuthView(LoggingMixin, GenericAPIView):
    permission_classes = [AllowAny]
    serializer_class = AppleSocialAuthSerializer
    throttle_classes = [AuthRateThrottle]

    def post(self, request):
        """POST with "auth_token".

        Send an access token as from facebook to get user information
        """

        status_code = status.HTTP_200_OK
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        response_body = (serializer.validated_data)["code"]
        view_response = ViewResponse(
            response_body=response_body,
            response_status=status_code,
            is_successful=True,
            response_information_code=MessageCode.BASE_LOGIN_SUCCESS,
        )
        return view_response.rest_response
