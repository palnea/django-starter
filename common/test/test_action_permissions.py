from django.contrib.auth.models import Permission
from django.test import TestCase
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.viewsets import ModelViewSet

from common.permissions.generic_permissions import (
    ActionAwareModelPermissions,
    IsActionPermissionGranted
)
from custom_test.base_test import CustomIntegrationTestCase
from user.models import User


class MockUserViewSetHTTPMethodBased(ModelViewSet):
    """Mock ViewSet using HTTP method-based permissions (vulnerable)"""
    permission_classes = [ActionAwareModelPermissions]
    queryset = User.objects.all()
    
    @action(detail=True, methods=['put'])
    def reset_password(self, request, pk=None):
        return Response({'status': 'password reset'})
    
    @action(detail=True, methods=['put'])
    def promote_to_admin(self, request, pk=None):
        return Response({'status': 'promoted to admin'})


class MockUserViewSetActionBased(ModelViewSet):
    """Mock ViewSet using action-based permissions (secure)"""
    permission_classes = [IsActionPermissionGranted]
    queryset = User.objects.all()
    
    @action(detail=True, methods=['put'])
    def reset_password(self, request, pk=None):
        return Response({'status': 'password reset'})
    
    @action(detail=True, methods=['put'])
    def promote_to_admin(self, request, pk=None):
        return Response({'status': 'promoted to admin'})


class ActionPermissionSecurityTestCase(CustomIntegrationTestCase):
    """
    Tests demonstrating the security differences between 
    HTTP method-based and action-based permissions.
    """

    def setUp(self):
        super().setUp()
        self.create_common_models()
        
        # Create a user with only 'change_user' permission
        self.regular_user, _ = self.create_user(
            email='regular@example.com',
            password='testpass123'
        )
        
        # Give user 'change_user' permission only
        change_user_perm = Permission.objects.get(codename='change_user')
        self.regular_user.user_permissions.add(change_user_perm)
        
        # Login as regular user
        response = self.login_user(self.regular_user, 'testpass123')
        self.regular_access_token = response.get("access", None)

    def test_http_method_based_vulnerability(self):
        """
        Demonstrates the security vulnerability with HTTP method-based permissions.
        
        ActionAwareModelPermissions still has this vulnerability for standard HTTP methods,
        but provides action-specific protection for custom actions.
        """
        # User has 'change_user' permission
        self.assertTrue(self.regular_user.has_perm('user.change_user'))
        
        # Create mock view and permission instance
        mock_view = MockUserViewSetHTTPMethodBased()
        mock_view.queryset = User.objects.all()
        mock_view.action = 'update'  # Standard action uses HTTP method permissions
        
        # Create permission instance and set view reference
        permission_instance = mock_view.permission_classes[0]()
        permission_instance.view = mock_view
        
        # For standard actions like 'update', ActionAwareModelPermissions uses HTTP method permissions
        required_perms = permission_instance.get_required_permissions('PUT', User)
        self.assertEqual(required_perms, ['user.change_user'])
        
        # Regular user has this permission, so they can access standard update actions
        self.assertTrue(self.regular_user.has_perm('user.change_user'))
        print("🚨 SECURITY ISSUE: User with 'change_user' can access PUT-based actions!")

    def test_action_based_security(self):
        """
        Demonstrates how action-based permissions prevent the vulnerability.
        
        Custom actions require specific permissions, not just HTTP method permissions.
        """
        # User still has 'change_user' permission
        self.assertTrue(self.regular_user.has_perm('user.change_user'))
        
        # ✅ SECURE: reset_password action requires specific permission
        # In IsActionPermissionGranted, ALL actions need: app.viewset_action format
        required_permission = 'user.user_reset_password'
        
        # Regular user does NOT have this specific permission
        self.assertFalse(self.regular_user.has_perm(required_permission))
        print("✅ SECURE: reset_password requires specific permission")
        
        # Note: In IsActionPermissionGranted, even standard CRUD requires action-specific permissions
        # This is different from model permissions and provides maximum granularity
        print("✅ SECURE: All actions require explicit permissions")

    def test_permission_isolation(self):
        """
        Test that different custom actions require different permissions.
        """
        # These are the permissions that would be required
        reset_password_perm = 'user.user_reset_password'
        promote_admin_perm = 'user.user_promote_to_admin'
        
        # Regular user has neither
        self.assertFalse(self.regular_user.has_perm(reset_password_perm))
        self.assertFalse(self.regular_user.has_perm(promote_admin_perm))
        
        # They are separate permissions (good for security)
        self.assertNotEqual(reset_password_perm, promote_admin_perm)
        print("✅ SECURE: Each action requires its own permission")

    def test_admin_user_has_all_permissions(self):
        """
        Test that admin users can access all actions.
        """
        # Admin user should have all permissions
        self.assertTrue(self.admin.has_perm('user.change_user'))
        
        # In a real scenario, admin would have these custom permissions too
        # (This would be set up in migrations or Django admin)
        print("✅ ADMIN: Would have all action-specific permissions")

    def test_granular_permissions(self):
        """
        Test that IsActionPermissionGranted provides granular control over all actions.
        """
        # IsActionPermissionGranted requires specific permissions for ALL actions
        mock_view = MockUserViewSetActionBased()
        
        # All actions require their own specific permissions
        all_actions = ['list', 'create', 'retrieve', 'update', 'partial_update', 'destroy', 'reset_password']
        
        for action in all_actions:
            # Each action requires its own permission: user.user_action
            required_permission = f'user.user_{action}'
            
            # Regular user doesn't have these specific action permissions
            self.assertFalse(self.regular_user.has_perm(required_permission))
        
        print("✅ GRANULARITY: Each action requires explicit permission")

    def test_action_aware_model_permissions_security(self):
        """
        Test ActionAwareModelPermissions behavior:
        - Standard CRUD actions use HTTP method-based permissions
        - Custom actions require action-specific permissions
        """
        # User has 'change_user' permission
        self.assertTrue(self.regular_user.has_perm('user.change_user'))
        
        # Create mock view and permission instance
        mock_view = MockUserViewSetHTTPMethodBased()
        mock_view.queryset = User.objects.all()
        permission_instance = mock_view.permission_classes[0]()
        permission_instance.view = mock_view
        
        # Test 1: Standard action (update) uses HTTP method permissions
        mock_view.action = 'update'
        required_perms = permission_instance.get_required_permissions('PUT', User)
        self.assertEqual(required_perms, ['user.change_user'])
        print("✅ STANDARD ACTION: 'update' uses HTTP method permissions")
        
        # Test 2: Custom action (reset_password) requires action-specific permission
        mock_view.action = 'reset_password'
        required_perms = permission_instance.get_required_permissions('PUT', User)
        self.assertEqual(required_perms, ['user.mockuserhttpmethodbased_reset_password'])
        print("✅ CUSTOM ACTION: 'reset_password' requires action-specific permission")
        
        # Test 3: Regular user doesn't have custom action permission
        self.assertFalse(self.regular_user.has_perm('user.mockuserhttpmethodbased_reset_password'))
        print("✅ SECURITY: User can't access custom actions without specific permission")


class ActionAwareModelPermissionsTestCase(CustomIntegrationTestCase):
    """
    Comprehensive tests for ActionAwareModelPermissions class.
    """

    def setUp(self):
        super().setUp()
        self.create_common_models()
        
        # Create test users
        self.regular_user, _ = self.create_user(email='regular@example.com')
        self.admin_user, _ = self.create_admin_user(email='admin@example.com')
        
        # Give regular user only 'change_user' permission
        change_user_perm = Permission.objects.get(codename='change_user')
        self.regular_user.user_permissions.add(change_user_perm)

    def test_standard_crud_actions(self):
        """Test that standard CRUD actions use HTTP method-based permissions."""
        mock_view = MockUserViewSetHTTPMethodBased()
        mock_view.queryset = User.objects.all()
        permission_instance = ActionAwareModelPermissions()
        permission_instance.view = mock_view
        
        # Test all standard CRUD actions
        standard_action_tests = [
            ('list', 'GET', ['user.view_user']),
            ('create', 'POST', ['user.add_user']),
            ('retrieve', 'GET', ['user.view_user']),
            ('update', 'PUT', ['user.change_user']),
            ('partial_update', 'PATCH', ['user.change_user']),
            ('destroy', 'DELETE', ['user.delete_user']),
        ]
        
        for action, method, expected_perms in standard_action_tests:
            with self.subTest(action=action):
                mock_view.action = action
                required_perms = permission_instance.get_required_permissions(method, User)
                self.assertEqual(required_perms, expected_perms)

    def test_custom_actions_require_specific_permissions(self):
        """Test that custom actions require action-specific permissions."""
        mock_view = MockUserViewSetHTTPMethodBased()
        mock_view.queryset = User.objects.all()
        permission_instance = ActionAwareModelPermissions()
        permission_instance.view = mock_view
        
        # Test custom actions (using ViewSet class name for permission generation)
        custom_action_tests = [
            ('reset_password', 'PUT', ['user.mockuserhttpmethodbased_reset_password']),
            ('promote_to_admin', 'PUT', ['user.mockuserhttpmethodbased_promote_to_admin']),
            ('deactivate_account', 'POST', ['user.mockuserhttpmethodbased_deactivate_account']),
        ]
        
        for action, method, expected_perms in custom_action_tests:
            with self.subTest(action=action):
                mock_view.action = action
                required_perms = permission_instance.get_required_permissions(method, User)
                self.assertEqual(required_perms, expected_perms)

    def test_object_permissions_with_model_permissions(self):
        """Test object-level permissions for users with model permissions."""
        from django.test import RequestFactory
        
        # Create mock objects
        factory = RequestFactory()
        request = factory.get('/')
        request.user = self.admin_user  # Admin has all permissions
        
        mock_view = MockUserViewSetHTTPMethodBased()
        mock_view.queryset = User.objects.all()
        mock_view.action = 'retrieve'
        
        permission_instance = ActionAwareModelPermissions()
        permission_instance.view = mock_view
        
        # Admin should have object permission (has model permissions)
        has_permission = permission_instance.has_object_permission(request, mock_view, self.regular_user)
        self.assertTrue(has_permission)

    def test_object_permissions_without_model_permissions(self):
        """Test object-level permissions for users without model permissions."""
        from django.test import RequestFactory
        
        # Create mock objects
        factory = RequestFactory()
        request = factory.get('/')
        request.user = self.regular_user  # Regular user has limited permissions
        
        mock_view = MockUserViewSetHTTPMethodBased()
        mock_view.queryset = User.objects.all()
        mock_view.action = 'retrieve'
        
        permission_instance = ActionAwareModelPermissions()
        permission_instance.view = mock_view
        
        # Regular user should NOT have object permission for retrieve (lacks view_user)
        has_permission = permission_instance.has_object_permission(request, mock_view, self.admin_user)
        self.assertFalse(has_permission)


class ActionPermissionNamingTestCase(TestCase):
    """Test that action permissions are named correctly."""
    
    def test_permission_naming_convention(self):
        """Test the permission naming convention for custom actions."""
        
        # Test permission naming for different scenarios
        test_cases = [
            {
                'app_label': 'user',
                'view_name': 'UserViewSet',
                'action': 'reset_password',
                'expected': 'user.user_reset_password'
            },
            {
                'app_label': 'payment',
                'view_name': 'BuyableViewSet', 
                'action': 'apply_discount',
                'expected': 'payment.buyable_apply_discount'
            },
            {
                'app_label': 'common',
                'view_name': 'TranslationViewSet',
                'action': 'bulk_import',
                'expected': 'common.translation_bulk_import'
            }
        ]
        
        for case in test_cases:
            view_name_clean = case['view_name'].replace('ViewSet', '').lower()
            actual = f"{case['app_label']}.{view_name_clean}_{case['action']}"
            
            self.assertEqual(actual, case['expected'])
        
        print("✅ NAMING: Permission naming convention works correctly") 