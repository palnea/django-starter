from rest_framework import permissions
from rest_framework.permissions import SAFE_METHODS, DjangoModelPermissions

from common.middlewares.global_context_middleware import (
    GlobalContextMiddleware,
)


def get_action_permission_name(view_class, action, app_label=None):
    """
    Centralized function to generate consistent action permission names.

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
    """
    Short-circuiting OR operator for permissions that stops evaluation
    once the first permission passes, preventing unwanted side effects.

    Usage:
        permission_classes = [ShortCircuitOr(DjangoModelPermissionsWithView, IsOwnerWithoutSideEffects)]
    """

    def __init__(self, *permissions):
        self.permissions = permissions

    def __call__(self):
        return ShortCircuitOrPermission(self.permissions)


class ShortCircuitOrPermission(permissions.BasePermission):
    """
    Permission class that implements short-circuiting OR logic.
    Difference between using ShortCircuitOr and | in permissions is:
    - ShortCircuitOr will stop evaluating permissions once the first one passes
    - | will evaluate all permissions and return True if any pass

    Example:
        permission_classes = [ShortCircuitOr(DjangoModelPermissionsWithView, IsOwnerWithoutSideEffects)] // Won't evaluate IsOwnerWithoutSideEffects if DjangoModelPermissionsWithView passes
        permission_classes = [DjangoModelPermissionsWithView | IsOwnerWithoutSideEffects] // Will evaluate both permissions and return True if any pass
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
    """
    Applies different permissions based on conditions.

    Usage:
        permission_classes = [ConditionalPermission({
            lambda r, v: r.user.has_perm('user.view_user'): DjangoModelPermissionsWithView,
            lambda r, v: True: IsOwnerWithoutSideEffects  # Default case
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
    """
    Enhanced action-based permission check that uses actual DRF action names.

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
    """
    Enhanced Django model permissions that handles custom actions separately.

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
        """
        Override to handle custom actions vs standard CRUD operations.
        """
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
        """
        For object-level permissions:
        - If user has model-level permissions, grant access (like admins)
        - If user doesn't have model-level permissions, defer to ownership checks
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


class IsOwnerWithoutSideEffects(permissions.BasePermission):
    """
    Pure ownership permission without side effects - designed for composition.

    This version:
    - Does NOT auto-filter querysets (no side effects)
    - Does NOT auto-inject user_id (no side effects)
    - Only checks ownership at object level
    - Perfect for use in OR conditions with other permissions

    Use this when you want ownership checks but need to compose with other permissions.
    """

    def has_permission(self, request, view):
        return request.user.is_authenticated

    def has_object_permission(self, request, view, obj):
        # Special case: For User model, check id instead of user_id
        if obj.__class__.__name__ == "User":
            return str(obj.id) == str(request.user.id)

        if not hasattr(obj, "user_id"):
            return False
        return str(obj.user_id) == str(request.user.id)


class IsReadonly(permissions.BasePermission):
    """
    Global permission check for read-only access
    Allows only safe HTTP methods
    """

    def has_permission(self, request, view):
        return request.method in SAFE_METHODS
