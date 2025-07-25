from rest_framework.viewsets import ModelViewSet
from django.http import Http404
from rest_framework.generics import get_object_or_404


class OwnershipFilterMixin:
    """
    Mixin to handle ownership-based queryset filtering and object retrieval.
    
    Behavior:
    - List operations: Apply ownership filtering (users see only their own data)
    - Object operations (retrieve, update, delete): No filtering, rely on has_object_permission for 403 responses
    """
    
    ownership_field = 'user_id'  # Override in subclass if needed
    ownership_permission = None  # e.g., 'user.view_user' - set in subclass
    
    # Actions that should use object-level permission checks instead of queryset filtering
    object_level_actions = {'retrieve', 'update', 'partial_update', 'destroy'}
    
    def get_queryset(self):
        """
        Apply ownership filtering only for list operations.
        Object operations get unfiltered queryset and rely on has_object_permission.
        """
        queryset = super().get_queryset()
        
        # For object-level actions, return unfiltered queryset
        # This allows proper 403 responses instead of 404
        action = getattr(self, 'action', None)
        if action in self.object_level_actions:
            return queryset
        
        # For list actions, apply ownership filtering
        if self.ownership_permission is None:
            # Auto-determine permission from model
            model = queryset.model
            app_label = model._meta.app_label
            model_name = model._meta.model_name
            self.ownership_permission = f"{app_label}.view_{model_name}"
        
        # If user has broad permissions, return full queryset
        if self.request.user.has_perm(self.ownership_permission):
            return queryset
            
        # Otherwise filter by ownership for list operations
        # Special case: For User model, filter by id instead of user_id
        if queryset.model.__name__ == 'User' and self.ownership_field == 'user_id':
            filter_kwargs = {'id': self.request.user.id}
        else:
            filter_kwargs = {self.ownership_field: self.request.user.id}
        
        return queryset.filter(**filter_kwargs)

    def get_object(self):
        """
        For object-level operations, use standard DRF flow.
        This will find the object and then check permissions via has_object_permission.
        """
        # Use the standard DRF get_object implementation
        # This will find the object (or 404) and then check object permissions (or 403)
        return super().get_object()


class UserIDInjectionMixin:
    """
    Mixin to auto-inject user_id for create operations when users don't have broad permissions.
    
    This replaces the automatic injection that was previously done in permission classes.
    Now injection is explicit and visible in the view layer.
    """
    
    user_id_field = 'user_id'  # Override in subclass if needed
    
    def perform_create(self, serializer):
        """
        Auto-inject user_id for users without broad permissions.
        Users with model-level permissions can create for any user.
        """
        # Check if user needs user_id injection
        model = serializer.Meta.model
        app_label = model._meta.app_label
        model_name = model._meta.model_name
        add_permission = f"{app_label}.add_{model_name}"
        
        # If user has broad add permission, let them specify any user_id
        if self.request.user.has_perm(add_permission):
            serializer.save()
        else:
            # Special case: For User model, don't inject user_id since it doesn't have that field
            if model.__name__ == 'User' and self.user_id_field == 'user_id':
                # For User model, just save normally - each user creates their own User record
                serializer.save()
            else:
                # Otherwise, force user_id to current user
                save_kwargs = {self.user_id_field: self.request.user.id}
                serializer.save(**save_kwargs)


class OwnershipMixin(OwnershipFilterMixin, UserIDInjectionMixin):
    """
    Combined mixin that provides both ownership filtering and user_id injection.
    
    Use this for models that need complete ownership logic:
    - Filtering querysets by ownership
    - Auto-injecting user_id on create
    
    Perfect replacement for the old IsOwner permission with side effects.
    """
    pass 