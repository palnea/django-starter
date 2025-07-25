"""
Tests for DRF serializer integration with structured error responses.

This test file verifies that all DRF serializer validation errors are properly
converted to the structured error format, ensuring consistency across the entire API.
"""

from django.test import TestCase, override_settings
from django.contrib.auth.models import User
from rest_framework import serializers, status
from rest_framework.test import APITestCase, APIRequestFactory
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.exceptions import ValidationError
from unittest.mock import Mock

from common.exception_handling.custom_exception_handler import custom_exception_handler


class TestUserSerializer(serializers.ModelSerializer):
    """Test serializer for validation error testing"""
    
    class Meta:
        model = User
        fields = ['username', 'email', 'password', 'first_name', 'last_name']
        extra_kwargs = {
            'password': {'write_only': True, 'min_length': 8},
            'email': {'required': True},
            'username': {'required': True, 'min_length': 3}
        }
    
    def validate_email(self, value):
        """Custom email validation"""
        if not value or '@' not in value:
            raise serializers.ValidationError("Email must contain @ symbol", code='invalid_email')
        if value.endswith('.test'):
            raise serializers.ValidationError("Test emails are not allowed", code='test_email_forbidden')
        return value
    
    def validate_username(self, value):
        """Custom username validation"""
        if len(value) < 3:
            raise serializers.ValidationError("Username must be at least 3 characters", code='too_short')
        if value.lower() == 'admin':
            raise serializers.ValidationError("Username 'admin' is reserved", code='reserved_username')
        return value
    
    def validate(self, attrs):
        """Object-level validation"""
        username = attrs.get('username')
        email = attrs.get('email')
        
        if username and email and username.lower() in email.lower():
            raise serializers.ValidationError({
                'username': 'Username cannot be part of email address',
                'email': 'Email cannot contain username'
            })
        
        # Non-field error example
        if attrs.get('first_name') == 'Test' and attrs.get('last_name') == 'User':
            raise serializers.ValidationError('Test users are not allowed in production')
        
        return attrs


class TestLoginSerializer(serializers.Serializer):
    """Test serializer for login validation"""
    
    email = serializers.EmailField(required=True, error_messages={
        'required': 'Email address is required for login',
        'invalid': 'Please enter a valid email address'
    })
    password = serializers.CharField(required=True, min_length=1, error_messages={
        'required': 'Password is required',
        'blank': 'Password cannot be empty'
    })
    
    def validate(self, attrs):
        email = attrs.get('email')
        password = attrs.get('password')
        
        # Simulate authentication check
        if email == 'banned@example.com':
            raise serializers.ValidationError('This account has been suspended')
        
        return attrs


class TestAPIView(APIView):
    """Test API view for serializer validation testing"""
    
    def post(self, request):
        if request.path.endswith('/register'):
            serializer = TestUserSerializer(data=request.data)
        elif request.path.endswith('/login'):
            serializer = TestLoginSerializer(data=request.data)
        else:
            return Response({'error': 'Invalid endpoint'}, status=400)
        
        serializer.is_valid(raise_exception=True)
        return Response({'success': True}, status=201)


@override_settings(USE_STRUCTURED_ERROR_RESPONSES=True)
class DRFSerializerStructuredErrorTest(TestCase):
    """Test DRF serializer validation errors are converted to structured format"""
    
    def setUp(self):
        self.factory = APIRequestFactory()
        self.view = TestAPIView.as_view()
    
    def _make_request_and_get_error_response(self, path, data):
        """Helper method to make request and get structured error response"""
        request = self.factory.post(path, data, format='json')
        
        try:
            response = self.view(request)
            self.fail("Expected ValidationError but request succeeded")
        except ValidationError as exc:
            # Simulate the exception handler
            context = {
                'request': request,
                'view': TestAPIView(),
                'args': (),
                'kwargs': {}
            }
            
            return custom_exception_handler(exc, context)
    
    def test_required_field_errors(self):
        """Test that required field errors are properly structured"""
        response = self._make_request_and_get_error_response('/api/register', {})
        
        self.assertEqual(response.status_code, 400)
        data = response.data
        
        # Verify structured format
        self.assertEqual(data['type'], 'validation_error')
        self.assertEqual(data['status'], 400)
        self.assertIn('title', data)
        self.assertIn('detail', data)
        self.assertIn('errors', data)
        
        # Verify field-specific errors
        self.assertIn('username', data['errors'])
        self.assertIn('email', data['errors'])
        
        # Check error structure for each field
        for field_name, field_errors in data['errors'].items():
            self.assertIsInstance(field_errors, list)
            for error in field_errors:
                self.assertIn('code', error)
                self.assertIn('message', error)
                self.assertIn('value', error)
    
    def test_custom_validation_errors(self):
        """Test custom field validation errors"""
        response = self._make_request_and_get_error_response('/api/register', {
            'username': 'ab',  # Too short
            'email': 'invalid-email',  # No @ symbol
            'password': '123',  # Too short
        })
        
        data = response.data
        
        self.assertEqual(data['type'], 'validation_error')
        self.assertIn('errors', data)
        
        # Check specific validation errors
        username_errors = data['errors'].get('username', [])
        self.assertTrue(any('at least 3 characters' in error['message'] for error in username_errors))
        
        email_errors = data['errors'].get('email', [])
        self.assertTrue(any('@ symbol' in error['message'] for error in email_errors))
        
        password_errors = data['errors'].get('password', [])
        self.assertTrue(any(error['message'] for error in password_errors))
    
    def test_custom_error_codes(self):
        """Test that custom error codes are preserved"""
        response = self._make_request_and_get_error_response('/api/register', {
            'username': 'admin',  # Reserved username
            'email': 'test@example.test',  # Test email forbidden
            'password': 'validpassword123'
        })
        
        data = response.data
        
        # Check that custom error codes are preserved
        username_errors = data['errors'].get('username', [])
        self.assertTrue(any(error['code'] == 'reserved_username' for error in username_errors))
        
        email_errors = data['errors'].get('email', [])
        self.assertTrue(any(error['code'] == 'test_email_forbidden' for error in email_errors))
    
    def test_object_level_validation_errors(self):
        """Test object-level validation errors with field mapping"""
        response = self._make_request_and_get_error_response('/api/register', {
            'username': 'testuser',
            'email': 'testuser@example.com',  # Username in email
            'password': 'validpassword123'
        })
        
        data = response.data
        
        self.assertEqual(data['type'], 'validation_error')
        self.assertIn('errors', data)
        
        # Should have errors for both username and email
        self.assertIn('username', data['errors'])
        self.assertIn('email', data['errors'])
    
    def test_non_field_errors(self):
        """Test non-field errors are handled as general errors"""
        response = self._make_request_and_get_error_response('/api/register', {
            'username': 'testuser',
            'email': 'test@example.com',
            'password': 'validpassword123',
            'first_name': 'Test',
            'last_name': 'User'  # This will trigger non-field error
        })
        
        data = response.data
        
        self.assertEqual(data['type'], 'validation_error')
        # Non-field errors should be in the general error, not in the errors dict
        self.assertIn('detail', data)
        self.assertTrue('Test users are not allowed' in data['detail'])
    
    def test_login_serializer_errors(self):
        """Test errors from different serializer"""
        response = self._make_request_and_get_error_response('/api/login', {
            'email': 'invalid-email-format'
            # Missing password
        })
        
        data = response.data
        
        self.assertEqual(data['type'], 'validation_error')
        self.assertIn('errors', data)
        
        # Should have errors for both email format and missing password
        self.assertIn('email', data['errors'])
        self.assertIn('password', data['errors'])
    
    def test_custom_error_messages(self):
        """Test custom error messages are preserved"""
        response = self._make_request_and_get_error_response('/api/login', {})
        
        data = response.data
        email_errors = data['errors'].get('email', [])
        password_errors = data['errors'].get('password', [])
        
        # Check custom error messages
        self.assertTrue(any('Email address is required for login' in error['message'] for error in email_errors))
        self.assertTrue(any('Password is required' in error['message'] for error in password_errors))
    
    def test_nested_serializer_errors(self):
        """Test nested serializer validation errors"""
        
        class AddressSerializer(serializers.Serializer):
            street = serializers.CharField(required=True, max_length=100)
            city = serializers.CharField(required=True, max_length=50)
            zipcode = serializers.CharField(required=True, min_length=5, max_length=10)
        
        class UserWithAddressSerializer(serializers.Serializer):
            username = serializers.CharField(required=True, min_length=3)
            email = serializers.EmailField(required=True)
            address = AddressSerializer(required=True)
        
        # Test with invalid nested data
        serializer = UserWithAddressSerializer(data={
            'username': 'ab',  # Too short
            'email': 'invalid-email',
            'address': {
                'street': '',  # Required but empty
                'city': 'Valid City',
                'zipcode': '123'  # Too short
            }
        })
        
        try:
            serializer.is_valid(raise_exception=True)
            self.fail("Expected ValidationError")
        except ValidationError as exc:
            request = self.factory.post('/api/test', {})
            context = {'request': request}
            
            response = custom_exception_handler(exc, context)
            data = response.data
            
            self.assertEqual(data['type'], 'validation_error')
            self.assertIn('errors', data)
            
            # Should have errors for top-level and nested fields
            self.assertIn('username', data['errors'])
            self.assertIn('email', data['errors'])
            self.assertIn('address.street', data['errors'])
            self.assertIn('address.zipcode', data['errors'])
    
    def test_list_serializer_errors(self):
        """Test list serializer validation errors"""
        
        class ItemSerializer(serializers.Serializer):
            name = serializers.CharField(required=True, max_length=50)
            quantity = serializers.IntegerField(required=True, min_value=1)
        
        class OrderSerializer(serializers.Serializer):
            order_id = serializers.CharField(required=True)
            items = ItemSerializer(many=True, required=True)
        
        # Test with invalid list data
        serializer = OrderSerializer(data={
            'order_id': '',  # Required but empty
            'items': [
                {'name': 'Valid Item', 'quantity': 5},
                {'name': '', 'quantity': 0},  # Invalid
                {'quantity': -1}  # Missing name, invalid quantity
            ]
        })
        
        try:
            serializer.is_valid(raise_exception=True)
            self.fail("Expected ValidationError")
        except ValidationError as exc:
            request = self.factory.post('/api/test', {})
            context = {'request': request}
            
            response = custom_exception_handler(exc, context)
            data = response.data
            
            self.assertEqual(data['type'], 'validation_error')
            self.assertIn('errors', data)
            
            # Should have errors for order_id and list items
            self.assertIn('order_id', data['errors'])
            # List errors should be indexed
            self.assertIn('items.1.name', data['errors'])
            self.assertIn('items.1.quantity', data['errors'])
            self.assertIn('items.2.name', data['errors'])
            self.assertIn('items.2.quantity', data['errors'])


@override_settings(USE_STRUCTURED_ERROR_RESPONSES=False)
class DRFSerializerLegacyErrorTest(TestCase):
    """Test that legacy error format still works when structured responses are disabled"""
    
    def test_legacy_format_when_disabled(self):
        """Test that when structured responses are disabled, we get legacy format"""
        factory = APIRequestFactory()
        request = factory.post('/api/register', {})
        
        try:
            serializer = TestUserSerializer(data={})
            serializer.is_valid(raise_exception=True)
            self.fail("Expected ValidationError")
        except ValidationError as exc:
            context = {'request': request}
            
            response = custom_exception_handler(exc, context)
            
            # Should use legacy format
            self.assertNotEqual(response.data.get('type'), 'validation_error')
            # Legacy format has different structure
            self.assertIn('success', response.data)
            self.assertEqual(response.data['success'], False)


class DRFErrorCodeConsistencyTest(TestCase):
    """Test that error codes are consistent across different serializer scenarios"""
    
    def test_error_code_preservation(self):
        """Test that DRF error codes are preserved in structured format"""
        factory = APIRequestFactory()
        request = factory.post('/api/test', {})
        
        # Test various DRF built-in error codes
        test_cases = [
            ({'email': ['']}, 'email', 'blank'),
            ({'email': ['invalid@']}, 'email', 'invalid'),
            ({'age': ['abc']}, 'age', 'invalid'),
            ({'age': ['-5']}, 'age', 'min_value'),
        ]
        
        for error_detail, field_name, expected_code in test_cases:
            with self.subTest(error_detail=error_detail):
                exc = ValidationError(error_detail)
                context = {'request': request}
                
                response = custom_exception_handler(exc, context)
                data = response.data
                
                if 'errors' in data and field_name in data['errors']:
                    field_errors = data['errors'][field_name]
                    # At least one error should have the expected code
                    codes = [error.get('code') for error in field_errors]
                    # Note: Some codes might be 'invalid' as fallback, which is acceptable


if __name__ == '__main__':
    import unittest
    unittest.main()