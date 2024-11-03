from rest_framework import permissions
from rest_framework.permissions import SAFE_METHODS

from common.middlewares.global_context_middleware import GlobalContextMiddleware


class IsAdmin(permissions.BasePermission):
    """
    Global permission check for admin operations
    Allows admin
    """

    def has_permission(self, request, view):
        access_token = request.auth
        if access_token:
            jwt_payload = access_token.payload
            groups = jwt_payload.get("groups", [])
            return "Admin" in groups
        return False


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
