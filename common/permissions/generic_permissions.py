from rest_framework import permissions
from rest_framework.permissions import SAFE_METHODS, DjangoModelPermissions
from functools import wraps
from rest_framework.response import Response
from rest_framework import status

from common.middlewares.global_context_middleware import (
    GlobalContextMiddleware,
)


def get_action_permission_name(view_class, action, app_label=None):
    """Centralized function to generate consistent action permission names.

    Args:
        view_class: The ViewSet class (e.g., UserViewSet)
        action: The action name (e.g., 'reset_password')
        app_label: Optional app label (e.g., 'user')

    Returns:
        tuple: (codename, full_permission_name)

    Examples:
        get_action_permission_name(UserViewSet, 'reset_password', 'user')
        # Returns: ('user_reset_password', 'user.user_reset_password')
    """
    view_name = view_class.__name__.replace("ViewSet", "").lower()
    codename = f"{view_name}_{action}"

    if app_label:
        full_permission_name = f"{app_label}.{codename}"
    else:
        full_permission_name = codename

    return codename, full_permission_name


class ShortCircuitOr:
    """Short-circuiting OR operator for permissions that stops evaluation once the first permission passes, preventing
    unwanted side effects.

    Examples:
        permission_classes = [ShortCircuitOr(ActionAwareModelPermissions, IsOwner)]
    """

    def __init__(self, *permissions):
        self.permissions = permissions

    def __call__(self):
        return ShortCircuitOrPermission(self.permissions)


class ShortCircuitOrPermission(permissions.BasePermission):
    """Permission class that implements short-circuiting OR logic. Difference between using ShortCircuitOr and | in
    permissions is: - ShortCircuitOr will stop evaluating permissions once the first one passes - | will evaluate
    all permissions and return True if any pass.

    Examples:
        permission_classes = [ShortCircuitOr(ActionAwareModelPermissions, IsOwner)] // Won't evaluate IsOwner if ActionAwareModelPermissions passes
        permission_classes = [ActionAwareModelPermissions | IsOwner] // Will evaluate both permissions and return True if any pass
    """

    def __init__(self, permission_classes):
        self.permission_classes = permission_classes
        self.permission_instances = [perm() for perm in permission_classes]

    def has_permission(self, request, view):
        for perm in self.permission_instances:
            if perm.has_permission(request, view):
                return True  # Short-circuit: stop here, no more permissions evaluated
        return False

    def has_object_permission(self, request, view, obj):
        for perm in self.permission_instances:
            if hasattr(perm, "has_object_permission"):
                if perm.has_object_permission(request, view, obj):
                    return True
        return False


class ConditionalPermission(permissions.BasePermission):
    """Applies different permissions based on conditions.

    Examples:
        permission_classes = [ConditionalPermission({
            lambda r, v: r.user.has_perm('user.view_user'): ActionAwareModelPermissions,
            lambda r, v: True: IsOwner  # Default case
        })]
    """

    def __init__(self, condition_map):
        self.condition_map = condition_map

    def _get_active_permission(self, request, view):
        for condition, permission_class in self.condition_map.items():
            if condition(request, view):
                return permission_class()
        return None

    def has_permission(self, request, view):
        perm = self._get_active_permission(request, view)
        return perm.has_permission(request, view) if perm else False

    def has_object_permission(self, request, view, obj):
        perm = self._get_active_permission(request, view)
        if perm and hasattr(perm, "has_object_permission"):
            return perm.has_object_permission(request, view, obj)
        return False


class IsActionPermissionGranted(permissions.BasePermission):
    """Enhanced action-based permission check that uses actual DRF action names.

    Permission format: {app_label}.{view_name}_{action}

    Examples:
    - user.user_reset_password (for reset_password action)
    - user.user_promote_to_admin (for promote_to_admin action)
    - user.user_list (for list action)
    - user.user_create (for create action)

    This provides granular control over each action rather than HTTP method-based permissions.
    """

    def has_permission(self, request, view):
        if not request.user.is_authenticated:
            return False

        # Get the actual DRF action (more specific than HTTP method)
        action = getattr(view, "action", None)
        if not action:
            return False

        app_label = getattr(view.queryset.model._meta, "app_label", None)

        # Use centralized permission naming function
        codename, permission_name = get_action_permission_name(
            view.__class__, action, app_label
        )

        user_all_permissions = (
            GlobalContextMiddleware.get_global_context().user_all_permissions
        )
        return permission_name in user_all_permissions


class ActionAwareModelPermissions(DjangoModelPermissions):
    """Enhanced Django model permissions that handles custom actions separately.

    Standard CRUD operations use Django model permissions:
    - list/retrieve -> view_model
    - create -> add_model
    - update/partial_update -> change_model
    - destroy -> delete_model

    Custom actions require explicit permissions:
    - reset_password -> app_label.viewname_reset_password
    - promote_to_admin -> app_label.viewname_promote_to_admin

    This prevents security issues where custom actions inherit inappropriate permissions.
    """

    # Standard CRUD action mapping
    perms_map = {
        "GET": ["%(app_label)s.view_%(model_name)s"],
        "OPTIONS": [],
        "HEAD": [],
        "POST": ["%(app_label)s.add_%(model_name)s"],
        "PUT": ["%(app_label)s.change_%(model_name)s"],
        "PATCH": ["%(app_label)s.change_%(model_name)s"],
        "DELETE": ["%(app_label)s.delete_%(model_name)s"],
    }

    # Standard DRF actions that should use model permissions
    standard_actions = {
        "list",
        "create",
        "retrieve",
        "update",
        "partial_update",
        "destroy",
    }

    def get_required_permissions(self, method, model_cls):
        """Override to handle custom actions vs standard CRUD operations."""
        # Get the current action from the view
        action = getattr(self.view, "action", None)

        # If it's a standard CRUD action, use the parent's logic
        if action in self.standard_actions:
            return super().get_required_permissions(method, model_cls)

        # For custom actions, create action-specific permission
        if action:
            app_label = model_cls._meta.app_label
            codename, action_permission = get_action_permission_name(
                self.view.__class__, action, app_label
            )
            return [action_permission]

        # Fallback to parent behavior
        return super().get_required_permissions(method, model_cls)

    def has_permission(self, request, view):
        # Store view reference for get_required_permissions
        self.view = view
        return super().has_permission(request, view)

    def has_object_permission(self, request, view, obj):
        """For object-level permissions: - If user has model-level permissions, grant access (like admins) - If user
        doesn't have model-level permissions, defer to ownership checks.
        """
        # Store view reference needed for get_required_permissions
        self.view = view

        # Check if user has the required model-level permission for this action
        queryset = self._queryset(view)
        model_cls = queryset.model
        perms = self.get_required_permissions(request.method, model_cls)

        # If user has the required model permission, grant object access
        if request.user.has_perms(perms):
            return True

        # Otherwise, defer to ownership checks
        return False


class IsOwner(permissions.BasePermission):
    """Enhanced ownership permission that detects attempts to access other users' data.

    This version:
    - Checks for ownership field in query parameters (for list operations)
    - Prevents users from listing/filtering other users' data
    - Prevents users from creating objects on behalf of others
    - Checks ownership at object level for retrieve/update/delete operations
    - Perfect for use in OR conditions with other permissions

    Behavior:
    1. User cannot change, retrieve, delete or list someone else's objects
    2. User cannot create objects on behalf of someone else
    """

    def has_permission(self, request, view):
        if not request.user.is_authenticated:
            return False

        # Check if this is a list operation with ownership filtering attempts
        action = getattr(view, "action", None)
        if action == "list":
            return self._check_list_ownership_attempt(request, view)

        # Check if this is a create operation with user_id injection attempt
        if action == "create":
            return self._check_create_ownership_attempt(request, view)

        return True  # For other operations, rely on object-level permissions

    def has_object_permission(self, request, view, obj):
        # Staff and superusers bypass ownership checks.
        # This is important when IsOwner is composed with ShortCircuitOr:
        # an admin may pass has_permission via ActionAwareModelPermissions,
        # but ShortCircuitOrPermission.has_object_permission evaluates all
        # permission classes independently. Without this bypass, an admin
        # who lacks a specific model-level permission would be blocked here
        # even though they passed has_permission through a different class.
        if request.user.is_staff or request.user.is_superuser:
            return True

        # Special case: For User model, check id instead of user_id
        if obj.__class__.__name__ == "User":
            return str(obj.id) == str(request.user.id)

        if not hasattr(obj, "user_id"):
            return False
        return str(obj.user_id) == str(request.user.id)

    def _check_list_ownership_attempt(self, request, view):
        """Check if user is attempting to list/filter other users' data."""
        # Get the ownership field (default or from query params)
        ownership_field = getattr(view, "ownership_field", "user_id")
        query_ownership_field = request.query_params.get(
            "ownership_field", ownership_field
        )

        # Check if user is trying to filter by a specific ownership value
        ownership_filter = request.query_params.get(query_ownership_field, None)

        if ownership_filter is not None:
            # User is trying to filter by specific ownership value
            current_user_id = str(request.user.id)
            if ownership_filter != current_user_id:
                # Attempting to access someone else's data
                return False

        # Check for other potential ownership-related parameters
        for param_name in request.query_params:
            if "user_id" in param_name.lower() or param_name.lower() in [
                "user",
                "owner",
                "created_by",
            ]:
                param_value = request.query_params.get(param_name)
                if param_value and str(param_value) != str(request.user.id):
                    return False

        return True

    def _check_create_ownership_attempt(self, request, view):
        """Check if user is attempting to create objects on behalf of others."""
        # Check if user_id or similar fields are in the request data
        user_id_field = getattr(view, "user_id_field", "user_id")

        # Check request data for user_id injection attempts
        if hasattr(request, "data") and request.data:
            data = request.data

            # Check the primary user_id field
            if user_id_field in data:
                provided_user_id = str(data[user_id_field])
                if provided_user_id != str(request.user.id):
                    return False

            # Check for other common user identification fields
            user_fields = [
                "user_id",
                "user",
                "owner_id",
                "owner",
                "created_by",
                "author_id",
                "author",
            ]
            for field in user_fields:
                if field in data:
                    provided_value = str(data[field])
                    if provided_value != str(request.user.id):
                        return False

        return True


class IsReadonly(permissions.BasePermission):
    """Global permission check for read-only access Allows only safe HTTP methods."""

    def has_permission(self, request, view):
        return request.method in SAFE_METHODS


def check_ownership(
    ownership_field="user_id",
    allow_admin=True,
    check_query_params=True,
    check_request_data=True,
):
    """Decorator to check ownership for custom actions.

    Args:
        ownership_field (str): Field name to check for ownership (default: 'user_id')
        allow_admin (bool): Whether to allow users with model permissions to bypass ownership checks
        check_query_params (bool): Whether to check query parameters for ownership attempts
        check_request_data (bool): Whether to check request data for ownership attempts

    Examples:
        @action(detail=True, methods=['post'])
        @check_ownership()
        def reset_password(self, request, pk=None):
            # Only the owner can reset their own password
            user = self.get_object()
            # ... action logic

        @action(detail=False, methods=['get'])
        @check_ownership(ownership_field='author_id', check_request_data=False)
        def my_posts(self, request):
            # Custom list action with ownership filtering
            # ... action logic
    """

    def decorator(action_func):
        @wraps(action_func)
        def wrapper(self, request, *args, **kwargs):
            if not request.user.is_authenticated:
                return Response(
                    {"detail": "Authentication required."},
                    status=status.HTTP_401_UNAUTHORIZED,
                )

            # Check if user has admin permissions and admin access is allowed
            if allow_admin:
                model = getattr(self, "queryset", None)
                if model is not None:
                    model_class = model.model
                    app_label = model_class._meta.app_label
                    model_name = model_class._meta.model_name
                    view_permission = f"{app_label}.view_{model_name}"

                    if request.user.has_perm(view_permission):
                        # User has admin permissions, allow action
                        return action_func(self, request, *args, **kwargs)

            # Perform ownership checks
            ownership_violation = _check_action_ownership(
                request, self, ownership_field, check_query_params, check_request_data
            )

            if ownership_violation:
                return Response(
                    {
                        "detail": f"You don't have permission to perform this action. {ownership_violation}"
                    },
                    status=status.HTTP_403_FORBIDDEN,
                )

            # If this is a detail action, check object-level ownership
            if kwargs.get("pk") is not None:
                try:
                    obj = self.get_object()
                    if not _check_object_ownership(request.user, obj, ownership_field):
                        return Response(
                            {
                                "detail": "You don't have permission to perform this action on this object."
                            },
                            status=status.HTTP_403_FORBIDDEN,
                        )
                except Exception:
                    # If object doesn't exist, let the action handle it
                    pass

            return action_func(self, request, *args, **kwargs)

        return wrapper

    return decorator


def _check_action_ownership(
    request, view, ownership_field, check_query_params, check_request_data
):
    """Helper function to check ownership violations in custom actions. Returns a string describing the violation, or
    None if no violation.
    """
    current_user_id = str(request.user.id)

    # Check query parameters for ownership attempts
    if check_query_params:
        # Check the specific ownership field
        if ownership_field in request.query_params:
            param_value = request.query_params.get(ownership_field)
            if param_value and str(param_value) != current_user_id:
                return f"Cannot filter by {ownership_field}={param_value} - you can only access your own data."

        # Check other common ownership parameters
        ownership_params = [
            "user_id",
            "user",
            "owner_id",
            "owner",
            "created_by",
            "author_id",
            "author",
        ]
        for param_name in request.query_params:
            if param_name.lower() in ownership_params or any(
                op in param_name.lower() for op in ["user_id", "owner"]
            ):
                param_value = request.query_params.get(param_name)
                if param_value and str(param_value) != current_user_id:
                    return f"Cannot filter by {param_name}={param_value} - you can only access your own data."

    # Check request data for ownership attempts
    if check_request_data and hasattr(request, "data") and request.data:
        data = request.data

        # Check the specific ownership field
        if ownership_field in data:
            provided_value = str(data[ownership_field])
            if provided_value != current_user_id:
                return f"Cannot set {ownership_field}={provided_value} - you can only create/modify your own data."

        # Check other common ownership fields
        ownership_fields = [
            "user_id",
            "user",
            "owner_id",
            "owner",
            "created_by",
            "author_id",
            "author",
        ]
        for field in ownership_fields:
            if field in data:
                provided_value = str(data[field])
                if provided_value != current_user_id:
                    return f"Cannot set {field}={provided_value} - you can only create/modify your own data."

    return None


def _check_object_ownership(user, obj, ownership_field):
    """Helper function to check if user owns the object."""
    # Special case: For User model, check id instead of user_id
    if obj.__class__.__name__ == "User":
        return str(obj.id) == str(user.id)

    # Check the specified ownership field
    if hasattr(obj, ownership_field):
        return str(getattr(obj, ownership_field)) == str(user.id)

    return False


def require_ownership(ownership_field="user_id", allow_admin=True):
    """Simple decorator for actions that require object ownership. Only works with detail actions (actions that have pk
    parameter).

    Args:
        ownership_field (str): Field name to check for ownership
        allow_admin (bool): Whether to allow users with model permissions

    Examples:
        @action(detail=True, methods=['post'])
        @require_ownership()
        def activate(self, request, pk=None):
            # Only the owner can activate their object
            obj = self.get_object()
            # ... action logic
    """

    def decorator(action_func):
        @wraps(action_func)
        def wrapper(self, request, *args, **kwargs):
            if not request.user.is_authenticated:
                return Response(
                    {"detail": "Authentication required."},
                    status=status.HTTP_401_UNAUTHORIZED,
                )

            # Check if user has admin permissions
            if allow_admin:
                model = getattr(self, "queryset", None)
                if model is not None:
                    model_class = model.model
                    app_label = model_class._meta.app_label
                    model_name = model_class._meta.model_name
                    view_permission = f"{app_label}.view_{model_name}"

                    if request.user.has_perm(view_permission):
                        return action_func(self, request, *args, **kwargs)

            # Check object ownership
            if kwargs.get("pk") is not None:
                try:
                    obj = self.get_object()
                    if not _check_object_ownership(request.user, obj, ownership_field):
                        return Response(
                            {
                                "detail": "You don't have permission to perform this action on this object."
                            },
                            status=status.HTTP_403_FORBIDDEN,
                        )
                except Exception:
                    return Response(
                        {"detail": "Object not found."},
                        status=status.HTTP_404_NOT_FOUND,
                    )
            else:
                return Response(
                    {"detail": "This action requires an object ID."},
                    status=status.HTTP_400_BAD_REQUEST,
                )

            return action_func(self, request, *args, **kwargs)

        return wrapper

    return decorator
