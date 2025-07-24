from rest_framework.viewsets import ModelViewSet
from django.http import Http404
from rest_framework.generics import get_object_or_404


class OwnershipFilterMixin:
    """
    Mixin to handle ownership-based queryset filtering.
    
    This replaces the automatic filtering that was previously done in permission classes.
    Now filtering is explicit and visible in the view layer.
    """
    
    ownership_field = 'user_id'  # Override in subclass if needed
    ownership_permission = None  # e.g., 'user.view_user' - set in subclass
    
    def get_queryset(self):
        """
        Filter queryset based on ownership for users without broad permissions.
        Users with model-level permissions see all objects.
        """
        queryset = super().get_queryset()
        
        # If no ownership permission is specified, apply ownership filtering by default
        if self.ownership_permission is None:
            # Auto-determine permission from model
            model = queryset.model
            app_label = model._meta.app_label
            model_name = model._meta.model_name
            self.ownership_permission = f"{app_label}.view_{model_name}"
        
        # If user has broad permissions, return full queryset
        if self.request.user.has_perm(self.ownership_permission):
            return queryset
            
        # Otherwise filter by ownership
        # Special case: For User model, filter by id instead of user_id
        if queryset.model.__name__ == 'User' and self.ownership_field == 'user_id':
            filter_kwargs = {'id': self.request.user.id}
        else:
            filter_kwargs = {self.ownership_field: self.request.user.id}
        
        return queryset.filter(**filter_kwargs)

    def get_object(self):
        """
        Ensure that detail operations (retrieve, update, delete) also respect ownership filtering.
        This prevents users from accessing objects that aren't in their filtered queryset.
        """
        # Use the ownership-filtered queryset for getting the object
        queryset = self.filter_queryset(self.get_queryset())
        
        # Perform the lookup filtering.
        lookup_url_kwarg = self.lookup_url_kwarg or self.lookup_field
        
        assert lookup_url_kwarg in self.kwargs, (
            'Expected view %s to be called with a URL keyword argument '
            'named "%s". Fix your URL conf, or set the `.lookup_field` '
            'attribute on the view correctly.' %
            (self.__class__.__name__, lookup_url_kwarg)
        )
        
        filter_kwargs = {self.lookup_field: self.kwargs[lookup_url_kwarg]}
        obj = get_object_or_404(queryset, **filter_kwargs)
        
        # May raise a permission denied
        self.check_object_permissions(self.request, obj)
        
        return obj


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