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
        permission_classes = [ShortCircuitOr(DjangoModelPermissionsWithView, IsOwner)]
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
        permission_classes = [ShortCircuitOr(DjangoModelPermissionsWithView, IsOwner)] // Won't evaluate IsOwner if DjangoModelPermissionsWithView passes
        permission_classes = [DjangoModelPermissionsWithView | IsOwner] // Will evaluate both permissions and return True if any pass
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


class DjangoModelPermissionsWithOwnership(DjangoModelPermissions):
    """
    Enhanced DjangoModelPermissions that:
    1. Uses Django's standard model permissions (add_model, change_model, delete_model, view_model)
    2. Adds object-level ownership checks for users without broad permissions
    3. Automatically injects user_id for users who don't have broad permissions
    4. Follows Django best practices by checking actual permissions, not user roles
    
    Permission Flow:
    - Users with model-level permissions can access all objects
    - Users without model-level permissions can only access their own objects
    - user_id is auto-injected for users without broad permissions
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
    
    def _get_required_permission(self, request, view):
        """Get the required permission for this request"""
        if not hasattr(view, 'queryset') or view.queryset is None:
            return None
            
        model = view.queryset.model
        app_label = model._meta.app_label
        model_name = model._meta.model_name
        
        perms = self.get_required_permissions(request.method, model)
        if perms:
            return perms[0]  # Return first required permission
        return None
    
    def _user_has_model_permission(self, request, view):
        """Check if user has the broad model-level permission"""
        required_perm = self._get_required_permission(request, view)
        if not required_perm:
            return False
        return request.user.has_perm(required_perm)
    
    def _inject_user_id_if_needed(self, request, view):
        """Auto-inject user_id for users without broad permissions"""
        if not request.user.is_authenticated:
            return
            
        # Skip injection if user has broad model permissions
        if self._user_has_model_permission(request, view):
            return
            
        # Only inject for write operations
        if request.method not in ['POST', 'PUT', 'PATCH']:
            return
            
        user_id_in_url = request.parser_context.get("kwargs", {}).get("user_id")
        user_id_in_query = request.query_params.get("user_id")
        user_id_in_data = request.data.get("user_id") if hasattr(request, 'data') else None
        
        # If no user_id is specified anywhere, inject current user's ID
        if not any([user_id_in_url, user_id_in_query, user_id_in_data]):
            if hasattr(request, '_full_data'):
                request._full_data['user_id'] = str(request.user.id)
            elif hasattr(request, 'data') and hasattr(request.data, '_mutable'):
                was_mutable = request.data._mutable
                request.data._mutable = True
                request.data['user_id'] = str(request.user.id)
                request.data._mutable = was_mutable

    def has_permission(self, request, view):
        if not request.user.is_authenticated:
            return False
            
        # Auto-inject user_id if needed
        self._inject_user_id_if_needed(request, view)
        
        # If user has broad model permission, allow access
        if self._user_has_model_permission(request, view):
            return True
            
        # For users without broad permissions, they can only access their own data
        # This will be further validated in has_object_permission
        return True
    
    def has_object_permission(self, request, view, obj):
        # If user has broad model permission, allow access
        if self._user_has_model_permission(request, view):
            return True
            
        # For users without broad permissions, check ownership
        if not hasattr(obj, 'user_id'):
            return False
            
        return str(obj.user_id) == str(request.user.id)


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
        if not hasattr(obj, 'user_id'):
            return False
        return str(obj.user_id) == str(request.user.id)


class IsOwner(permissions.BasePermission):
    """
    Comprehensive ownership permission that:
    1. Allows users to only see their own entities (list and detail)
    2. Allows users to only create, update, delete their own entities
    3. Auto-injects user_id for create operations when not specified
    4. Uses hybrid approach: auto-filtering for lists, explicit errors for detail access
    5. Does NOT require client to send user_id for retrieve operations
    
    Security Design:
    - LIST operations: Auto-filter to user's objects (better UX, secure)
    - DETAIL operations: Explicit permission check (clear feedback)
    
    IMPORTANT: This permission automatically filters querysets for list operations.
    If you need custom queryset logic, override get_queryset() in your ViewSet.
    
    Usage:
    - Apply this permission to ViewSet
    - Permission automatically handles queryset filtering for list operations
    - Object-level checks provide explicit errors for unauthorized detail access
    
    Works for all operations:
    - LIST: Automatically filters queryset to user's objects (no errors)
    - RETRIEVE: Explicit permission check (403 if not owner)
    - CREATE: Auto-inject user_id if not specified
    - UPDATE/DELETE: Explicit permission check (403 if not owner)
    """

    def has_permission(self, request, view):
        """
        View-level permission check.
        
        For ownership-based permissions, we allow authenticated requests
        and handle filtering/ownership at the queryset and object level.
        """
        if not request.user.is_authenticated:
            return False
            
        # Auto-inject user_id for create operations when not specified
        if request.method == 'POST':
            self._inject_user_id_for_create(request)
        
        # For list views, apply automatic filtering (better UX)
        if self._is_list_operation(request, view):
            self._ensure_queryset_filtering(request, view)
            
        return True
    
    def has_object_permission(self, request, view, obj):
        """
        Object-level permission check.
        
        Provides explicit permission errors for detail operations.
        This gives clear feedback when users try to access specific objects they don't own.
        """
        # Object must have a user_id attribute for ownership check
        if not hasattr(obj, 'user_id'):
            return False
            
        # Check ownership - returns explicit 403 if not owner
        return str(obj.user_id) == str(request.user.id)
    
    def _is_list_operation(self, request, view):
        """
        Determine if this is a list operation vs detail operation.
        
        List operations should be filtered automatically for better UX.
        Detail operations should return explicit errors for clarity.
        """
        # GET requests without specific object lookup are list operations
        if request.method == 'GET':
            # Check if there's a specific object being requested
            lookup_url_kwarg = getattr(view, 'lookup_url_kwarg', None) or getattr(view, 'lookup_field', 'pk')
            lookup_value = view.kwargs.get(lookup_url_kwarg)
            return lookup_value is None
        
        return False
    
    def _inject_user_id_for_create(self, request):
        """
        Auto-inject user_id for create operations when not specified.
        This ensures users create entities for themselves.
        """
        if not hasattr(request, 'data'):
            return
            
        # Check if user_id is already specified in the data
        if request.data.get('user_id'):
            # If user_id is specified, ensure it matches the current user
            specified_user_id = str(request.data.get('user_id'))
            if specified_user_id != str(request.user.id):
                # For regular users, override with their own ID
                if hasattr(request.data, '_mutable'):
                    was_mutable = request.data._mutable
                    request.data._mutable = True
                    request.data['user_id'] = str(request.user.id)
                    request.data._mutable = was_mutable
                elif hasattr(request, '_full_data'):
                    request._full_data['user_id'] = str(request.user.id)
        else:
            # Auto-inject user_id if not specified
            if hasattr(request.data, '_mutable'):
                was_mutable = request.data._mutable
                request.data._mutable = True
                request.data['user_id'] = str(request.user.id)
                request.data._mutable = was_mutable
            elif hasattr(request, '_full_data'):
                request._full_data['user_id'] = str(request.user.id)
    
    def _ensure_queryset_filtering(self, request, view):
        """
        Ensure that the queryset is filtered by user ownership for list views.
        
        This provides better UX by showing users their content without errors,
        while maintaining security by preventing access to others' content.
        """
        # Mark that we've checked the filtering
        request._queryset_filtered_by_isowner = True
        
        # Check if the view has a queryset that can be filtered
        if not hasattr(view, 'queryset') or view.queryset is None:
            return
            
        # Check if the model has user_id field
        model = view.queryset.model
        if not hasattr(model, 'user_id'):
            import warnings
            warnings.warn(
                f"IsOwner permission applied to {view.__class__.__name__} but "
                f"{model.__name__} model doesn't have 'user_id' field. "
                f"This may allow users to see all objects.",
                UserWarning
            )
            return
        
        # Check if get_queryset is overridden (developer has custom filtering)
        has_custom_get_queryset = (
            hasattr(view, 'get_queryset') and 
            view.__class__.get_queryset != view.__class__.__bases__[0].get_queryset
        )
        
        if not has_custom_get_queryset:
            # No custom queryset filtering - apply automatic filtering
            import warnings
            warnings.warn(
                f"IsOwner permission on {view.__class__.__name__} is automatically "
                f"filtering queryset by user_id for list operations. Override get_queryset() for custom logic.",
                UserWarning
            )
            
            # Apply automatic filtering by monkey-patching the get_queryset method
            original_get_queryset = view.get_queryset
            
            def filtered_get_queryset():
                base_queryset = original_get_queryset()
                return base_queryset.filter(user_id=request.user.id)
            
            view.get_queryset = filtered_get_queryset


class IsReadonly(permissions.BasePermission):
    """
    Global permission check for read-only access
    Allows only safe HTTP methods
    """

    def has_permission(self, request, view):
        return request.method in SAFE_METHODS
