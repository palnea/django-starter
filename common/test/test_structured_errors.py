"""
Tests for structured error response system.

This test file demonstrates the new structured error responses and ensures they work correctly.
"""

import json
from django.test import TestCase, override_settings
from django.utils.translation import gettext_lazy as _
from rest_framework import status
from rest_framework.test import APITestCase
from rest_framework.response import Response

from common.custom_exceptions.custom_exception import CustomException
from common.response.response_information_codes.error_code import ErrorCode
from common.response.structured_error_response import (
    StructuredErrorResponse, 
    FieldError, 
    GeneralError,
    StructuredErrorType
)


class StructuredErrorResponseTest(TestCase):
    """Test the StructuredErrorResponse class functionality"""

    def test_field_validation_error(self):
        """Test field-based validation errors"""
        field_errors = [
            FieldError(field="email", code="invalid_format", message="Email format is invalid"),
            FieldError(field="password", code="too_short", message="Password is too short")
        ]
        
        response = StructuredErrorResponse.validation_error(
            field_errors=field_errors,
            instance="/api/v1/users/register"
        )
        
        data = response.to_dict()
        
        self.assertEqual(data["type"], "validation_error")
        self.assertEqual(data["status"], 400)
        self.assertIn("title", data)
        self.assertIn("detail", data)
        self.assertEqual(data["instance"], "/api/v1/users/register")
        self.assertIn("errors", data)
        self.assertIn("email", data["errors"])
        self.assertIn("password", data["errors"])

    def test_general_business_logic_error(self):
        """Test general business logic errors"""
        response = StructuredErrorResponse.business_logic_error(
            title="Insufficient Balance",
            detail="Your account balance is $10.50, but this transaction requires $25.00",
            code="insufficient_balance",
            instance="/api/v1/transactions",
            extra_data={
                "current_balance": 10.50,
                "required_amount": 25.00
            }
        )
        
        data = response.to_dict()
        
        self.assertEqual(data["type"], "business_logic_error")
        self.assertEqual(data["status"], 400)
        self.assertEqual(data["title"], "Insufficient Balance")
        self.assertIn("Your account balance", data["detail"])
        self.assertEqual(data["instance"], "/api/v1/transactions")
        self.assertEqual(data["current_balance"], 10.50)
        self.assertEqual(data["required_amount"], 25.00)

    def test_authentication_error(self):
        """Test authentication errors"""
        response = StructuredErrorResponse.authentication_error(
            title="Authentication Failed",
            detail="The provided token has expired",
            instance="/api/v1/protected-endpoint"
        )
        
        data = response.to_dict()
        
        self.assertEqual(data["type"], "authentication_error")
        self.assertEqual(data["status"], 401)
        self.assertEqual(data["title"], "Authentication Failed")
        self.assertEqual(data["detail"], "The provided token has expired")

    def test_authorization_error(self):
        """Test authorization errors"""
        response = StructuredErrorResponse.authorization_error(
            title="Access Denied",
            detail="You need admin privileges to perform this action",
            instance="/api/v1/admin/users"
        )
        
        data = response.to_dict()
        
        self.assertEqual(data["type"], "authorization_error")
        self.assertEqual(data["status"], 403)
        self.assertEqual(data["title"], "Access Denied")
        self.assertEqual(data["detail"], "You need admin privileges to perform this action")


class CustomExceptionTest(TestCase):
    """Test the updated CustomException class with structured error support"""

    def test_validation_error_creation(self):
        """Test creating validation errors using CustomException"""
        with self.assertRaises(CustomException) as context:
            raise CustomException.validation_error(
                field_errors={
                    "email": ["Email format is invalid"],
                    "password": ["Password is too short"]
                },
                title="Validation Failed",
                instance="/api/v1/auth/login"
            )
        
        exc = context.exception
        self.assertTrue(exc.has_field_errors())
        self.assertTrue(exc.is_structured())
        self.assertEqual(exc.title, "Validation Failed")
        self.assertEqual(exc.instance, "/api/v1/auth/login")

    def test_business_logic_error_creation(self):
        """Test creating business logic errors using CustomException"""
        with self.assertRaises(CustomException) as context:
            raise CustomException.business_logic_error(
                title="Insufficient Balance",
                detail="Your account balance is too low",
                code=ErrorCode.NOT_ENOUGH_BALANCE_LEFT,
                instance="/api/v1/transactions",
                extra_data={"balance": 10.50}
            )
        
        exc = context.exception
        self.assertTrue(exc.is_structured())
        self.assertEqual(exc.title, "Insufficient Balance")
        self.assertEqual(exc.extra_data["balance"], 10.50)

    def test_authentication_error_creation(self):
        """Test creating authentication errors using CustomException"""
        with self.assertRaises(CustomException) as context:
            raise CustomException.authentication_error(
                title="Authentication Failed",
                detail="Token has expired",
                instance="/api/v1/protected"
            )
        
        exc = context.exception
        self.assertEqual(exc.status_code, 401)
        self.assertEqual(exc.title, "Authentication Failed")

    def test_not_found_error_creation(self):
        """Test creating not found errors using CustomException"""
        with self.assertRaises(CustomException) as context:
            raise CustomException.not_found_error(
                title="User Not Found",
                detail="User with ID 12345 does not exist",
                instance="/api/v1/users/12345"
            )
        
        exc = context.exception
        self.assertEqual(exc.status_code, 404)
        self.assertEqual(exc.title, "User Not Found")

    def test_backward_compatibility(self):
        """Test that old exception format still works"""
        with self.assertRaises(CustomException) as context:
            raise CustomException(
                detail="User not found",
                code=ErrorCode.NOT_FOUND_ERROR,
                status_code=status.HTTP_404_NOT_FOUND,
                message=_("Content not found!"),
            )
        
        exc = context.exception
        self.assertFalse(exc.is_structured())  # Should not be structured
        self.assertEqual(exc.status_code, 404)
        self.assertEqual(str(exc), "User not found")


@override_settings(USE_STRUCTURED_ERROR_RESPONSES=True)
class StructuredErrorIntegrationTest(APITestCase):
    """Integration tests for structured error responses"""

    def test_drf_validation_error_structure(self):
        """Test that DRF ValidationError gets converted to structured format"""
        # This would require a test view that raises ValidationError
        # For demonstration purposes, we'll test the conversion logic directly
        from rest_framework.exceptions import ValidationError
        from common.exception_handling.custom_exception_handler import create_structured_response_from_validation_error
        
        # Simulate DRF ValidationError
        validation_error = ValidationError({
            "email": ["This field is required."],
            "password": ["This field is required."]
        })
        
        context = {
            "request": type('obj', (object,), {
                'get_full_path': lambda: '/api/v1/auth/login'
            })()
        }
        
        response = create_structured_response_from_validation_error(validation_error, context)
        data = response.data
        
        self.assertEqual(data["type"], "validation_error")
        self.assertEqual(data["status"], 400)
        self.assertIn("errors", data)
        self.assertIn("email", data["errors"])
        self.assertIn("password", data["errors"])

    def test_custom_exception_structured_response(self):
        """Test that CustomException with structured data generates proper response"""
        from common.exception_handling.custom_exception_handler import create_structured_response_from_custom_exception
        
        exc = CustomException.validation_error(
            field_errors={
                "email": ["Invalid email format"],
                "password": ["Password too short"]
            },
            title="Login Failed",
            instance="/api/v1/auth/login"
        )
        
        context = {
            "request": type('obj', (object,), {
                'get_full_path': lambda: '/api/v1/auth/login'
            })()
        }
        
        response = create_structured_response_from_custom_exception(exc, context)
        data = response.data
        
        self.assertEqual(data["type"], "validation_error")
        self.assertEqual(data["title"], "Login Failed")
        self.assertIn("errors", data)
        self.assertIn("email", data["errors"])
        self.assertIn("password", data["errors"])


class ErrorResponseFormatTest(TestCase):
    """Test specific error response formats for client consumption"""

    def test_login_validation_error_format(self):
        """Test the exact format expected for login validation errors"""
        field_errors = [
            FieldError(field="email", code="invalid_format", message="The email format is incorrect"),
            FieldError(field="password", code="required", message="Password is required")
        ]
        
        response = StructuredErrorResponse.validation_error(
            field_errors=field_errors,
            instance="/api/v1/auth/login"
        )
        
        data = response.to_dict()
        
        # Verify the exact format clients expect
        expected_structure = {
            "type": "validation_error",
            "status": 400,
            "title": str(_("Validation Error")),
            "detail": str(_("The request data is invalid.")),
            "instance": "/api/v1/auth/login",
            "errors": {
                "email": [
                    {
                        "code": "invalid_format",
                        "message": "The email format is incorrect",
                        "value": None
                    }
                ],
                "password": [
                    {
                        "code": "required",
                        "message": "Password is required",
                        "value": None
                    }
                ]
            }
        }
        
        # Check structure matches
        for key, value in expected_structure.items():
            if key != "errors":
                self.assertEqual(data[key], value, f"Mismatch in {key}")
        
        # Check errors structure
        self.assertIn("email", data["errors"])
        self.assertIn("password", data["errors"])
        self.assertEqual(len(data["errors"]["email"]), 1)
        self.assertEqual(len(data["errors"]["password"]), 1)

    def test_business_logic_error_format(self):
        """Test the exact format expected for business logic errors"""
        response = StructuredErrorResponse.business_logic_error(
            title="Insufficient Balance",
            detail="Your account balance is $10.50, but this transaction requires $25.00",
            code="insufficient_balance",
            instance="/api/v1/transactions",
            extra_data={
                "balance": 10.50,
                "required_amount": 25.00
            }
        )
        
        data = response.to_dict()
        
        # Verify the exact format clients expect
        expected_keys = ["type", "status", "title", "detail", "instance", "balance", "required_amount"]
        
        for key in expected_keys:
            self.assertIn(key, data, f"Missing key: {key}")
        
        self.assertEqual(data["type"], "business_logic_error")
        self.assertEqual(data["title"], "Insufficient Balance")
        self.assertIn("$10.50", data["detail"])
        self.assertIn("$25.00", data["detail"])
        self.assertEqual(data["balance"], 10.50)
        self.assertEqual(data["required_amount"], 25.00)


if __name__ == '__main__':
    import unittest
    unittest.main()