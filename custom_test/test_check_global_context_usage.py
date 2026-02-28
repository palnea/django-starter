import os
import re

from django.apps import apps
from django.test import TestCase


class GlobalContextBoundaryTestCase(TestCase):
    """Ensures GlobalContext is only used in HTTP-bound layers (views, permissions, middleware, response).

    Business logic (models, services, tasks, serializers) must receive data as explicit parameters so they work
    correctly in Django shell, Celery tasks, and tests.
    """

    GLOBAL_CONTEXT_PATTERN = re.compile(
        r"(?:GlobalContextMiddleware|get_global_context|from\s+common\.middlewares\.global_context_middleware\s+import)"
    )

    # Relative path fragments that are ALLOWED to use GlobalContext
    ALLOWED_PATTERNS = [
        "views.py",
        "permissions",
        "middleware",
        os.path.join("common", "response"),
    ]

    # Relative path fragments that are FORBIDDEN from using GlobalContext
    FORBIDDEN_PATTERNS = [
        "models.py",
        "services.py",
        "tasks.py",
        "serializers.py",
        os.path.join("utils", ""),
    ]

    def _is_allowed(self, rel_path: str) -> bool:
        """Check if a file path is in the allowed layer."""
        # Test files are always allowed
        if "test" in rel_path.lower():
            return True

        for pattern in self.ALLOWED_PATTERNS:
            if pattern in rel_path:
                return True
        return False

    def _is_forbidden(self, rel_path: str) -> bool:
        """Check if a file path is in a forbidden layer."""
        for pattern in self.FORBIDDEN_PATTERNS:
            if pattern in rel_path:
                return True
        return False

    def test_global_context_not_used_in_business_logic(self):
        """GlobalContextMiddleware must not be imported in models, services, tasks, or serializers."""
        violations = []
        third_party_prefixes = ["django", "rest_framework", "drf_yasg"]

        for app_config in apps.get_app_configs():
            # Skip third-party apps
            if any(
                app_config.name.startswith(prefix) for prefix in third_party_prefixes
            ):
                continue

            app_path = app_config.path

            for root, _, files in os.walk(app_path):
                for file in files:
                    if not file.endswith(".py") or file.startswith("__"):
                        continue

                    full_path = os.path.join(root, file)
                    rel_path = os.path.relpath(full_path)

                    # Skip allowed locations
                    if self._is_allowed(rel_path):
                        continue

                    # Only flag forbidden locations
                    if not self._is_forbidden(rel_path):
                        continue

                    try:
                        with open(full_path, "r") as f:
                            content = f.read()
                    except (IOError, UnicodeDecodeError):
                        continue

                    if self.GLOBAL_CONTEXT_PATTERN.search(content):
                        violations.append(rel_path)

        self.assertEqual(
            violations,
            [],
            f"GlobalContext must not be used in business logic layers. "
            f"Pass data as explicit parameters instead.\n"
            f"Violating files:\n" + "\n".join(f"  - {v}" for v in violations),
        )
