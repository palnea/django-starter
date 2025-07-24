from django.http import Http404
from django.utils.translation import gettext_lazy as _
from rest_framework import status
from rest_framework.viewsets import ModelViewSet
from structlog import get_logger

from common.pagination import CustomPageNumberPagination
from common.permissions.generic_permissions import (
    DjangoModelPermissionsWithView,
    IsOwnerWithoutSideEffects,
    ShortCircuitOr,
)
from common.view_mixins import OwnershipMixin
from common.response.response_information_codes.message_code import MessageCode
from common.response.view_response import (
    log_view_response,
    ViewResponse,
    ViewResponseNoContent,
)
from user.models import User
from user.serializers import (
    UserPartialUpdateSerializer,
    UserSerializer,
)
from user.services import (
    UserService,
)

log = get_logger(__name__)


# Create your views here.
class UserViewSet(OwnershipMixin, ModelViewSet):
    """
    ViewSet for User model with Django model permissions and ownership checks.
    
    Permissions:
    - DjangoModelPermissionsWithView: Standard Django model permissions for admins
    - IsOwnerWithoutSideEffects: Ownership checks for regular users
    - ShortCircuitOr: Combines permissions without side effects
    
    Mixins:
    - OwnershipMixin: Handles queryset filtering and user_id injection explicitly in views
    
    Permission Flow:
    - Users with model-level permissions (add_user, change_user, delete_user, view_user) can access all user data
    - Users without model-level permissions can only access their own user data  
    - user_id is automatically injected for users without broad permissions (via mixin)
    - Follows Django best practices by checking actual permissions, not user roles
    
    This means:
    - Admins with appropriate permissions can perform any action on any user
    - Regular users can only read/modify their own user data
    - No role-based checks - everything is permission-based
    - All side effects are handled explicitly in view layer (not hidden in permissions)
    """
    permission_classes = [ShortCircuitOr(DjangoModelPermissionsWithView, IsOwnerWithoutSideEffects)]
    pagination_class = CustomPageNumberPagination
    queryset = User.objects.all()
    lookup_url_kwarg = "user_id"
    lookup_field = "id"

    def get_serializer_class(self):
        if self.action == "partial_update":
            return UserPartialUpdateSerializer
        return UserSerializer

    def get_queryset(self):
        # Start with ownership-filtered queryset from mixin
        queryset = super().get_queryset()
        
        # Apply additional custom filtering based on query parameters
        query_params = self.request.query_params
        created_from = query_params.get("created_from")
        created_to = query_params.get("created_to")
        reference_code = query_params.get("reference_code", None)
        reference_codes = reference_code and reference_code.split(",")
        order_by = query_params.get("order_by")

        if created_from:
            queryset = queryset.filter(created__gte=created_from)

        if created_to:
            queryset = queryset.filter(created__lte=created_to)

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
