# Django REST Framework Permissions Guide

## Overview

This application implements a robust permission system that follows Django best practices by integrating Django's built-in model permissions with object-level ownership checks. 

## Key Features

✅ **Django Integration**: Uses standard Django model permissions (`add_user`, `change_user`, `delete_user`, `view_user`)  
✅ **Permission-Based Access**: No role-based checks - everything uses Django's permission system  
✅ **Automatic User ID Injection**: Auto-populates `user_id` for users without broad permissions  
✅ **Object-Level Ownership**: Users without model permissions can only access their own objects  
✅ **Admin-Friendly**: Admins get access based on permissions, not roles  
✅ **Client-Friendly**: No unnecessary user_id parameters required from clients
✅ **Composable**: Generic permission composition without side effects

## Generic Permission Composition

### 🚀 **ShortCircuitOr - True OR Logic**

**Solves the side effect problem by stopping evaluation once a permission passes:**

```python
from common.permissions.generic_permissions import (
    ShortCircuitOr, DjangoModelPermissionsWithView, IsOwnerWithoutSideEffects
)

class UserViewSet(ModelViewSet):
    # ✅ Admin OR Owner access - no side effects!
    permission_classes = [ShortCircuitOr(DjangoModelPermissionsWithView, IsOwnerWithoutSideEffects)]
    queryset = User.objects.all()
    
    def get_queryset(self):
        # Only filter for users without model permissions
        if not self.request.user.has_perm('user.view_user'):
            return User.objects.filter(id=self.request.user.id)
        return User.objects.all()
```

### 🎯 **ConditionalPermission - Declarative Logic**

**Apply different permissions based on conditions:**

```python
from common.permissions.generic_permissions import ConditionalPermission

class UserViewSet(ModelViewSet):
    permission_classes = [ConditionalPermission({
        # If user has model permissions, use Django permissions
        lambda r, v: r.user.has_perm('user.view_user'): DjangoModelPermissionsWithView,
        # Otherwise, use ownership logic
        lambda r, v: True: IsOwnerWithoutSideEffects  # Default case
    })]
```

### 🔧 **Side-Effect-Free Permissions**

**Use these for composition without unwanted side effects:**

```python
from common.permissions.generic_permissions import IsOwnerWithoutSideEffects

# ✅ Safe for composition - no auto-filtering or injection
permission_classes = [DjangoModelPermissionsWithView | IsOwnerWithoutSideEffects]
```

## Permission Classes

### 1. IsOwnerWithoutSideEffects (Composition-Safe)

**Pure ownership permission designed for composition with other permissions.**

```python
from common.permissions.generic_permissions import (
    IsOwnerWithoutSideEffects, DjangoModelPermissionsWithView, ShortCircuitOr
)

class DocumentViewSet(ModelViewSet):
    # ✅ Admin OR Owner - safe composition
    permission_classes = [ShortCircuitOr(DjangoModelPermissionsWithView, IsOwnerWithoutSideEffects)]
    queryset = Document.objects.all()
    
    def get_queryset(self):
        if not self.request.user.has_perm('documents.view_document'):
            return Document.objects.filter(user_id=self.request.user.id)
        return Document.objects.all()
```

**Perfect for:** Composition scenarios where you need ownership checks without side effects

### 2. DjangoModelPermissionsWithView

**Standard Django model permissions with view permission for GET requests.**

```python
from common.permissions.generic_permissions import DjangoModelPermissionsWithView

class AdminOnlyViewSet(ModelViewSet):
    permission_classes = [DjangoModelPermissionsWithView]
    queryset = SomeModel.objects.all()
```

**Perfect for:** Admin-only resources where no ownership logic is needed

## Advanced Composition Examples

### Example 1: Admin OR Owner (Recommended Approach)

```python
class DocumentViewSet(ModelViewSet):
    """
    Admins can manage all documents.
    Users can only manage their own documents.
    """
    permission_classes = [ShortCircuitOr(
        DjangoModelPermissionsWithView,  # Admin path
        IsOwnerWithoutSideEffects        # User path
    )]
    queryset = Document.objects.all()
    
    def get_queryset(self):
        if not self.request.user.has_perm('documents.view_document'):
            return Document.objects.filter(user_id=self.request.user.id)
        return Document.objects.all()
    
    def perform_create(self, serializer):
        # Auto-assign to current user if no broad permissions
        if not self.request.user.has_perm('documents.add_document'):
            serializer.save(user_id=self.request.user.id)
        else:
            serializer.save()
```

### Example 2: Conditional Permission Logic

```python
class BlogPostViewSet(ModelViewSet):
    """
    Different permission logic based on user type.
    """
    permission_classes = [ConditionalPermission({
        # Staff can manage all posts
        lambda r, v: r.user.is_staff: DjangoModelPermissionsWithView,
        # Authors can manage their own posts
        lambda r, v: r.user.groups.filter(name='Authors').exists(): IsOwnerWithoutSideEffects,
        # Readers can only view
        lambda r, v: True: IsReadonly
    })]
```

### Example 3: Complex Business Logic

```python
class ProjectViewSet(ModelViewSet):
    """
    Complex permission logic:
    - Project owners can do anything
    - Team members can view and edit
    - Public projects allow read-only access
    """
    permission_classes = [ShortCircuitOr(
        IsProjectOwner,           # Owner can do anything
        IsTeamMember,            # Team members can view/edit
        IsPublicProjectReadOnly   # Public read access
    )]
```

## Comparison: Old vs New Approach

### ❌ **Old Approach - Creating Specialized Permissions**

```python
# Had to create specialized permission for each combination
class BlogPostModelPermissionsWithOwnership(DjangoModelPermissions):
    # Complex logic mixing model permissions with ownership for blog posts
    pass

class DocumentModelPermissionsWithOwnership(DjangoModelPermissions):
    # Another specialized permission for documents
    pass

class ProjectModelPermissionsWithOwnership(DjangoModelPermissions):
    # Yet another specialized permission for projects
    pass
```

### ✅ **New Approach - Generic Composition**

```python
# Generic, reusable composition for any use case
class UserViewSet(ModelViewSet):
    permission_classes = [ShortCircuitOr(DjangoModelPermissionsWithView, IsOwnerWithoutSideEffects)]

class DocumentViewSet(ModelViewSet):
    permission_classes = [ShortCircuitOr(DjangoModelPermissionsWithView, IsOwnerWithoutSideEffects)]

class BlogPostViewSet(ModelViewSet):
    permission_classes = [ConditionalPermission({
        lambda r, v: r.user.has_perm('blog.change_post'): DjangoModelPermissionsWithView,
        lambda r, v: True: IsOwnerWithoutSideEffects
    })]
```

## Key Benefits of Generic Composition

### ✅ **No More Specialized Permissions**
- Use `ShortCircuitOr` instead of creating new permission classes
- Combine any permissions without side effects
- Future-proof for new requirements

### ✅ **True Composition**
```python
# Complex combinations without specialized classes
permission_classes = [ShortCircuitOr(
    IsAdminUser,
    IsOwnerWithoutSideEffects & IsTeamMember,
    IsPublicReadOnly
)]
```

### ✅ **Declarative Logic**
```python
# Clear, readable permission rules
permission_classes = [ConditionalPermission({
    lambda r, v: r.user.has_perm('app.admin_access'): AllowAny,
    lambda r, v: r.user.is_verified: IsOwnerWithoutSideEffects,
    lambda r, v: True: IsReadonly
})]
```

### ✅ **Scalable Architecture**
- Add new permissions without modifying existing ones
- Compose permissions for new use cases
- No code duplication

## Usage Patterns

### Pattern 1: Admin OR Owner
```python
permission_classes = [ShortCircuitOr(DjangoModelPermissionsWithView, IsOwnerWithoutSideEffects)]
# + conditional queryset filtering
```

### Pattern 2: Conditional Logic
```python
permission_classes = [ConditionalPermission({condition: permission})]
```

### Pattern 3: Complex Composition
```python
permission_classes = [ShortCircuitOr(PermA, PermB & PermC, PermD)]
```

### Pattern 4: Pure Ownership
```python
# Use OwnershipMixin + IsOwnerWithoutSideEffects for pure ownership
from common.view_mixins import OwnershipMixin

class DocumentViewSet(OwnershipMixin, ModelViewSet):
    permission_classes = [IsOwnerWithoutSideEffects]
    # Mixin handles queryset filtering automatically
```

## Migration Guide

### From Specialized Permissions
```python
# Old: Specialized permission for each model
class DocumentViewSet(ModelViewSet):
    permission_classes = [DocumentModelPermissionsWithOwnership]

# New: Generic composition
class DocumentViewSet(ModelViewSet):
    permission_classes = [ShortCircuitOr(DjangoModelPermissionsWithView, IsOwnerWithoutSideEffects)]
    
    def get_queryset(self):
        if not self.request.user.has_perm('documents.view_document'):
            return Document.objects.filter(user_id=self.request.user.id)
        return Document.objects.all()
```

### From Standard OR Composition
```python
# Old: Side effects with standard OR
permission_classes = [DjangoModelPermissionsWithView | IsOwnerWithoutSideEffects]  # ❌ Potential evaluation issues

# New: Safe composition with short-circuiting
permission_classes = [ShortCircuitOr(DjangoModelPermissionsWithView, IsOwnerWithoutSideEffects)]  # ✅ No side effects
```

This generic approach solves your scaling problem - **no more specialized permissions needed for every combination!** 