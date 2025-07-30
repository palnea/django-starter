from unittest.mock import patch

from django.contrib.auth.models import Permission
from django.test import RequestFactory
from rest_framework import status
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.viewsets import ModelViewSet

from common.permissions.generic_permissions import (
    check_ownership,
    require_ownership,
    ShortCircuitOr,
    ActionAwareModelPermissions,
    IsOwner,
)
from common.view_mixins import OwnershipMixin
from custom_test.base_test import CustomIntegrationTestCase
from user.models import User


class MockDocumentViewSet(OwnershipMixin, ModelViewSet):
    """Mock ViewSet for testing ownership decorators using User model"""

    permission_classes = [ShortCircuitOr(ActionAwareModelPermissions, IsOwner)]
    queryset = User.objects.all()
    ownership_field = "id"  # For User model, we use id directly

    @action(detail=True, methods=["post"])
    @check_ownership(ownership_field="id")
    def publish(self, request, pk=None):
        """Publish a document - requires ownership"""
        return Response({"status": "published", "id": pk})

    @action(detail=True, methods=["post"])
    @check_ownership(ownership_field="id", allow_admin=False)
    def delete_permanently(self, request, pk=None):
        """Delete permanently - no admin bypass"""
        return Response({"status": "deleted permanently", "id": pk})

    @action(detail=False, methods=["get"])
    @check_ownership(ownership_field="id", check_request_data=False)
    def my_drafts(self, request):
        """List user's drafts - checks query params only"""
        return Response({"drafts": ["draft1", "draft2"]})

    @action(detail=False, methods=["post"])
    @check_ownership(ownership_field="author_id")
    def bulk_create(self, request):
        """Bulk create with custom ownership field"""
        return Response({"created": "bulk items"})

    @action(detail=True, methods=["patch"])
    @check_ownership(ownership_field="id", check_query_params=False)
    def update_metadata(self, request, pk=None):
        """Update metadata - checks request data only"""
        return Response({"status": "metadata updated", "id": pk})

    @action(detail=True, methods=["post"])
    @require_ownership(ownership_field="id")
    def activate(self, request, pk=None):
        """Simple ownership check using require_ownership"""
        return Response({"status": "activated", "id": pk})

    @action(detail=True, methods=["post"])
    @require_ownership(ownership_field="id", allow_admin=False)
    def reset_settings(self, request, pk=None):
        """Reset settings - no admin bypass"""
        return Response({"status": "settings reset", "id": pk})


class OwnershipDecoratorsTestCase(CustomIntegrationTestCase):
    """
    Tests for ownership decorators: @check_ownership and @require_ownership
    """

    def setUp(self):
        super().setUp()
        self.create_common_models()
        self.factory = RequestFactory()

        # Create test users
        self.owner_user, _ = self.create_user(
            email="owner@example.com", password="testpass123"
        )
        self.other_user, _ = self.create_user(
            email="other@example.com", password="testpass123"
        )

        # Give admin user view permission for admin bypass tests
        view_user_perm = Permission.objects.get(codename="view_user")
        self.admin.user_permissions.add(view_user_perm)

        # Create view instance for testing
        self.view = MockDocumentViewSet()
        self.view.queryset = User.objects.all()

    def create_mock_request(self, user, method="GET", data=None, query_params=None):
        """Helper to create mock requests"""
        if method == "GET":
            request = self.factory.get("/", query_params or {})
        elif method == "POST":
            request = self.factory.post("/", data or {}, format="json")
        elif method == "PATCH":
            request = self.factory.patch("/", data or {}, format="json")
        else:
            request = self.factory.generic(method, "/", data or {})

        request.user = user
        request.data = data or {}
        request.query_params = query_params or {}
        return request

    def test_check_ownership_authentication_required(self):
        """Test that unauthenticated users are rejected"""
        from django.contrib.auth.models import AnonymousUser

        request = self.create_mock_request(AnonymousUser(), "POST")
        response = self.view.publish(request, pk=str(self.owner_user.id))

        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)
        self.assertIn("Authentication required", response.data["detail"])

    def test_check_ownership_detail_action_success(self):
        """Test successful ownership check for detail action"""
        request = self.create_mock_request(self.owner_user, "POST")

        # Mock get_object to return the user
        with patch.object(self.view, "get_object", return_value=self.owner_user):
            response = self.view.publish(request, pk=str(self.owner_user.id))

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["status"], "published")

    def test_check_ownership_detail_action_forbidden(self):
        """Test ownership violation for detail action"""
        request = self.create_mock_request(self.owner_user, "POST")

        # Mock get_object to return the other user (not owned by request user)
        with patch.object(self.view, "get_object", return_value=self.other_user):
            response = self.view.publish(request, pk=str(self.other_user.id))

        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)
        self.assertIn("You don't have permission", response.data["detail"])

    def test_check_ownership_admin_bypass_allowed(self):
        """Test that admins can bypass ownership checks when allowed"""
        request = self.create_mock_request(self.admin, "POST")

        # Mock get_object to return any user
        with patch.object(self.view, "get_object", return_value=self.owner_user):
            response = self.view.publish(request, pk=str(self.owner_user.id))

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["status"], "published")

    def test_check_ownership_admin_bypass_disabled(self):
        """Test that admins are blocked when admin bypass is disabled"""
        request = self.create_mock_request(self.admin, "POST")

        # Mock get_object to return any user - should still be blocked
        with patch.object(self.view, "get_object", return_value=self.owner_user):
            response = self.view.delete_permanently(request, pk=str(self.owner_user.id))

        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_check_ownership_query_params_violation(self):
        """Test ownership violation via query parameters"""
        request = self.create_mock_request(
            self.owner_user, "GET", query_params={"id": str(self.other_user.id)}
        )

        response = self.view.my_drafts(request)
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)
        self.assertIn("you can only access your own data", response.data["detail"])

    def test_check_ownership_query_params_success(self):
        """Test successful query with own user_id"""
        request = self.create_mock_request(
            self.owner_user, "GET", query_params={"id": str(self.owner_user.id)}
        )

        response = self.view.my_drafts(request)
        self.assertEqual(response.status_code, status.HTTP_200_OK)

    def test_check_ownership_query_params_no_filter(self):
        """Test successful query without ownership filter"""
        request = self.create_mock_request(self.owner_user, "GET")

        response = self.view.my_drafts(request)
        self.assertEqual(response.status_code, status.HTTP_200_OK)

    def test_check_ownership_request_data_violation(self):
        """Test ownership violation via request data"""
        request = self.create_mock_request(
            self.owner_user,
            "POST",
            data={"author_id": self.other_user.id, "items": ["item1", "item2"]},
        )

        response = self.view.bulk_create(request)
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)
        self.assertIn(
            "you can only create/modify your own data", response.data["detail"]
        )

    def test_check_ownership_request_data_success(self):
        """Test successful request with own user_id in data"""
        request = self.create_mock_request(
            self.owner_user,
            "POST",
            data={"author_id": self.owner_user.id, "items": ["item1", "item2"]},
        )

        response = self.view.bulk_create(request)
        self.assertEqual(response.status_code, status.HTTP_200_OK)

    def test_require_ownership_success(self):
        """Test successful require_ownership decorator"""
        request = self.create_mock_request(self.owner_user, "POST")

        # Mock get_object to return the user
        with patch.object(self.view, "get_object", return_value=self.owner_user):
            response = self.view.activate(request, pk=str(self.owner_user.id))

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["status"], "activated")

    def test_require_ownership_forbidden(self):
        """Test require_ownership decorator with wrong owner"""
        request = self.create_mock_request(self.owner_user, "POST")

        # Mock get_object to return the other user
        with patch.object(self.view, "get_object", return_value=self.other_user):
            response = self.view.activate(request, pk=str(self.other_user.id))

        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_admin_can_access_any_user_data(self):
        """Test that admins can filter by any user's data"""
        request = self.create_mock_request(
            self.admin, "GET", query_params={"id": str(self.other_user.id)}
        )

        response = self.view.my_drafts(request)
        self.assertEqual(response.status_code, status.HTTP_200_OK)

    def test_admin_can_create_for_any_user(self):
        """Test that admins can create objects for any user"""
        request = self.create_mock_request(
            self.admin,
            "POST",
            data={"author_id": self.other_user.id, "items": ["item1"]},
        )

        response = self.view.bulk_create(request)
        self.assertEqual(response.status_code, status.HTTP_200_OK)

    def test_error_messages_are_descriptive(self):
        """Test that error messages provide clear feedback"""
        # Query param violation
        request = self.create_mock_request(
            self.owner_user, "GET", query_params={"user_id": str(self.other_user.id)}
        )

        response = self.view.my_drafts(request)
        self.assertIn("Cannot filter by user_id=", response.data["detail"])
        self.assertIn("you can only access your own data", response.data["detail"])

        # Request data violation
        request = self.create_mock_request(
            self.owner_user, "POST", data={"author_id": self.other_user.id}
        )

        response = self.view.bulk_create(request)
        self.assertIn("Cannot set author_id=", response.data["detail"])
        self.assertIn(
            "you can only create/modify your own data", response.data["detail"]
        )
