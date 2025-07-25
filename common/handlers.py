import importlib
import inspect
import os
from typing import List

from django.apps import apps
from django.contrib.auth.models import Permission, Group
from django.contrib.contenttypes.models import ContentType
from django.core.exceptions import ImproperlyConfigured
from django.db.models.signals import post_migrate
from django.dispatch import receiver
from django.views import View
from rest_framework.permissions import BasePermission
from rest_framework.viewsets import ViewSet

from common.permissions.generic_permissions import (
    IsActionPermissionGranted,
    get_action_permission_name,
)

# Standard actions in ModelViewSet
STANDARD_ACTIONS = ["create", "destroy", "update", "partial_update", "retrieve", "list"]


def get_viewsets(app_label=None):
    """
    Dynamically retrieve all viewsets that inherit from ModelViewSet for a specified app.
    If no app_label is provided, retrieves viewsets for all installed apps.
    """
    viewsets = []
    third_party_prefixes = [
        "django",
        "rest_framework",
        "drf_yasg",
    ]

    for app_config in apps.get_app_configs():
        # If app_label is specified, skip other apps
        if app_label and app_config.label != app_label:
            continue

        app_path = app_config.path
        for root, _, files in os.walk(app_path):
            for file in files:
                if (
                    file == "admin.py"
                    or file.startswith("__")
                    or not file.endswith(".py")
                    or "test" in file.lower()  # Exclude test files
                    or "test" in root.lower()  # Exclude test directories
                ):
                    continue

                module_path = (
                    os.path.join(root, file)
                    .replace(app_path, app_config.name)
                    .replace("/", ".")
                    .replace("\\", ".")
                    .replace(".py", "")
                )
                try:
                    module = importlib.import_module(module_path)
                    for attr_name in dir(module):
                        attr = getattr(module, attr_name)
                        if (
                            inspect.isclass(attr)
                            and issubclass(attr, View)
                            and attr is not View
                            and not attr_name.startswith("Mock")  # Exclude Mock classes
                            and not attr_name.startswith("Test")  # Exclude Test classes
                        ):
                            # Check that the module is from the current app and not third-party
                            if module.__name__.startswith(app_config.name) and not any(
                                module.__name__.startswith(prefix)
                                for prefix in third_party_prefixes
                            ):
                                viewsets.append((attr, app_config.label))
                except (ModuleNotFoundError, ImportError, ImproperlyConfigured):
                    continue
    return viewsets


def get_all_actions(viewset_class: View) -> List[str]:
    """
    Retrieve all actions (standard and custom) for a given viewset.
    """
    # Standard actions in ModelViewSet
    standard_actions = [
        method
        for method in [
            "create",
            "destroy",
            "update",
            "partial_update",
            "retrieve",
            "list",
        ]
        if hasattr(viewset_class, method)
    ]

    # Custom actions added with @action decorator (only for ViewSet subclasses)
    custom_actions = []
    if issubclass(viewset_class, ViewSet):
        custom_actions = [
            action.__name__ for action in viewset_class.get_extra_actions()
        ]

    # Combine standard and custom actions
    return standard_actions + custom_actions


def contains_permission(permission_classes, permission_class):
    """
    Recursively checks if a permission_class is contained within permission_classes,
    handling both direct instances and compound expressions.
    """
    # Ensure permission_classes is always a list
    if not isinstance(permission_classes, list):
        permission_classes = [permission_classes]

    for perm in permission_classes:  # Ensure permission_classes is iterable
        # Check if perm directly matches the target_permission class
        if perm == permission_class or perm.__class__ == permission_class:
            return True
        # Check if perm is a compound permission
        if isinstance(perm, BasePermission) and hasattr(perm, "permissions"):
            # Inspect permissions within the compound permission
            for sub_perm in perm.permissions:
                if (
                    sub_perm == permission_class
                    or sub_perm.__class__ == permission_class
                ):
                    return True
        # Handle compound permissions (e.g., OperandHolder objects)
        if hasattr(perm, "op1_class") and hasattr(perm, "op2_class"):
            # Recursively check both operands
            if contains_permission(
                [perm.op1_class], permission_class
            ) or contains_permission([perm.op2_class], permission_class):
                return True
    return False


@receiver(post_migrate)
def create_permissions(sender, **kwargs):
    """
    Signal handler to create Django model permissions for ModelViewSet actions after migrations.
    
    This creates standard Django permissions that work with DjangoModelPermissions:
    - add_model
    - change_model  
    - delete_model
    - view_model
    
    These are created automatically by Django for models, but this handler ensures
    they exist for all models used in ViewSets and assigns them to the Admin group.
    """
    create_admin_group_with_all_permissions()

    for viewset_class, app_label in get_viewsets(sender.name):
        # Only process viewsets that have a queryset/model
        if not (hasattr(viewset_class, "queryset") and viewset_class.queryset is not None):
            continue
            
        model = viewset_class.queryset.model
        content_type = ContentType.objects.get_for_model(model)
        
        # Standard Django model permissions
        standard_permissions = [
            ('add', f'Can add {model._meta.verbose_name}'),
            ('change', f'Can change {model._meta.verbose_name}'),
            ('delete', f'Can delete {model._meta.verbose_name}'),
            ('view', f'Can view {model._meta.verbose_name}'),
        ]
        
        # Create standard permissions if they don't exist
        for codename_prefix, name in standard_permissions:
            codename = f"{codename_prefix}_{model._meta.model_name}"
            Permission.objects.get_or_create(
                codename=codename,
                name=name,
                content_type=content_type,
            )

        # Create permissions for IsActionPermissionGranted if used in permission_classes
        if contains_permission(
            viewset_class.permission_classes, IsActionPermissionGranted
        ):
            actions = get_all_actions(viewset_class)
            
            for action in actions:
                # Use centralized permission naming function
                codename, full_permission_name = get_action_permission_name(
                    viewset_class, action, app_label
                )
                
                view_name = viewset_class.__name__.replace("ViewSet", "").lower()
                name = f"Can {action} {view_name}"
                Permission.objects.get_or_create(
                    codename=codename,
                    name=name,
                    content_type=content_type,
                )


def create_admin_group_with_all_permissions():
    """
    Create Admin group and assign all permissions to it.
    This ensures admins have access to all functionality.
    """
    admin_group, created = Group.objects.get_or_create(name="Admin")
    
    # Assign all permissions to admin group
    if created or admin_group.permissions.count() == 0:
        all_permissions = Permission.objects.all()
        admin_group.permissions.set(all_permissions)
        admin_group.save()
