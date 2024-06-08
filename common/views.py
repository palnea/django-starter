from django.db import IntegrityError
from django.db.models import Q, Count
from django.http import Http404
from rest_framework import status
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.request import Request
from rest_framework.viewsets import ModelViewSet
from structlog import get_logger

from common.custom_exceptions.custom_exception import CustomException
from common.models import Translation, TranslatedFile, Locale
from common.permissions.generic_permissions import EditorAndUp, EditorAndUpOrReadOnly
from common.response.response_information_codes.error_code import ErrorCode
from common.response.response_information_codes.message_code import MessageCode
from common.response.view_response import (
    ViewResponse,
    log_view_response,
    ViewResponseNoContent,
)
from common.serializers import (
    TranslationSerializer,
    TranslatedFileSerializer,
    TranslationBulkCreateSerializer,
    TranslatedFileBulkCreateSerializer,
    LocaleSerializer,
)
from common.services import TranslationService, TranslatedFileService
from utils.converters import ValueConverter
from django.utils.translation import gettext_lazy as _

log = get_logger(__name__)


class TranslationViewSet(ModelViewSet):
    permission_classes = [EditorAndUp]
    serializer_class = TranslationSerializer
    lookup_field = "id"

    def get_queryset(self):
        request = self.request
        params = request.query_params
        locale_code = params.get("locale_code", None)
        language = params.get("language", None)
        text = params.get("text", None)
        is_root = params.get("is_root", None)
        order_by = params.get("order_by", None)
        query_set = Translation.objects.all()
        if locale_code:
            query_set = query_set.filter(locale__code=locale_code)
        if language:
            query_set = query_set.filter(locale__code=language)
        if text:
            query_set = query_set.filter(Q(text__icontains=text) | Q(root__text=text))
        if is_root is not None and ValueConverter.str2bool(is_root, empty_is_true=True):
            query_set = query_set.annotate(nchild=Count("translations")).filter(
                nchild__gt=0
            )

        if order_by:
            query_set.order_by(order_by)

        return query_set.select_related("root").select_related("locale")

    def retrieve(self, request, *args, **kwargs):
        response = super().retrieve(request, *args, **kwargs)
        view_response = ViewResponse(
            response_body=response.data,
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
        view_response = ViewResponse(
            response_body=response.data,
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

    def handle_duplicate_locale_text_index(self, request: Request) -> Response:
        translation = Translation.objects.filter(
            locale_id=request.data.get("locale"), text=request.data.get("text")
        ).first()
        if not translation:
            raise CustomException(
                detail={"error": "An error occured"},
                code=ErrorCode.UNKNOWN_ERROR,
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )
        serializer = self.get_serializer(translation)
        headers = self.get_success_headers(serializer.data)
        return Response(
            serializer.data, status=status.HTTP_201_CREATED, headers=headers
        )

    def handle_locale_text_duplication(
            self, request: Request, create_exception: Exception
    ):
        try:
            return self.handle_duplicate_locale_text_index(request)
        except:
            raise create_exception

    def create(self, request, *args, **kwargs):
        try:
            response = super().create(request, *args, **kwargs)
        except Exception as create_exception:
            query_params = request.query_params.copy()
            return_existing_one = ValueConverter.str2bool(
                query_params.get("return_existing_one", "False"), empty_is_true=True
            )

            if return_existing_one:
                response = self.handle_locale_text_duplication(
                    request, create_exception
                )
            else:
                raise create_exception

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

    @action(detail=False, methods=["post"])
    def bulk_create(self, request, *args, **kwargs):
        status_code = status.HTTP_201_CREATED
        self.serializer_class = TranslationBulkCreateSerializer
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        query_params = request.query_params
        translations = TranslationService.bulk_create(
            serializer.validated_data, query_params
        )
        view_response = ViewResponse(
            response_body=translations,
            response_status=status_code,
            is_successful=True,
            response_information_code=MessageCode.CREATE_CONTENT_SUCCESS,
            response_message=_("Created successfully!"),
        )
        log_view_response(
            struct_logger=log,
            view_name=self.__class__.__name__,
            method_name="bulk_create",
            request_body=request.data,
            request_path=request.get_full_path(),
            request_method=request.method,
            view_response=view_response,
        )
        return view_response.rest_response


class TranslatedFileViewSet(ModelViewSet):
    permission_classes = [EditorAndUp]
    serializer_class = TranslatedFileSerializer
    lookup_field = "id"

    def get_queryset(self):
        request = self.request
        params = request.query_params
        locale_code = params.get("locale_code", None)
        language = params.get("language", None)
        is_root = params.get("is_root", None)
        order_by = params.get("order_by", None)
        name = params.get("name", None)
        query_set = TranslatedFile.objects.all()
        if locale_code:
            query_set = query_set.filter(locale__code=locale_code)
        if language:
            query_set = query_set.filter(locale__code=language)
        if name:
            query_set = query_set.filter(name__icontains=name)
        if is_root is not None and ValueConverter.str2bool(is_root, empty_is_true=True):
            query_set = query_set.annotate(nchild=Count("translations")).filter(
                nchild__gt=0
            )

        if order_by:
            query_set.order_by(order_by)

        return query_set.select_related("root").select_related("locale")

    def retrieve(self, request, *args, **kwargs):
        response = super().retrieve(request, *args, **kwargs)
        view_response = ViewResponse(
            response_body=response.data,
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
        view_response = ViewResponse(
            response_body=response.data,
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

    @action(detail=False, methods=["post"])
    def bulk_create(self, request, *args, **kwargs):
        status_code = status.HTTP_201_CREATED
        self.serializer_class = TranslatedFileBulkCreateSerializer
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        translations = TranslatedFileService.bulk_create(serializer.validated_data)
        view_response = ViewResponse(
            response_body=translations,
            response_status=status_code,
            is_successful=True,
            response_information_code=MessageCode.CREATE_CONTENT_SUCCESS,
            response_message=_("Created successfully!"),
        )
        log_view_response(
            struct_logger=log,
            view_name=self.__class__.__name__,
            method_name="bulk_create",
            request_body=request.data,
            request_path=request.get_full_path(),
            request_method=request.method,
            view_response=view_response,
        )
        return view_response.rest_response


class LocaleViewSet(ModelViewSet):
    permission_classes = [EditorAndUpOrReadOnly]
    serializer_class = LocaleSerializer
    queryset = Locale.objects.all()
    lookup_field = "id"

    def retrieve(self, request, *args, **kwargs):
        response = super().retrieve(request, *args, **kwargs)
        view_response = ViewResponse(
            response_body=response.data,
            response_status=response.status_code,
            is_successful=True,
            response_information_code=MessageCode.RETRIEVE_CONTENT_SUCCESS,
        )
        return view_response.rest_response

    def list(self, request, *args, **kwargs):
        response = super().list(request, *args, **kwargs)
        view_response = ViewResponse(
            response_body=response.data,
            response_status=response.status_code,
            is_successful=True,
            response_information_code=MessageCode.LIST_CONTENT_SUCCESS,
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
            response_information_code=MessageCode.LIST_CONTENT_SUCCESS,
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
            view_response = ViewResponseNoContent(_("Deleted successfully!"))
        except Http404:
            view_response = ViewResponseNoContent(_("Deleted successfully!"))
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
