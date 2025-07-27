"""
Tests for Generic (Non-Field) Errors with Title and Description

This test file verifies that generic errors not tied to specific fields
properly include title and description data in the structured response.
"""

from django.test import TestCase, override_settings
from rest_framework import serializers, status
from rest_framework.test import APIRequestFactory
from rest_framework.exceptions import ValidationError

from common.custom_exceptions.custom_exception import CustomException
from common.response.response_information_codes.error_code import ErrorCode
from common.exception_handling.custom_exception_handler import custom_exception_handler


class GenericErrorTest(TestCase):
    """Test generic errors with title and description"""

    def setUp(self):
        self.factory = APIRequestFactory()

    def _get_mock_context(self, path="/api/test"):
        """Helper to create mock context"""
        return {
            "request": type("MockRequest", (), {"get_full_path": lambda self: path})()
        }

    def test_drf_non_field_error_single(self):
        """Test single DRF non-field error becomes generic error with title and detail"""

        # Create a ValidationError with non-field error
        from rest_framework.fields import empty

        exc = ValidationError(
            {"non_field_errors": ["Start date cannot be after end date."]}
        )
        context = self._get_mock_context("/api/v1/reports")

        response = custom_exception_handler(exc, context)
        data = response.data

        # Verify it's a generic error (no errors field)
        self.assertEqual(data["type"], "validation_error")
        self.assertEqual(data["status"], 400)
        self.assertIn("title", data)
        self.assertIn("detail", data)
        self.assertNotIn("errors", data)  # No field-specific errors

        # Verify title and detail content
        self.assertEqual(data["title"], "Validation Error")
        self.assertEqual(data["detail"], "Start date cannot be after end date.")
        self.assertEqual(data["instance"], "/api/v1/reports")

    def test_drf_non_field_error_multiple(self):
        """Test multiple DRF non-field errors get combined into single generic error"""

        # Create ValidationError with multiple non-field errors
        errors = [
            "Enterprise projects require a minimum budget of $1,000",
            "Projects cannot exceed 365 days duration",
            "High-budget projects must have a minimum duration of 30 days",
        ]
        exc = ValidationError({"non_field_errors": errors})
        context = self._get_mock_context("/api/v1/projects")

        response = custom_exception_handler(exc, context)
        data = response.data

        # Verify it's a generic error with multiple errors
        self.assertEqual(data["type"], "validation_error")
        self.assertIn("title", data)
        self.assertIn("detail", data)
        self.assertIn("errors", data)

        # Verify multiple errors structure
        self.assertEqual(data["title"], "Multiple Issues Found")
        self.assertEqual(
            data["detail"], "Multiple issues were identified with your request."
        )
        self.assertIn("general", data["errors"])
        self.assertEqual(len(data["errors"]["general"]), 3)

        # Verify each error is properly structured
        for i, error_item in enumerate(data["errors"]["general"]):
            self.assertEqual(error_item["title"], "Validation Error")
            self.assertEqual(error_item["detail"], errors[i])
            self.assertEqual(error_item["code"], "validation_error")

    def test_business_logic_generic_error(self):
        """Test custom business logic error with title and description"""

        try:
            raise CustomException.business_logic_error(
                title="Insufficient Funds",
                detail="Your account balance is $50.00, but this transaction requires $75.00. Please add funds to your account.",
                code=ErrorCode.NOT_ENOUGH_BALANCE_LEFT,
                instance="/api/v1/payments",
                extra_data={"current_balance": 50.0, "required_amount": 75.0},
            )
        except CustomException as exc:
            context = self._get_mock_context("/api/v1/payments")
            response = custom_exception_handler(exc, context)
            data = response.data

            # Verify generic error structure
            self.assertEqual(data["type"], "business_logic_error")
            self.assertEqual(data["status"], 400)
            self.assertEqual(data["title"], "Insufficient Funds")
            self.assertIn("Your account balance is $50.00", data["detail"])
            self.assertEqual(data["instance"], "/api/v1/payments")
            self.assertEqual(data["response_code"], "ERR_NOT_ENOUGH_BALANCE_LEFT")

            # Verify extra data is included
            self.assertEqual(data["current_balance"], 50.0)
            self.assertEqual(data["required_amount"], 75.0)

            # Verify no field errors
            self.assertNotIn("errors", data)

    def test_authentication_generic_error(self):
        """Test authentication error with title and description"""

        try:
            raise CustomException.authentication_error(
                title="Session Expired",
                detail="Your authentication token has expired. Please log in again to continue.",
                instance="/api/v1/protected",
            )
        except CustomException as exc:
            context = self._get_mock_context("/api/v1/protected")
            response = custom_exception_handler(exc, context)
            data = response.data

            # Verify authentication error structure
            self.assertEqual(data["type"], "authentication_error")
            self.assertEqual(data["status"], 401)
            self.assertEqual(data["title"], "Session Expired")
            self.assertEqual(
                data["detail"],
                "Your authentication token has expired. Please log in again to continue.",
            )
            self.assertEqual(data["instance"], "/api/v1/protected")
            self.assertNotIn("errors", data)

    def test_authorization_generic_error(self):
        """Test authorization error with title and description"""

        try:
            raise CustomException.authorization_error(
                title="Insufficient Permissions",
                detail="You need administrator privileges to delete resources. Please contact your system administrator.",
                instance="/api/v1/users",
            )
        except CustomException as exc:
            context = self._get_mock_context("/api/v1/users")
            response = custom_exception_handler(exc, context)
            data = response.data

            # Verify authorization error structure
            self.assertEqual(data["type"], "authorization_error")
            self.assertEqual(data["status"], 403)
            self.assertEqual(data["title"], "Insufficient Permissions")
            self.assertIn("administrator privileges", data["detail"])
            self.assertEqual(data["instance"], "/api/v1/users")
            self.assertNotIn("errors", data)

    def test_system_maintenance_generic_error(self):
        """Test system maintenance error with rich title and description"""

        try:
            raise CustomException.business_logic_error(
                title="System Maintenance in Progress",
                detail="Our systems are currently undergoing scheduled maintenance. Please try again in 30 minutes.",
                code=ErrorCode.AN_ERROR_OCCURED,
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                instance="/api/v1/system",
                extra_data={
                    "maintenance_type": "scheduled",
                    "estimated_completion": "2024-01-01T15:30:00Z",
                },
            )
        except CustomException as exc:
            context = self._get_mock_context("/api/v1/system")
            response = custom_exception_handler(exc, context)
            data = response.data

            # Verify system error structure
            self.assertEqual(data["type"], "business_logic_error")
            self.assertEqual(data["status"], 503)
            self.assertEqual(data["title"], "System Maintenance in Progress")
            self.assertIn("scheduled maintenance", data["detail"])
            self.assertEqual(data["maintenance_type"], "scheduled")
            self.assertEqual(data["estimated_completion"], "2024-01-01T15:30:00Z")
            self.assertNotIn("errors", data)

    def test_subscription_conflict_generic_error(self):
        """Test subscription conflict with title, description and suggested actions"""

        try:
            raise CustomException.business_logic_error(
                title="Active Subscription Exists",
                detail="You already have an active subscription. To change your plan, please use the upgrade option or cancel your current subscription first.",
                code=ErrorCode.ACTIVE_SUBSCRIPTION_EXISTS,
                status_code=status.HTTP_409_CONFLICT,
                instance="/api/v1/subscriptions",
                extra_data={
                    "existing_subscription": {"id": 12345, "plan": "standard"},
                    "suggested_actions": ["upgrade", "cancel_current"],
                },
            )
        except CustomException as exc:
            context = self._get_mock_context("/api/v1/subscriptions")
            response = custom_exception_handler(exc, context)
            data = response.data

            # Verify subscription conflict structure
            self.assertEqual(data["type"], "business_logic_error")
            self.assertEqual(data["status"], 409)
            self.assertEqual(data["title"], "Active Subscription Exists")
            self.assertIn("active subscription", data["detail"])
            self.assertEqual(data["existing_subscription"]["id"], 12345)
            self.assertEqual(data["suggested_actions"], ["upgrade", "cancel_current"])
            self.assertNotIn("errors", data)


class DRFNonFieldErrorIntegrationTest(TestCase):
    """Test DRF serializer non-field errors integration"""

    def test_serializer_object_level_validation_error(self):
        """Test object-level validation in serializer becomes generic error"""

        class TestSerializer(serializers.Serializer):
            start_date = serializers.DateField(required=True)
            end_date = serializers.DateField(required=True)

            def validate(self, attrs):
                if attrs["start_date"] > attrs["end_date"]:
                    raise ValidationError(
                        "Start date cannot be after end date. Please check your date range."
                    )
                return attrs

        # Test with invalid data
        serializer = TestSerializer(
            data={"start_date": "2024-12-31", "end_date": "2024-01-01"}
        )

        try:
            serializer.is_valid(raise_exception=True)
            self.fail("Expected ValidationError")
        except ValidationError as exc:
            factory = APIRequestFactory()
            request = factory.post("/api/test", {})
            context = {"request": request}

            response = custom_exception_handler(exc, context)
            data = response.data

            # Verify it's a generic error, not field error
            self.assertEqual(data["type"], "validation_error")
            self.assertEqual(data["title"], "Validation Error")
            self.assertEqual(
                data["detail"],
                "Start date cannot be after end date. Please check your date range.",
            )
            self.assertNotIn("errors", data)  # No field-specific errors

    def test_serializer_mixed_field_and_non_field_errors(self):
        """Test that field errors take precedence over non-field errors"""

        class TestSerializer(serializers.Serializer):
            username = serializers.CharField(required=True, min_length=3)
            password = serializers.CharField(required=True, min_length=8)

            def validate_username(self, value):
                if value == "admin":
                    raise serializers.ValidationError("Username is reserved")
                return value

            def validate(self, attrs):
                # This will only be called if field validations pass
                raise ValidationError("Terms must be accepted")

        # Test with field validation errors (should not reach object validation)
        serializer = TestSerializer(
            data={
                "username": "admin",  # Will fail field validation
                "password": "123",  # Will fail field validation
            }
        )

        try:
            serializer.is_valid(raise_exception=True)
            self.fail("Expected ValidationError")
        except ValidationError as exc:
            factory = APIRequestFactory()
            request = factory.post("/api/test", {})
            context = {"request": request}

            response = custom_exception_handler(exc, context)
            data = response.data

            # Should have field errors, not generic error
            self.assertEqual(data["type"], "validation_error")
            self.assertIn("errors", data)
            self.assertIn("username", data["errors"])
            self.assertIn("password", data["errors"])

            # Should have generic title/detail for field errors
            # Since there are multiple field errors, expect plural form
            self.assertEqual(data["title"], "Validation Errors")
            self.assertEqual(data["detail"], "Multiple fields have validation errors.")


class ErrorResponseStructureTest(TestCase):
    """Test that generic errors follow consistent structure"""

    def test_generic_error_required_fields(self):
        """Test that all generic errors have required fields"""

        error_scenarios = [
            # (exception_creator, expected_type)
            (
                lambda: CustomException.business_logic_error(
                    title="Test Error", detail="Test detail"
                ),
                "business_logic_error",
            ),
            (
                lambda: CustomException.authentication_error(
                    title="Auth Error", detail="Auth detail"
                ),
                "authentication_error",
            ),
            (
                lambda: CustomException.authorization_error(
                    title="Authz Error", detail="Authz detail"
                ),
                "authorization_error",
            ),
            (
                lambda: CustomException.not_found_error(
                    title="Not Found", detail="Resource not found"
                ),
                "not_found_error",
            ),
        ]

        factory = APIRequestFactory()
        context = {"request": factory.get("/api/test")}

        for create_exception, expected_type in error_scenarios:
            with self.subTest(expected_type=expected_type):
                try:
                    raise create_exception()
                except CustomException as exc:
                    response = custom_exception_handler(exc, context)
                    data = response.data

                    # Verify required fields for generic errors
                    required_fields = ["type", "status", "title", "detail"]
                    for field in required_fields:
                        self.assertIn(
                            field, data, f"Missing {field} in {expected_type}"
                        )

                    # Verify correct type
                    self.assertEqual(data["type"], expected_type)

                    # Verify no field errors for generic errors
                    self.assertNotIn("errors", data)

                    # Verify title and detail are not empty
                    self.assertTrue(data["title"].strip())
                    self.assertTrue(data["detail"].strip())

    def test_generic_error_optional_fields(self):
        """Test that generic errors can include optional fields"""

        try:
            raise CustomException.business_logic_error(
                title="Rich Error",
                detail="Detailed description",
                code=ErrorCode.NOT_ENOUGH_BALANCE_LEFT,
                instance="/api/v1/test",
                extra_data={
                    "custom_field": "custom_value",
                    "numeric_field": 42,
                    "array_field": [1, 2, 3],
                },
            )
        except CustomException as exc:
            factory = APIRequestFactory()
            context = {"request": factory.get("/api/test")}

            response = custom_exception_handler(exc, context)
            data = response.data

            # Verify optional fields are included
            self.assertEqual(data["response_code"], "ERR_NOT_ENOUGH_BALANCE_LEFT")
            self.assertEqual(data["instance"], "/api/v1/test")
            self.assertEqual(data["custom_field"], "custom_value")
            self.assertEqual(data["numeric_field"], 42)
            self.assertEqual(data["array_field"], [1, 2, 3])

    def test_title_and_detail_internationalization(self):
        """Test that title and detail support internationalization"""

        from django.utils.translation import gettext_lazy as _

        try:
            raise CustomException.business_logic_error(
                title=_("Internationalized Title"),
                detail=_("This is an internationalized error detail message."),
                instance="/api/v1/i18n",
            )
        except CustomException as exc:
            factory = APIRequestFactory()
            context = {"request": factory.get("/api/test")}

            response = custom_exception_handler(exc, context)
            data = response.data

            # Verify internationalized strings are rendered
            self.assertEqual(data["title"], "Internationalized Title")
            self.assertEqual(
                data["detail"], "This is an internationalized error detail message."
            )


if __name__ == "__main__":
    import unittest

    unittest.main()
