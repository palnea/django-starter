import importlib
import inspect
import os
from typing import List

from django.apps import apps
from django.contrib.auth.models import Permission
from django.contrib.contenttypes.models import ContentType
from django.core.exceptions import ImproperlyConfigured
from django.db.models.signals import post_migrate
from django.dispatch import receiver
from django.views import View
from rest_framework.permissions import BasePermission
from rest_framework.viewsets import ViewSet

from common.permissions.generic_permissions import (
    IsActionPermissionGranted,
    HasWritePermission,
)  # Update with actual import path

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
    Signal handler to create custom permissions for ModelViewSet actions after migrations,
    including those without an associated model.
    """
    for viewset_class, app_label in get_viewsets(sender.name):
        # Determine if the viewset has a queryset/model or should use a fallback content type
        if hasattr(viewset_class, "queryset") and viewset_class.queryset is not None:
            # Use the model's content type if a queryset is defined
            model = viewset_class.queryset.model
            content_type = ContentType.objects.get_for_model(model)
            view_name = viewset_class.__name__.replace("ViewSet", "").lower()
        else:
            # Use a fallback content type for viewsets without a queryset
            content_type, _ = ContentType.objects.get_or_create(
                app_label=app_label, model="generic_view"
            )
            view_name = viewset_class.__name__.replace("ViewSet", "").lower()

        # Get actions dynamically
        actions = get_all_actions(viewset_class)

        # Create permissions for IsActionPermissionGranted if used in permission_classes
        if contains_permission(
            viewset_class.permission_classes, IsActionPermissionGranted
        ):
            for action in actions:
                codename = f"{view_name}.{action}"
                name = f"Can {action} {view_name}"
                Permission.objects.get_or_create(
                    codename=codename,
                    name=name,
                    content_type=content_type,
                )

        # Create can_write_<view_name> permission if HasWritePermission is used
        if contains_permission(viewset_class.permission_classes, HasWritePermission):
            write_permission_codename = f"can_write_{view_name}"
            write_permission_name = f"Can write {view_name}"
            Permission.objects.get_or_create(
                codename=write_permission_codename,
                name=write_permission_name,
                content_type=content_type,
            )
