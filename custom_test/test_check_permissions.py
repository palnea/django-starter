import importlib
import inspect
import os
from typing import List, Tuple, Union

from django.apps import apps
from django.contrib.auth.models import Permission
from django.core.exceptions import ImproperlyConfigured
from django.test import TestCase
from django.views import View
from rest_framework.permissions import BasePermission
from rest_framework.viewsets import ViewSet

from common.permissions.generic_permissions import IsActionPermissionGranted, HasWritePermission


class PermissionExistenceTestCase(TestCase):

    def get_all_viewsets(self) -> List[Tuple[Union[View, str]]]:
        """
        Dynamically retrieve all viewsets that inherit from ModelViewSet.
        """
        viewsets = []
        third_party_prefixes = [
            "django",
            "rest_framework",
            "drf_yasg",
        ]

        for app_config in apps.get_app_configs():
            # Get the base path of the app
            app_path = app_config.path

            # Walk through the app directory and inspect each Python file
            for root, _, files in os.walk(app_path):
                for file in files:
                    # Skip admin.py and any init files
                    if file == "admin.py" or file.startswith("__") or not file.endswith(".py"):
                        continue

                    # Construct the module path
                    module_path = os.path.join(root, file) \
                        .replace(app_path, app_config.name) \
                        .replace("/", ".") \
                        .replace("\\", ".") \
                        .replace(".py", "")
                    try:
                        module = importlib.import_module(module_path)
                        for attr_name in dir(module):
                            attr = getattr(module, attr_name)
                            # Check if the attribute is a class, a subclass of ModelViewSet, and is not ModelViewSet itself
                            if inspect.isclass(attr) and issubclass(attr, View) and attr is not View:
                                # Ensure the viewset belongs to the current app and is not from a third-party package
                                if module.__name__.startswith(app_config.name) and not any(module.__name__.startswith(prefix) for prefix in third_party_prefixes):
                                    viewsets.append((attr, app_config.label))
                    except (ModuleNotFoundError, ImportError, ImproperlyConfigured):
                        # Skip modules that cannot be imported or cause configuration errors
                        continue
        return viewsets

    def get_all_actions(self, viewset_class: View) -> List[str]:
        """
        Retrieve all actions (standard and custom) for a given viewset.
        """
        # Standard actions in ModelViewSet
        standard_actions = [method for method in [
            'create', 'destroy', 'update', 'partial_update', 'retrieve', 'list'
        ] if hasattr(viewset_class, method)]

        # Custom actions added with @action decorator (only for ViewSet subclasses)
        custom_actions = []
        if issubclass(viewset_class, ViewSet):
            custom_actions = [action.__name__ for action in viewset_class.get_extra_actions()]

        # Combine standard and custom actions
        return standard_actions + custom_actions

    def contains_permission(self, permission_classes, permission_class):
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
                    if sub_perm == permission_class or sub_perm.__class__ == permission_class:
                        return True
            # Handle compound permissions (e.g., OperandHolder objects)
            if hasattr(perm, "op1_class") and hasattr(perm, "op2_class"):
                # Recursively check both operands
                if self.contains_permission([perm.op1_class], permission_class) or self.contains_permission([perm.op2_class], permission_class):
                    return True
        return False

    def test_viewset_permissions_exist(self):
        viewsets_to_test = self.get_all_viewsets()
        for viewset_class, app_label in viewsets_to_test:
            # Retrieve all actions dynamically
            actions = self.get_all_actions(viewset_class)

            # Check for permissions if IsActionPermissionGranted is in permission_classes
            if self.contains_permission(viewset_class.permission_classes, IsActionPermissionGranted):
                for action in actions:
                    view_name = viewset_class.__name__.replace("ViewSet", "").lower()
                    permission_codename = f"{view_name}.{action}"
                    with self.subTest(permission_codename=permission_codename):
                        self.assertTrue(
                            Permission.objects.filter(codename=permission_codename, content_type__app_label=app_label).exists(),
                            f"Permission '{permission_codename}' does not exist in the database"
                        )

            # Check for 'can_write_<model_name>' permission if HasWritePermission is in permission_classes
            if self.contains_permission(viewset_class.permission_classes, HasWritePermission):
                view_name = viewset_class.__name__.replace("ViewSet", "").lower()
                write_permission_codename = f"can_write_{view_name}"
                with self.subTest(permission_codename=write_permission_codename):
                    self.assertTrue(
                        Permission.objects.filter(codename=write_permission_codename, content_type__app_label=app_label).exists(),
                        f"Permission '{write_permission_codename}' does not exist in the database"
                    )
