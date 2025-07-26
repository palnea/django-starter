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
    ShortCircuitOr, ActionAwareModelPermissions, IsOwnerWithoutSideEffects
)

class UserViewSet(ModelViewSet):
    # ✅ Admin OR Owner access - no side effects!
    permission_classes = [ShortCircuitOr(ActionAwareModelPermissions, IsOwnerWithoutSideEffects)]
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
        lambda r, v: r.user.has_perm('user.view_user'): ActionAwareModelPermissions,
        # Otherwise, use ownership logic
        lambda r, v: True: IsOwnerWithoutSideEffects  # Default case
    })]
```

### 🔧 **Side-Effect-Free Permissions**

**Use these for composition without unwanted side effects:**

```python
from common.permissions.generic_permissions import IsOwnerWithoutSideEffects

# ✅ Safe for composition - no auto-filtering or injection
permission_classes = [ActionAwareModelPermissions | IsOwnerWithoutSideEffects]
```

## Permission Classes

### 1. ActionAwareModelPermissions (Enhanced Django Permissions)

**Enhanced Django model permissions with action-level granularity and view permission support.**

```python
from common.permissions.generic_permissions import ActionAwareModelPermissions

class AdminOnlyViewSet(ModelViewSet):
    permission_classes = [ActionAwareModelPermissions]
    queryset = SomeModel.objects.all()
```

**Features:**
- **CRUD Operations**: Uses standard Django model permissions (add_model, change_model, delete_model, view_model)
- **Custom Actions**: Requires explicit permissions (e.g., `user.user_reset_password` for reset_password action)
- **View Permission**: Includes view permission for GET requests (unlike standard DjangoModelPermissions)
- **Security**: Prevents custom actions from inheriting inappropriate CRUD permissions

**Perfect for:** Admin-only resources where no ownership logic is needed, enhanced security for custom actions

### 2. IsOwnerWithoutSideEffects (Composition-Safe)

**Pure ownership permission designed for composition with other permissions.**

```python
from common.permissions.generic_permissions import (
    IsOwnerWithoutSideEffects, ActionAwareModelPermissions, ShortCircuitOr
)

class DocumentViewSet(ModelViewSet):
    # ✅ Admin OR Owner - safe composition
    permission_classes = [ShortCircuitOr(ActionAwareModelPermissions, IsOwnerWithoutSideEffects)]
    queryset = Document.objects.all()
    
    def get_queryset(self):
        if not self.request.user.has_perm('documents.view_document'):
            return Document.objects.filter(user_id=self.request.user.id)
        return Document.objects.all()
```

**Perfect for:** Composition scenarios where you need ownership checks without side effects

### 3. IsActionPermissionGranted (Action-Specific Permissions)

**Granular permission checks for specific ViewSet actions.**

```python
from common.permissions.generic_permissions import IsActionPermissionGranted

class UserViewSet(ModelViewSet):
    permission_classes = [IsActionPermissionGranted]
    
    @action(detail=True, methods=['post'])
    def reset_password(self, request, user_id=None):
        # Requires permission: user.user_reset_password
        pass
```

**Features:**
- **Action-Based**: Uses actual DRF action names instead of HTTP methods
- **Granular Control**: Each action requires its own permission
- **Format**: `{app_label}.{view_name}_{action}` (e.g., `user.user_reset_password`)

**Perfect for:** Fine-grained permission control over individual actions

### 4. IsReadonly (Read-Only Access)

**Global permission check for read-only access.**

```python
from common.permissions.generic_permissions import IsReadonly

class PublicViewSet(ModelViewSet):
    permission_classes = [IsReadonly]
    # Only allows GET, HEAD, OPTIONS methods
```

**Perfect for:** Public or read-only endpoints

## View Mixins for Side Effects

### OwnershipMixin (Complete Ownership Logic)

**Combined mixin that provides both ownership filtering and user_id injection.**

```python
from common.view_mixins import OwnershipMixin

class DocumentViewSet(OwnershipMixin, ModelViewSet):
    permission_classes = [ShortCircuitOr(ActionAwareModelPermissions, IsOwnerWithoutSideEffects)]
    queryset = Document.objects.all()
    # Mixin automatically handles:
    # - Queryset filtering by ownership for users without model permissions
    # - Auto-injection of user_id on create for users without broad permissions
```

### OwnershipFilterMixin (Queryset Filtering Only)

```python
from common.view_mixins import OwnershipFilterMixin

class DocumentViewSet(OwnershipFilterMixin, ModelViewSet):
    # Only handles queryset filtering, no user_id injection
```

### UserIDInjectionMixin (Auto-Injection Only)

```python
from common.view_mixins import UserIDInjectionMixin

class DocumentViewSet(UserIDInjectionMixin, ModelViewSet):
    # Only handles user_id injection on create, no queryset filtering
```

## Advanced Composition Examples

### Example 1: Admin OR Owner (Recommended Approach)

```python
from common.view_mixins import OwnershipMixin
from common.permissions.generic_permissions import (
    ShortCircuitOr, ActionAwareModelPermissions, IsOwnerWithoutSideEffects
)

class DocumentViewSet(OwnershipMixin, ModelViewSet):
    """
    Admins can manage all documents.
    Users can only manage their own documents.
    """
    permission_classes = [ShortCircuitOr(
        ActionAwareModelPermissions,     # Admin path
        IsOwnerWithoutSideEffects        # User path
    )]
    queryset = Document.objects.all()
    # OwnershipMixin handles queryset filtering and user_id injection automatically
```

### Example 2: Conditional Permission Logic

```python
class BlogPostViewSet(ModelViewSet):
    """
    Different permission logic based on user type.
    """
    permission_classes = [ConditionalPermission({
        # Staff can manage all posts
        lambda r, v: r.user.is_staff: ActionAwareModelPermissions,
        # Authors can manage their own posts
        lambda r, v: r.user.groups.filter(name='Authors').exists(): IsOwnerWithoutSideEffects,
        # Readers can only view
        lambda r, v: True: IsReadonly
    })]
```

### Example 3: Read-Only OR Admin Permissions

```python
class BuyableViewSet(ModelViewSet):
    """
    Public read-only access OR admin management.
    """
    permission_classes = [IsReadonly | ActionAwareModelPermissions]
    queryset = Buyable.objects.all()
```

### Example 4: Action-Specific Permissions

```python
class UserViewSet(OwnershipMixin, ModelViewSet):
    """
    Real-world example from the codebase.
    Combines CRUD permissions with granular action permissions.
    """
    permission_classes = [ShortCircuitOr(
        ActionAwareModelPermissions,     # For CRUD + custom actions with proper permissions
        IsOwnerWithoutSideEffects        # For ownership-based access
    )]
    
    @action(detail=True, methods=['post'])
    def reset_password(self, request, user_id=None):
        # Requires: user.user_reset_password permission
        pass
    
    @action(detail=True, methods=['patch'])  
    def promote_to_admin(self, request, user_id=None):
        # Requires: user.user_promote_to_admin permission
        pass
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
class UserViewSet(OwnershipMixin, ModelViewSet):
    permission_classes = [ShortCircuitOr(ActionAwareModelPermissions, IsOwnerWithoutSideEffects)]

class DocumentViewSet(OwnershipMixin, ModelViewSet):
    permission_classes = [ShortCircuitOr(ActionAwareModelPermissions, IsOwnerWithoutSideEffects)]

class BlogPostViewSet(ModelViewSet):
    permission_classes = [ConditionalPermission({
        lambda r, v: r.user.has_perm('blog.change_post'): ActionAwareModelPermissions,
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
    IsReadonly
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

### Pattern 1: Admin OR Owner (Most Common)
```python
class DocumentViewSet(OwnershipMixin, ModelViewSet):
    permission_classes = [ShortCircuitOr(ActionAwareModelPermissions, IsOwnerWithoutSideEffects)]
    # OwnershipMixin handles all side effects (filtering + injection)
```

### Pattern 2: Conditional Logic
```python
permission_classes = [ConditionalPermission({condition: permission})]
```

### Pattern 3: Read-Only OR Admin
```python
permission_classes = [IsReadonly | ActionAwareModelPermissions]
```

### Pattern 4: Pure Ownership with Explicit Control
```python
class DocumentViewSet(OwnershipFilterMixin, ModelViewSet):
    permission_classes = [IsOwnerWithoutSideEffects]
    # Manual control over what side effects to include
```

### Pattern 5: Action-Specific Permissions
```python
permission_classes = [IsActionPermissionGranted]
# Requires explicit permission for each action
```

## Migration Guide

### From Specialized Permissions
```python
# Old: Specialized permission for each model
class DocumentViewSet(ModelViewSet):
    permission_classes = [DocumentModelPermissionsWithOwnership]

# New: Generic composition
class DocumentViewSet(OwnershipMixin, ModelViewSet):
    permission_classes = [ShortCircuitOr(ActionAwareModelPermissions, IsOwnerWithoutSideEffects)]
```

### From Standard OR Composition
```python
# Old: Side effects with standard OR
permission_classes = [ActionAwareModelPermissions | IsOwnerWithoutSideEffects]  # ❌ Potential evaluation issues

# New: Safe composition with short-circuiting
permission_classes = [ShortCircuitOr(ActionAwareModelPermissions, IsOwnerWithoutSideEffects)]  # ✅ No side effects
```

### Key Changes from Documentation
1. **`DjangoModelPermissionsWithView` → `ActionAwareModelPermissions`**: Enhanced version with action-level permissions
2. **Added `IsActionPermissionGranted`**: For fine-grained action control
3. **Clarified Mixins**: `OwnershipMixin` combines filtering + injection, separate mixins available for granular control
4. **Real Examples**: All examples now match actual codebase implementation

This generic approach solves your scaling problem - **no more specialized permissions needed for every combination!** 