from rest_framework import permissions
from rest_framework.permissions import SAFE_METHODS, DjangoModelPermissions

from common.middlewares.global_context_middleware import (
    GlobalContextMiddleware,
)


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
            if hasattr(perm, 'has_object_permission'):
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
        if perm and hasattr(perm, 'has_object_permission'):
            return perm.has_object_permission(request, view, obj)
        return False


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
        permission_name = (
            f"{app_label}.{view_name}.{request.method.lower()}"
            if app_label
            else f"{view_name}.{request.method.lower()}"
        )
        user_all_permissions = (
            GlobalContextMiddleware.get_global_context().user_all_permissions
        )
        return permission_name in user_all_permissions


class DjangoModelPermissionsWithView(DjangoModelPermissions):
    """
    Standard DjangoModelPermissions with view permission for GET requests.
    This is for cases where you want standard Django permissions without ownership logic.
    """
    
    perms_map = {
        'GET': ['%(app_label)s.view_%(model_name)s'],
        'OPTIONS': [],
        'HEAD': [],
        'POST': ['%(app_label)s.add_%(model_name)s'],
        'PUT': ['%(app_label)s.change_%(model_name)s'],
        'PATCH': ['%(app_label)s.change_%(model_name)s'],
        'DELETE': ['%(app_label)s.delete_%(model_name)s'],
    }


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
        if obj.__class__.__name__ == 'User':
            return str(obj.id) == str(request.user.id)
        
        if not hasattr(obj, 'user_id'):
            return False
        return str(obj.user_id) == str(request.user.id)


class IsReadonly(permissions.BasePermission):
    """
    Global permission check for read-only access
    Allows only safe HTTP methods
    """

    def has_permission(self, request, view):
        return request.method in SAFE_METHODS
