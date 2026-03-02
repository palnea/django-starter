"""
Tests for structured error response system.

This test file demonstrates the new structured error responses and ensures they work correctly.
"""

from django.test import TestCase
from django.utils.translation import gettext_lazy as _
from rest_framework import status
from rest_framework.test import APITestCase

from common.custom_exceptions.custom_exception import CustomException
from common.response.response_information_codes.error_code import ErrorCode
from common.response.structured_error_response import (
    StructuredErrorResponse,
    FieldError,
    StructuredErrorType,
    GeneralError,
)


class StructuredErrorResponseTest(TestCase):
    """Test the StructuredErrorResponse class functionality."""

    def test_field_validation_error(self):
        """Test field-based validation errors."""
        field_errors = [
            FieldError(
                field="email", code="invalid_format", message="Email format is invalid"
            ),
            FieldError(
                field="password", code="too_short", message="Password is too short"
            ),
        ]

        response = StructuredErrorResponse(
            error_type=StructuredErrorType.VALIDATION_ERROR,
            status_code=400,
            field_errors=field_errors,
            instance="/api/test",
        )

        data = response.to_dict()

        # Check basic structure
        self.assertEqual(data["type"], "validation_error")
        self.assertEqual(data["status"], 400)
        self.assertEqual(data["instance"], "/api/test")

        # Check field errors
        self.assertIn("errors", data)
        self.assertIn("email", data["errors"])
        self.assertIn("password", data["errors"])

        # Check field error structure
        email_error = data["errors"]["email"][0]
        self.assertEqual(email_error["code"], "invalid_format")
        self.assertEqual(email_error["message"], "Email format is invalid")

    def test_general_business_logic_error(self):
        """Test general business logic errors."""
        general_error = GeneralError(
            title="Insufficient Balance",
            detail="Your account balance is too low",
            code="BALANCE_LOW",
        )

        response = StructuredErrorResponse(
            error_type=StructuredErrorType.BUSINESS_LOGIC_ERROR,
            status_code=400,
            general_errors=[general_error],
            instance="/api/transaction",
        )

        data = response.to_dict()

        # Check basic structure
        self.assertEqual(data["type"], "business_logic_error")
        self.assertEqual(data["status"], 400)
        self.assertEqual(data["title"], "Insufficient Balance")
        self.assertEqual(data["detail"], "Your account balance is too low")
        self.assertEqual(data["response_code"], "BALANCE_LOW")

    def test_multiple_general_errors(self):
        """Test multiple general errors."""
        general_errors = [
            GeneralError(title="Error 1", detail="First error", code="ERR_1"),
            GeneralError(title="Error 2", detail="Second error", code="ERR_2"),
        ]

        response = StructuredErrorResponse(
            error_type=StructuredErrorType.BUSINESS_LOGIC_ERROR,
            status_code=400,
            general_errors=general_errors,
            instance="/api/test",
        )

        data = response.to_dict()

        # Check basic structure
        self.assertEqual(data["type"], "business_logic_error")
        self.assertEqual(data["status"], 400)
        self.assertEqual(data["title"], "Multiple Issues Found")
        self.assertEqual(
            data["detail"], "Multiple issues were identified with your request."
        )

        # Check general errors array
        self.assertIn("errors", data)
        self.assertIn("general", data["errors"])
        self.assertEqual(len(data["errors"]["general"]), 2)

        # Check first error
        first_error = data["errors"]["general"][0]
        self.assertEqual(first_error["title"], "Error 1")
        self.assertEqual(first_error["detail"], "First error")
        self.assertEqual(first_error["code"], "ERR_1")

    def test_mixed_field_and_general_errors(self):
        """Test combination of field and general errors."""
        field_errors = [
            FieldError(field="email", code="invalid", message="Invalid email")
        ]
        general_errors = [
            GeneralError(
                title="System Warning", detail="Maintenance mode active", code="MAINT"
            )
        ]

        response = StructuredErrorResponse(
            error_type=StructuredErrorType.VALIDATION_ERROR,
            status_code=400,
            field_errors=field_errors,
            general_errors=general_errors,
            instance="/api/test",
        )

        data = response.to_dict()

        # Should use the single general error for title/detail
        self.assertEqual(data["title"], "System Warning")
        self.assertEqual(data["detail"], "Maintenance mode active")
        self.assertEqual(data["response_code"], "MAINT")

        # Should still have field errors
        self.assertIn("errors", data)
        self.assertIn("email", data["errors"])

    def test_authentication_error(self):
        """Test authentication errors."""
        general_error = GeneralError(
            title="Invalid Token",
            detail="The provided authentication token is invalid",
            code="AUTH_INVALID",
        )

        response = StructuredErrorResponse(
            error_type=StructuredErrorType.AUTHENTICATION_ERROR,
            status_code=401,
            general_errors=[general_error],
        )

        data = response.to_dict()

        self.assertEqual(data["type"], "authentication_error")
        self.assertEqual(data["status"], 401)
        self.assertEqual(data["title"], "Invalid Token")

    def test_authorization_error(self):
        """Test authorization errors."""
        general_error = GeneralError(
            title="Access Denied",
            detail="You don't have permission to access this resource",
            code="PERM_DENIED",
        )

        response = StructuredErrorResponse(
            error_type=StructuredErrorType.AUTHORIZATION_ERROR,
            status_code=403,
            general_errors=[general_error],
        )

        data = response.to_dict()

        self.assertEqual(data["type"], "authorization_error")
        self.assertEqual(data["status"], 403)
        self.assertEqual(data["title"], "Access Denied")


class CustomExceptionTest(TestCase):
    """Test the updated CustomException class with structured error support."""

    def test_validation_error_creation(self):
        """Test creating validation errors using CustomException."""
        with self.assertRaises(CustomException) as context:
            raise CustomException.validation_error(
                field_errors={
                    "email": ["Email format is invalid"],
                    "password": ["Password is too short"],
                },
                title="Validation Failed",
                instance="/api/v1/auth/login",
            )

        exc = context.exception
        self.assertTrue(exc.has_field_errors())
        self.assertEqual(exc.title, "Validation Failed")
        self.assertEqual(exc.instance, "/api/v1/auth/login")

    def test_business_logic_error_creation(self):
        """Test creating business logic errors using CustomException."""
        with self.assertRaises(CustomException) as context:
            raise CustomException.business_logic_error(
                title="Insufficient Balance",
                detail="Your account balance is too low",
                code=ErrorCode.NOT_ENOUGH_BALANCE_LEFT,
                instance="/api/v1/transactions",
                extra_data={"balance": 10.50},
            )

        exc = context.exception
        self.assertEqual(exc.title, "Insufficient Balance")
        self.assertEqual(exc.extra_data["balance"], 10.50)

    def test_authentication_error_creation(self):
        """Test creating authentication errors using CustomException."""
        with self.assertRaises(CustomException) as context:
            raise CustomException.authentication_error(
                title="Authentication Failed",
                detail="Token has expired",
                instance="/api/v1/protected",
            )

        exc = context.exception
        self.assertEqual(exc.status_code, 401)
        self.assertEqual(exc.title, "Authentication Failed")

    def test_not_found_error_creation(self):
        """Test creating not found errors using CustomException."""
        with self.assertRaises(CustomException) as context:
            raise CustomException.not_found_error(
                title="User Not Found",
                detail="User with ID 12345 does not exist",
                instance="/api/v1/users/12345",
            )

        exc = context.exception
        self.assertEqual(exc.status_code, 404)
        self.assertEqual(exc.title, "User Not Found")

    def test_direct_structured_implementation(self):
        """Test that all CustomExceptions are now structured by default."""
        with self.assertRaises(CustomException) as context:
            raise CustomException(
                detail="User not found",
                code=ErrorCode.NOT_FOUND_ERROR,
                status_code=status.HTTP_404_NOT_FOUND,
                message=_("Content not found!"),
            )

        exc = context.exception
        self.assertIsNotNone(exc.title)
        self.assertEqual(exc.status_code, 404)
        self.assertEqual(str(exc), "User not found")

    def test_multiple_business_logic_errors_creation(self):
        """Test creating multiple business logic errors using CustomException."""
        try:
            raise CustomException.multiple_business_logic_errors(
                errors=[
                    {
                        "title": "Insufficient Funds",
                        "detail": "Your account balance is $50.00, but this transaction requires $75.00.",
                        "code": "insufficient_funds",
                    },
                    {
                        "title": "Daily Limit Exceeded",
                        "detail": "You have exceeded your daily transaction limit of $500.00.",
                        "code": "daily_limit_exceeded",
                    },
                ],
                instance="/api/v1/payments",
            )
        except CustomException as exc:
            self.assertIsNotNone(exc.title)
            self.assertEqual(exc.title, "Multiple Issues Found")
            self.assertIn("multiple_general_errors", exc.extra_data)
            self.assertEqual(len(exc.extra_data["multiple_general_errors"]), 2)
            self.assertEqual(exc.status_code, 400)
            self.assertEqual(exc.error_type, "business_logic_error")


class StructuredErrorIntegrationTest(APITestCase):
    """Integration tests for structured error responses."""

    def test_drf_validation_error_structure(self):
        """Test that DRF ValidationError gets converted to structured format."""
        # This would require a test view that raises ValidationError
        # For demonstration purposes, we'll test the conversion logic directly
        from rest_framework.exceptions import ValidationError
        from common.exception_handling.custom_exception_handler import (
            create_structured_response_from_validation_error,
        )

        # Simulate DRF ValidationError
        validation_error = ValidationError(
            {
                "email": ["This field is required."],
                "password": ["This field is required."],
            }
        )

        context = {
            "request": type(
                "obj", (object,), {"get_full_path": lambda self: "/api/v1/auth/login"}
            )()
        }

        response = create_structured_response_from_validation_error(
            validation_error, context
        )
        data = response.data

        self.assertEqual(data["type"], "validation_error")
        self.assertEqual(data["status"], 400)
        self.assertIn("errors", data)
        self.assertIn("email", data["errors"])
        self.assertIn("password", data["errors"])

    def test_custom_exception_structured_response(self):
        """Test that CustomException with structured data generates proper response."""
        from common.exception_handling.custom_exception_handler import (
            create_structured_response_from_custom_exception,
        )

        exc = CustomException.validation_error(
            field_errors={
                "email": ["Invalid email format"],
                "password": ["Password too short"],
            },
            title="Login Failed",
            instance="/api/v1/auth/login",
        )

        context = {
            "request": type(
                "obj", (object,), {"get_full_path": lambda self: "/api/v1/auth/login"}
            )()
        }

        response = create_structured_response_from_custom_exception(exc, context)
        data = response.data

        self.assertEqual(data["type"], "validation_error")
        self.assertEqual(data["title"], "Login Failed")
        self.assertIn("errors", data)
        self.assertIn("email", data["errors"])
        self.assertIn("password", data["errors"])


    def test_custom_exception_handled_before_api_exception(self):
        """CustomException (subclass of APIException) must be handled by the CustomException branch of
        custom_exception_handler, not the generic APIException branch. This ensures the structured error format
        with response_code starting with 'ERR_' is returned.
        """
        from rest_framework.exceptions import APIException
        from common.exception_handling.custom_exception_handler import (
            custom_exception_handler,
        )

        exc = CustomException.business_logic_error(
            title="Already Inactive",
            detail="User is already deactivated.",
        )

        # Sanity check: CustomException IS an APIException subclass
        self.assertIsInstance(exc, APIException)

        context = {
            "request": type(
                "obj",
                (object,),
                {"get_full_path": lambda self: "/api/v1/users/1/deactivate"},
            )()
        }

        response = custom_exception_handler(exc, context)
        data = response.data

        # Must use the structured CustomException format
        self.assertEqual(data["type"], "business_logic_error")
        self.assertEqual(data["title"], "Already Inactive")
        self.assertEqual(data["detail"], "User is already deactivated.")
        self.assertTrue(
            data["response_code"].startswith("ERR_"),
            f"Expected response_code starting with 'ERR_', got '{data['response_code']}'",
        )


class ErrorResponseFormatTest(TestCase):
    """Test specific error response formats for client consumption."""

    def test_login_validation_error_format(self):
        """Test the exact format expected for login validation errors."""
        field_errors = [
            FieldError(
                field="email",
                code="invalid_format",
                message="The email format is incorrect",
            ),
            FieldError(
                field="password", code="required", message="Password is required"
            ),
        ]

        from common.response.structured_error_response import GeneralError

        general_error = GeneralError(
            title=_("Validation Error"),
            detail=_("The request data is invalid."),
            code="validation_error",
        )

        response = StructuredErrorResponse(
            error_type=StructuredErrorType.VALIDATION_ERROR,
            status_code=400,
            field_errors=field_errors,
            general_errors=[general_error],
            instance="/api/v1/auth/login",
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
                        "value": None,
                    }
                ],
                "password": [
                    {
                        "code": "required",
                        "message": "Password is required",
                        "value": None,
                    }
                ],
            },
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
        """Test the exact format expected for business logic errors."""
        from common.response.response_information_codes.general_error_code import (
            GeneralErrorCode,
        )

        general_error = GeneralError(
            title="Insufficient Balance",
            detail="Your account balance is $10.50, but this transaction requires $25.00",
            code=GeneralErrorCode.INSUFFICIENT_FUNDS,
        )

        response = StructuredErrorResponse(
            error_type=StructuredErrorType.BUSINESS_LOGIC_ERROR,
            status_code=400,
            general_errors=[general_error],
            instance="/api/v1/transactions",
            extra_data={"balance": 10.50, "required_amount": 25.00},
        )

        data = response.to_dict()

        self.assertEqual(data["type"], "business_logic_error")
        self.assertEqual(data["status"], 400)
        self.assertEqual(data["title"], "Insufficient Balance")
        self.assertIn("Your account balance", data["detail"])
        self.assertEqual(data["instance"], "/api/v1/transactions")
        self.assertEqual(data["balance"], 10.50)
        self.assertEqual(data["required_amount"], 25.00)
