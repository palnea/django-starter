# Permission Security Analysis: HTTP Methods vs Actions

## 🚨 Security Problem with HTTP Method-Based Permissions

### Current Vulnerable Implementation

```python
from common.permissions.generic_permissions import DjangoModelPermissionsWithView

class UserViewSet(ModelViewSet):
    permission_classes = [DjangoModelPermissionsWithView]
    
    @action(detail=True, methods=['put'])
    def reset_password(self, request, pk=None):
        """🚨 SECURITY ISSUE: Anyone with 'change_user' permission can reset passwords!"""
        user = self.get_object()
        user.set_password(request.data['new_password'])
        user.save()
        return Response({'status': 'password reset'})
    
    @action(detail=True, methods=['put'])
    def promote_to_admin(self, request, pk=None):
        """🚨 SECURITY ISSUE: Anyone with 'change_user' permission can create admins!"""
        user = self.get_object()
        user.is_staff = True
        user.is_superuser = True
        user.save()
        return Response({'status': 'promoted to admin'})
    
    @action(detail=True, methods=['post'])
    def send_critical_notification(self, request, pk=None):
        """🚨 SECURITY ISSUE: Anyone with 'add_user' permission can send notifications!"""
        # Send critical system notification
        return Response({'status': 'notification sent'})
```

**Problem**: All `PUT` actions inherit `change_user` permission, but these operations are completely different!

### Permission Mapping Problem

| Action | HTTP Method | Current Permission | Should Require |
|--------|-------------|-------------------|----------------|
| `update` | PUT | `change_user` ✅ | `change_user` |
| `reset_password` | PUT | `change_user` ❌ | `user_reset_password` |
| `promote_to_admin` | PUT | `change_user` ❌ | `user_promote_to_admin` |
| `send_critical_notification` | POST | `add_user` ❌ | `user_send_critical_notification` |

## ✅ Secure Solutions

### Solution 1: Pure Action-Based Permissions (Recommended)

```python
from common.permissions.generic_permissions import IsActionPermissionGranted

class UserViewSet(ModelViewSet):
    permission_classes = [IsActionPermissionGranted]
    
    # ALL actions require explicit permissions:
    # list -> user.user_list
    # create -> user.user_create  
    # update -> user.user_update
    # reset_password -> user.user_reset_password
    # promote_to_admin -> user.user_promote_to_admin
```

### Solution 2: Composition for Flexibility

```python
from common.permissions.generic_permissions import (
    IsActionPermissionGranted, IsOwnerWithoutSideEffects, ShortCircuitOr
)

class UserViewSet(ModelViewSet):
    permission_classes = [ShortCircuitOr(
        IsActionPermissionGranted,   # Admin access with action-specific permissions
        IsOwnerWithoutSideEffects    # Users can only access their own data
    )]
    
    @action(detail=True, methods=['put'])
    def reset_password(self, request, pk=None):
        """
        ✅ SECURE: Requires either:
        - 'user.user_reset_password' permission (admin), OR
        - User is accessing their own record (ownership)
        """
        pass
```

## 🔧 Migration Guide

### Step 1: Create Action-Specific Permissions

Add these permissions to Django Admin or via migrations:

```python
# Migration to create action-specific permissions
from django.db import migrations
from django.contrib.auth.models import Permission
from django.contrib.contenttypes.models import ContentType

def create_action_permissions(apps, schema_editor):
    User = apps.get_model('user', 'User')
    content_type = ContentType.objects.get_for_model(User)
    
    permissions = [
        ('user_reset_password', 'Can reset user password'),
        ('user_promote_to_admin', 'Can promote user to admin'),
        ('user_send_critical_notification', 'Can send critical notifications'),
    ]
    
    for codename, name in permissions:
        Permission.objects.get_or_create(
            codename=codename,
            name=name,
            content_type=content_type,
        )

class Migration(migrations.Migration):
    operations = [
        migrations.RunPython(create_action_permissions),
    ]
```

### Step 2: Update Permission Classes

```python
# Before (Vulnerable)
class UserViewSet(ModelViewSet):
    permission_classes = [DjangoModelPermissionsWithView]

# After (Secure)
class UserViewSet(ModelViewSet):
    permission_classes = [IsActionPermissionGranted]
```

### Step 3: Assign Permissions to Users/Groups

```python
# In Django Admin or programmatically
admin_group = Group.objects.get(name='Admin')
admin_group.permissions.add(
    Permission.objects.get(codename='user_reset_password'),
    Permission.objects.get(codename='user_promote_to_admin'),
    Permission.objects.get(codename='user_send_critical_notification'),
)
```

## 🧪 Testing the Security

### Test Action-Specific Permissions

```python
def test_action_permissions_security():
    # User with only 'change_user' permission
    user = User.objects.create_user('regular_user')
    user.user_permissions.add(Permission.objects.get(codename='change_user'))
    
    # Should be able to update user data
    response = client.put('/users/1/', {'name': 'Updated'})
    assert response.status_code == 200
    
    # Should NOT be able to reset password (different permission required)
    response = client.put('/users/1/reset_password/', {'new_password': 'hack123'})
    assert response.status_code == 403  # ✅ Blocked!
    
    # Should NOT be able to promote to admin
    response = client.put('/users/1/promote_to_admin/')
    assert response.status_code == 403  # ✅ Blocked!
```

## 📊 Security Comparison

| Approach | Standard CRUD | Custom Actions | Security Level | Migration Effort |
|----------|---------------|----------------|----------------|------------------|
| **HTTP Method-Based** | ✅ Good | ❌ Vulnerable | 🔴 Low | None |
| **Pure Action-Based** | ✅ Granular | ✅ Secure | 🟢 Highest | Medium |

## 🎯 Recommendation

**Use `IsActionPermissionGranted`** for maximum security:
- **Security**: ALL actions require explicit permissions
- **Granularity**: Complete control over every single action
- **Consistency**: Same permission pattern for all actions
- **Automation**: Permissions auto-created via post_migrate signals
- **Maintainability**: Single, consistent approach

This approach provides the highest level of security by treating every action equally and requiring explicit permissions! 🔐 