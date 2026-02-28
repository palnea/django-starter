from django.utils.translation import gettext_lazy as _
from drf_yasg.utils import swagger_auto_schema
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
    log_view_response,
    ViewSuccessResponse,
)
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
from .services import RegistrationService, PasswordService

log = get_logger(__name__)


class UserLoginView(APIView):
    serializer_class = UserLoginSerializer
    permission_classes = (AllowAny,)

    @swagger_auto_schema(request_body=UserLoginSerializer)
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

            log_view_response(
                struct_logger=log,
                view_name=self.__class__.__name__,
                method_name="post",
                request_body=request.data,
                request_path=request.get_full_path(),
                request_method=request.method,
                view_response=view_response,
            )

            return view_response.rest_response


class UserRegisterView(APIView):
    serializer_class = UserRegisterSerializer
    permission_classes = (AllowAny,)

    @swagger_auto_schema(request_body=UserRegisterSerializer)
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

            log_view_response(
                struct_logger=log,
                view_name=self.__class__.__name__,
                method_name="post",
                request_body=request.data,
                request_path=request.get_full_path(),
                request_method=request.method,
                view_response=view_response,
            )

            return view_response.rest_response


class PasswordViewSet(GenericViewSet):
    permission_classes = [AllowAny]
    serializer_class = ResetPasswordSerializer

    @action(detail=False, methods=["post"])
    def reset_password(self, request, *args, **kwargs):
        PasswordService.reset_password(request.data)
        view_response = ViewSuccessResponse()

        log_view_response(
            struct_logger=log,
            view_name=self.__class__.__name__,
            method_name="reset_password",
            request_body=request.data,
            request_path=request.get_full_path(),
            request_method=request.method,
            view_response=view_response,
        )

        return view_response.rest_response


class UpdatePasswordViewSet(GenericViewSet):
    permission_classes = [IsAuthenticated]
    serializer_class = UpdatePasswordSerializer

    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)

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


class CustomTokenRefreshView(TokenRefreshView):
    serializer_class = CustomTokenRefreshSerializer


class GoogleSocialAuthView(GenericAPIView):
    permission_classes = [AllowAny]
    serializer_class = GoogleSocialAuthSerializer

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


class FacebookSocialAuthView(GenericAPIView):
    permission_classes = [AllowAny]
    serializer_class = FacebookSocialAuthSerializer

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


class AppleSocialAuthView(GenericAPIView):
    permission_classes = [AllowAny]
    serializer_class = AppleSocialAuthSerializer

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
