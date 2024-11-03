from rest_framework import permissions
from rest_framework.permissions import SAFE_METHODS

from common.middlewares.global_context_middleware import GlobalContextMiddleware, GlobalContext
from django.apps import apps


class IsActionPermissionGranted(permissions.BasePermission):
    """
    Global permission check for granted operations
    Allows admin or user with granted permissions
    """

    def has_permission(self, request, view):
        if not request.user.is_authenticated:
            return False

        view_name = view.__class__.__name__.replace("ViewSet", "").lower()
        app_label = view.queryset.model._meta.app_label
        permission_name = f"{app_label}.{view_name}.{request.method.lower()}" if app_label else f"{view_name}.{request.method.lower()}"
        user_all_permissions = GlobalContextMiddleware.get_global_context().user_all_permissions
        return permission_name in user_all_permissions


class HasWritePermission(permissions.BasePermission):
    """
    Custom permission to allow read-only access to everyone and restrict write access
    to users with a specific permission.
    """

    def has_permission(self, request, view):
        # Attempt to determine app_label from queryset
        if hasattr(view, 'queryset') and view.queryset is not None:
            app_label = view.queryset.model._meta.app_label
        elif hasattr(view, 'serializer_class') and hasattr(view.serializer_class.Meta, 'model'):
            # Attempt to get app_label from serializer's Meta model
            app_label = view.serializer_class.Meta.model._meta.app_label
        else:
            # Use the module path to infer app_label if queryset and serializer are unavailable
            module = view.__module__.split('.')
            app_label = next(
                (app_config.label for app_config in apps.get_app_configs() if app_config.name == module[0]), None)

        if not app_label:
            raise ValueError("Unable to determine app_label for permission check.")

        # Construct the permission codename based on viewset naming convention
        view_name = view.__class__.__name__.replace("ViewSet", "").lower()
        required_permission = f"{app_label}.can_write_{view_name}"

        user_all_permissions = GlobalContextMiddleware.get_global_context().user_all_permissions
        return required_permission in user_all_permissions


class IsOwner(permissions.BasePermission):
    """
    Global permission check for admin or user owned operations
    Allows admin or object owner
    This permission can only be used for views with a model that has a user_id field/property
    """

    def has_permission(self, request, view):
        auth = request.auth
        if auth:
            account = request.user
            if not account:
                return False

            try:
                user = account.user
            except:
                return False

            if not user:
                return False
            user_id_to_filter = (
                    request.parser_context.get("kwargs", {}).get("user_id")
                    or request.query_params.get("user_id")
                    or request.data.get("user_id")
            )
            writing_own_component = user_id_to_filter is None and request.method in [
                "POST",
                "PUT",
                "PATCH",
                "OPTIONS",
                "DELETE",
            ]
            if str(user_id_to_filter) == str(user.id) or writing_own_component:
                return True
        return False

    def has_object_permission(self, request, view, obj):
        user_id = GlobalContextMiddleware.get_global_context().user_id
        obj_user_id = obj.user_id if hasattr(obj, "user_id") else None
        if obj_user_id and str(obj_user_id) == user_id:
            return True

        return False


class IsReadonly(permissions.BasePermission):
    """
    Global permission check for admin or user owned operations
    Allows admin or object owner
    """

    def has_permission(self, request, view):
        return request.method in SAFE_METHODS
