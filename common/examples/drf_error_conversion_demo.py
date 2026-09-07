"""
Demo: DRF Validation Error Conversion to Structured Format

This file demonstrates how Django REST Framework serializer validation errors
are automatically converted to our structured error response format.
"""

from rest_framework import serializers
from rest_framework.exceptions import ValidationError
from django.contrib.auth.models import User

from common.exception_handling.custom_exception_handler import custom_exception_handler


# Example 1: Simple Field Validation Errors
def demo_simple_field_errors():
    """Demonstrates basic field validation error conversion"""

    class LoginSerializer(serializers.Serializer):
        email = serializers.EmailField(required=True)
        password = serializers.CharField(required=True, min_length=8)

    # This will trigger field validation errors
    serializer = LoginSerializer(data={"email": "invalid-email", "password": "123"})

    try:
        serializer.is_valid(raise_exception=True)
    except ValidationError as exc:
        # The exception handler converts this to structured format
        response = custom_exception_handler(
            exc,
            {
                "request": type(
                    "MockRequest", (), {"get_full_path": lambda: "/api/auth/login"}
                )()
            },
        )

        """
        Response will be:
        {
            "type": "validation_error",
            "status": 400,
            "title": "Validation Error",
            "detail": "The request data is invalid.",
            "instance": "/api/auth/login",
            "errors": {
                "email": [
                    {
                        "code": "invalid",
                        "message": "Enter a valid email address."
                    }
                ],
                "password": [
                    {
                        "code": "min_length",
                        "message": "Ensure this field has at least 8 characters."
                    }
                ]
            }
        }
        """

        return response.data


# Example 2: Custom Field Validation with Error Codes
def demo_custom_field_validation():
    """Demonstrates custom field validation with specific error codes"""

    class UserRegistrationSerializer(serializers.ModelSerializer):
        class Meta:
            model = User
            fields = ["username", "email", "password"]

        def validate_username(self, value):
            if len(value) < 3:
                raise serializers.ValidationError(
                    "Username must be at least 3 characters long",
                    code="username_too_short",
                )
            if value.lower() == "admin":
                raise serializers.ValidationError(
                    "Username 'admin' is reserved", code="reserved_username"
                )
            return value

        def validate_email(self, value):
            if User.objects.filter(email=value).exists():
                raise serializers.ValidationError(
                    "A user with this email already exists", code="email_exists"
                )
            return value

    # This will trigger custom validation errors
    serializer = UserRegistrationSerializer(
        data={
            "username": "ab",  # Too short
            "email": "existing@example.com",  # Assume this exists
            "password": "validpassword123",
        }
    )

    try:
        serializer.is_valid(raise_exception=True)
    except ValidationError as exc:
        response = custom_exception_handler(
            exc,
            {
                "request": type(
                    "MockRequest", (), {"get_full_path": lambda: "/api/users/register"}
                )()
            },
        )

        """
        Response will preserve custom error codes:
        {
            "type": "validation_error",
            "status": 400,
            "title": "Validation Error", 
            "detail": "The request data is invalid.",
            "instance": "/api/users/register",
            "errors": {
                "username": [
                    {
                        "code": "username_too_short",
                        "message": "Username must be at least 3 characters long"
                    }
                ],
                "email": [
                    {
                        "code": "email_exists",
                        "message": "A user with this email already exists"
                    }
                ]
            }
        }
        """

        return response.data


# Example 3: Object-level Validation Errors
def demo_object_level_validation():
    """Demonstrates object-level validation error conversion"""

    class PasswordChangeSerializer(serializers.Serializer):
        current_password = serializers.CharField(required=True)
        new_password = serializers.CharField(required=True, min_length=8)
        confirm_password = serializers.CharField(required=True)

        def validate(self, attrs):
            new_password = attrs.get("new_password")
            confirm_password = attrs.get("confirm_password")

            if new_password != confirm_password:
                # Object-level validation error mapped to specific fields
                raise serializers.ValidationError(
                    {
                        "new_password": "New password and confirmation do not match",
                        "confirm_password": "Password confirmation does not match",
                    }
                )

            return attrs

    serializer = PasswordChangeSerializer(
        data={
            "current_password": "oldpass",
            "new_password": "newpass123",
            "confirm_password": "differentpass123",
        }
    )

    try:
        serializer.is_valid(raise_exception=True)
    except ValidationError as exc:
        response = custom_exception_handler(
            exc,
            {
                "request": type(
                    "MockRequest",
                    (),
                    {"get_full_path": lambda: "/api/auth/change-password"},
                )()
            },
        )

        """
        Response will have field-specific errors from object validation:
        {
            "type": "validation_error",
            "status": 400,
            "title": "Validation Error",
            "detail": "The request data is invalid.",
            "instance": "/api/auth/change-password",
            "errors": {
                "new_password": [
                    {
                        "code": "invalid",
                        "message": "New password and confirmation do not match"
                    }
                ],
                "confirm_password": [
                    {
                        "code": "invalid", 
                        "message": "Password confirmation does not match"
                    }
                ]
            }
        }
        """

        return response.data


# Example 4: Non-field Errors (General Validation Errors)
def demo_non_field_errors():
    """Demonstrates non-field errors as general errors"""

    class ProfileSerializer(serializers.Serializer):
        first_name = serializers.CharField(required=True)
        last_name = serializers.CharField(required=True)
        birth_date = serializers.DateField(required=True)

        def validate(self, attrs):
            first_name = attrs.get("first_name")
            last_name = attrs.get("last_name")

            # General validation error not tied to specific field
            if first_name == "Test" and last_name == "User":
                raise serializers.ValidationError(
                    "Test accounts are not allowed in production environment"
                )

            return attrs

    serializer = ProfileSerializer(
        data={"first_name": "Test", "last_name": "User", "birth_date": "1990-01-01"}
    )

    try:
        serializer.is_valid(raise_exception=True)
    except ValidationError as exc:
        response = custom_exception_handler(
            exc,
            {
                "request": type(
                    "MockRequest", (), {"get_full_path": lambda: "/api/profile"}
                )()
            },
        )

        """
        Response will have general error in detail:
        {
            "type": "validation_error",
            "status": 400,
            "title": "Validation Error",
            "detail": "Test accounts are not allowed in production environment",
            "instance": "/api/profile"
        }
        """

        return response.data


# Example 5: Nested Serializer Errors
def demo_nested_serializer_errors():
    """Demonstrates nested serializer validation error conversion"""

    class AddressSerializer(serializers.Serializer):
        street = serializers.CharField(required=True, max_length=100)
        city = serializers.CharField(required=True, max_length=50)
        zipcode = serializers.CharField(required=True, min_length=5, max_length=10)

        def validate_zipcode(self, value):
            if not value.isdigit():
                raise serializers.ValidationError(
                    "Zipcode must contain only digits", code="invalid_zipcode"
                )
            return value

    class UserProfileSerializer(serializers.Serializer):
        username = serializers.CharField(required=True, min_length=3)
        email = serializers.EmailField(required=True)
        address = AddressSerializer(required=True)

    serializer = UserProfileSerializer(
        data={
            "username": "ab",  # Too short
            "email": "invalid-email",
            "address": {
                "street": "",  # Required but empty
                "city": "Valid City",
                "zipcode": "ABC123",  # Invalid zipcode
            },
        }
    )

    try:
        serializer.is_valid(raise_exception=True)
    except ValidationError as exc:
        response = custom_exception_handler(
            exc,
            {
                "request": type(
                    "MockRequest", (), {"get_full_path": lambda: "/api/profile/create"}
                )()
            },
        )

        """
        Response will have nested field errors with dot notation:
        {
            "type": "validation_error",
            "status": 400,
            "title": "Validation Error",
            "detail": "The request data is invalid.",
            "instance": "/api/profile/create",
            "errors": {
                "username": [
                    {
                        "code": "min_length",
                        "message": "Ensure this field has at least 3 characters."
                    }
                ],
                "email": [
                    {
                        "code": "invalid",
                        "message": "Enter a valid email address."
                    }
                ],
                "address.street": [
                    {
                        "code": "blank",
                        "message": "This field may not be blank."
                    }
                ],
                "address.zipcode": [
                    {
                        "code": "invalid_zipcode",
                        "message": "Zipcode must contain only digits"
                    }
                ]
            }
        }
        """

        return response.data


# Example 6: List Serializer Errors
def demo_list_serializer_errors():
    """Demonstrates list serializer validation error conversion"""

    class ItemSerializer(serializers.Serializer):
        name = serializers.CharField(required=True, max_length=50)
        quantity = serializers.IntegerField(required=True, min_value=1)
        price = serializers.DecimalField(
            required=True, max_digits=10, decimal_places=2, min_value=0.01
        )

    class OrderSerializer(serializers.Serializer):
        order_id = serializers.CharField(required=True)
        customer_email = serializers.EmailField(required=True)
        items = ItemSerializer(many=True, required=True)

    serializer = OrderSerializer(
        data={
            "order_id": "",  # Required but empty
            "customer_email": "invalid-email",
            "items": [
                {"name": "Valid Item", "quantity": 5, "price": "19.99"},
                {"name": "", "quantity": 0, "price": "-5.00"},  # Multiple errors
                {"quantity": -1},  # Missing name, invalid quantity
            ],
        }
    )

    try:
        serializer.is_valid(raise_exception=True)
    except ValidationError as exc:
        response = custom_exception_handler(
            exc,
            {
                "request": type(
                    "MockRequest", (), {"get_full_path": lambda: "/api/orders"}
                )()
            },
        )

        """
        Response will have indexed errors for list items:
        {
            "type": "validation_error",
            "status": 400,
            "title": "Validation Error",
            "detail": "The request data is invalid.",
            "instance": "/api/orders",
            "errors": {
                "order_id": [
                    {
                        "code": "blank",
                        "message": "This field may not be blank."
                    }
                ],
                "customer_email": [
                    {
                        "code": "invalid",
                        "message": "Enter a valid email address."
                    }
                ],
                "items.1.name": [
                    {
                        "code": "blank",
                        "message": "This field may not be blank."
                    }
                ],
                "items.1.quantity": [
                    {
                        "code": "min_value",
                        "message": "Ensure this value is greater than or equal to 1."
                    }
                ],
                "items.1.price": [
                    {
                        "code": "min_value",
                        "message": "Ensure this value is greater than or equal to 0.01."
                    }
                ],
                "items.2.name": [
                    {
                        "code": "required",
                        "message": "This field is required."
                    }
                ],
                "items.2.quantity": [
                    {
                        "code": "min_value",
                        "message": "Ensure this value is greater than or equal to 1."
                    }
                ]
            }
        }
        """

        return response.data


# Summary of Benefits
"""
Key Benefits of DRF Error Conversion to Structured Format:

1. **Consistency**: All validation errors follow the same structured format
2. **Field Mapping**: Clients know exactly which field has which error
3. **Error Codes**: Preserved custom error codes for programmatic handling
4. **Nested Support**: Handles nested serializers with dot notation (address.street)
5. **List Support**: Handles list serializers with indexed notation (items.1.name)
6. **Non-field Errors**: General validation errors in detail field
7. **Type Safety**: Always returns 'validation_error' type for validation issues
8. **Instance Context**: Includes request path for debugging

Client Usage Example:

```javascript
// Frontend can easily handle structured errors
fetch('/api/users/register', {
    method: 'POST',
    body: JSON.stringify(userData)
})
.then(response => response.json())
.then(data => {
    if (data.type === 'validation_error') {
        // Handle field-specific errors
        if (data.errors) {
            Object.keys(data.errors).forEach(fieldName => {
                const fieldErrors = data.errors[fieldName];
                fieldErrors.forEach(error => {
                    displayFieldError(fieldName, error.message, error.code);
                });
            });
        }
        
        // Handle general error
        if (data.detail && !data.errors) {
            displayGeneralError(data.title, data.detail);
        }
    }
})
.catch(error => {
    console.error('Network error:', error);
});
```

This provides a much better developer experience compared to parsing
inconsistent error formats!
"""
