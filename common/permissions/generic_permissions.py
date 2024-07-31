from django.contrib.auth.models import AnonymousUser
from rest_framework import permissions

from user.types import UserRole


class EditorAndUp(permissions.BasePermission):
    """
    Global permission check for editor and upper roles
    """

    def has_permission(self, request, view):
        auth = request.auth
        if auth:
            jwt_payload = auth.payload
            role = UserRole(jwt_payload.get("role", None) or UserRole.NONE.value)
            if role and role >= UserRole.EDITOR:
                return True
        return False


class EditorAndUpOrReadOnly(permissions.BasePermission):
    """
    Global permission check for free users
    Allows list for any user but limit access for paid content
    Write methods only allowed according to role
    """

    def has_permission(self, request, view):
        if request.method in ["GET"]:
            return True

        auth = request.auth
        if auth:
            jwt_payload = auth.payload
            role = UserRole(jwt_payload.get("role", None) or UserRole.NONE.value)
            if role and (
                role >= UserRole.EDITOR or view.action in ["list_with_progress"]
            ):
                return True

        return False


class IsAdmin(permissions.BasePermission):
    """
    Global permission check for admin operations
    Allows admin
    """

    def has_permission(self, request, view):
        auth = request.auth
        if auth:
            jwt_payload = auth.payload
            role = UserRole(jwt_payload.get("role", None) or UserRole.NONE.value)
            if role and role >= UserRole.ADMIN:
                return True
        return False


class AdminOrOwner(permissions.BasePermission):
    """
    Global permission check for admin or user owned operations
    Allows admin or object owner
    """

    def has_permission(self, request, view):
        auth = request.auth
        if auth:
            jwt_payload = auth.payload
            role = UserRole(jwt_payload.get("role", None) or UserRole.NONE.value)
            if role and role >= UserRole.ADMIN:
                return True

            account = request.user
            user = None
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


class AdminOrOwnerOrReadonly(permissions.BasePermission):
    """
    Global permission check for admin or user owned operations
    Allows admin or object owner
    """

    def has_permission(self, request, view):
        if request.method in ["GET"]:
            return True

        auth = request.auth
        if auth:
            jwt_payload = auth.payload
            role = UserRole(jwt_payload.get("role", None) or UserRole.NONE.value)
            if role and role >= UserRole.ADMIN:
                return True

            account = request.user
            user = None
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


class EditorAndUpOrOwnerOrReadonly(permissions.BasePermission):
    """
    Global permission check for admin or user owned operations
    Allows admin or object owner
    """

    def has_permission(self, request, view):
        if request.method in ["GET"]:
            return True

        auth = request.auth
        if auth:
            jwt_payload = auth.payload
            role = UserRole(jwt_payload.get("role", None) or UserRole.NONE.value)
            if role and role >= UserRole.EDITOR:
                return True

            account = request.user
            user = None
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


class ContentPermission(permissions.BasePermission):
    """
    Global permission check for blocked IPs.
    """

    def has_permission(self, request, view):
        """
        AllowAny user if the request is for list and retrieve the events
        Allow authenticated users if request is list with progress
        Allow write operations only if the role is higher or equal to Editor level
        """
        if request.method in ["GET"]:
            return True

        auth = request.auth
        if auth:
            jwt_payload = auth.payload
            role = UserRole(jwt_payload.get("role", None) or UserRole.NONE.value)
            if role and (
                role >= UserRole.EDITOR or view.action in ["list_with_progress"]
            ):
                return True

        return False

    def has_object_permission(self, request, view, obj):
        """
        AllowAny if the object to retrieve is free or list operation is applied
        Allow subscribers if the object to retrieve is not free
        """
        if request.auth:
            jwt_payload = request.auth.payload
            role = UserRole(jwt_payload.get("role", None) or UserRole.NONE.value)
            if role and role >= UserRole.EDITOR:
                return True

        if (
            view.action == "retrieve"
            and not (hasattr(obj, "free") and obj.free)
            and (
                request.user is None
                or type(request.user) is AnonymousUser
                or not (
                    request.user.user.email_verified or request.user.user.phone_verified
                )
            )
        ):
            return False
        return True
