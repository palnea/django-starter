from django.http import Http404
from django.utils.translation import gettext_lazy as _
from rest_framework import status
from rest_framework.viewsets import GenericViewSet, ModelViewSet
from structlog import get_logger

from common.middlewares.global_context_middleware import GlobalContextMiddleware
from common.models import Translation
from common.pagination import CustomPageNumberPagination
from common.permissions.generic_permissions import (
    EditorAndUpOrReadOnly,
)
from common.response.response_information_codes.message_code import MessageCode
from common.response.view_response import (
    log_view_response,
    ViewResponse,
    ViewResponseNoContent,
)
from user.models import User, School, Class, Avatar
from user.permissions import UserViewSetPermission
from user.serializers import (
    AvatarSerializer,
    UserPartialUpdateSerializer,
    UserSerializer,
    SchoolSerializer,
    ClassSerializer,
    SchoolRetrieveSerializer,
)
from user.services import (
    AvatarService,
    UserService,
)

log = get_logger(__name__)


# Create your views here.
class UserViewSet(ModelViewSet):
    permission_classes = [UserViewSetPermission]
    pagination_class = CustomPageNumberPagination
    queryset = User.objects.all().select_related("school")
    lookup_url_kwarg = "user_id"
    lookup_field = "id"

    def get_serializer_class(self):
        if self.action == "partial_update":
            return UserPartialUpdateSerializer
        return UserSerializer

    def get_queryset(self):
        query_params = self.request.query_params
        created_from = query_params.get("created_from")
        created_to = query_params.get("created_to")
        school_id = query_params.get("school_id", None)
        school_ids = school_id and school_id.split(",")
        reference_code = query_params.get("reference_code", None)
        reference_codes = reference_code and reference_code.split(",")
        order_by = query_params.get("order_by")

        queryset = User.objects.all().select_related("school")

        if created_from:
            queryset = queryset.filter(created__gte=created_from)

        if created_to:
            queryset = queryset.filter(created__lte=created_to)

        if school_ids:
            queryset = queryset.filter(school_id__in=school_ids)

        if reference_codes:
            queryset = queryset.filter(reference_codes__code__in=reference_codes)

        if order_by:
            queryset = queryset.order_by(order_by)
        else:
            queryset = queryset.order_by("-created")

        return queryset

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

    def partial_update(self, request, *args, **kwargs):
        status_code = status.HTTP_200_OK
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data

        user = UserService.update_user(data, True)

        view_response = ViewResponse(
            response_body=user,
            response_status=status_code,
            is_successful=True,
            response_information_code=MessageCode.UPDATE_CONTENT_SUCCESS,
            response_message=_("Updated successfully!"),
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


class AvatarViewSet(GenericViewSet):
    permission_classes = [EditorAndUpOrReadOnly]
    serializer_class = AvatarSerializer
    queryset = Avatar.objects.all()

    def create(self, request, *args, **kwargs):
        status_code = status.HTTP_201_CREATED
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        avatar = AvatarService.create_avatar(serializer.validated_data)
        view_response = ViewResponse(
            response_body=avatar,
            response_status=status_code,
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

    def list(self, request, *args, **kwargs):
        status_code = status.HTTP_200_OK
        avatars = AvatarService.list_avatars()
        view_response = ViewResponse(
            response_body=avatars,
            response_status=status_code,
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


class SchoolViewSet(ModelViewSet):
    permission_classes = [EditorAndUpOrReadOnly]
    queryset = School.objects.all()
    lookup_field = "id"

    def get_serializer_class(self):
        if self.action == "retrieve":
            return SchoolRetrieveSerializer
        return SchoolSerializer

    def get_queryset(self):
        queryset = School.objects.all()
        language_code = GlobalContextMiddleware.get_global_context().language_code

        return queryset.prefetch_related(
            Translation.create_prefetch_for_language(
                language_code, "name__translations", to_attr="translated_name"
            )
        )

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


class ClassViewSet(ModelViewSet):
    permission_classes = [EditorAndUpOrReadOnly]
    serializer_class = ClassSerializer
    queryset = Class.objects.all()
    lookup_field = "id"

    def get_queryset(self):
        request = self.request
        params = request.query_params
        school_id = params.get("school_id", None)

        query_set = Class.objects.all()

        if school_id:
            query_set = query_set.filter(school_id=school_id).select_related("school")

        return query_set

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
