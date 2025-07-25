"""
Examples of how to use the new structured error response system.

This file demonstrates various patterns for creating structured error responses
that are both field-based and general error responses.
"""

from django.utils.translation import gettext_lazy as _
from rest_framework import status

from common.custom_exceptions.custom_exception import CustomException
from common.response.response_information_codes.error_code import ErrorCode


# =============================================================================
# FIELD-BASED VALIDATION ERRORS
# =============================================================================

def example_field_validation_errors():
    """
    Example: Field-based validation errors for form validation
    This creates an error response with field-specific errors
    """
    
    # Old way (still supported for backward compatibility)
    raise CustomException(
        detail={
            "email": ["Email format is invalid"],
            "password": ["Password is too short", "Password must contain uppercase letters"]
        },
        code=ErrorCode.GENERAL_VALIDATION_ERROR,
        status_code=status.HTTP_400_BAD_REQUEST,
        message=_("Validation failed"),
    )
    
    # New structured way (recommended)
    raise CustomException.validation_error(
        field_errors={
            "email": ["The email format is incorrect"],
            "password": [
                "Password must be at least 8 characters long",
                "Password must contain at least one uppercase letter"
            ]
        },
        title=_("Validation Error"),
        instance="/api/v1/users/register"
    )


def example_login_validation():
    """
    Example: Login validation with field-specific errors
    Response will look like:
    {
        "type": "validation_error",
        "status": 400,
        "title": "Login Failed", 
        "detail": "The request data is invalid.",
        "instance": "/api/v1/auth/login",
        "errors": {
            "email": [
                {
                    "code": "invalid_format",
                    "message": "The email format is incorrect",
                    "value": null
                }
            ],
            "password": [
                {
                    "code": "required",
                    "message": "Password is required",
                    "value": null
                }
            ]
        }
    }
    """
    raise CustomException.validation_error(
        field_errors={
            "email": ["The email format is incorrect"],
            "password": ["Password is required"]
        },
        title=_("Login Failed"),
        instance="/api/v1/auth/login"
    )


# =============================================================================
# GENERAL ERROR MESSAGES
# =============================================================================

def example_general_server_error():
    """
    Example: General server error with title and details
    Response will look like:
    {
        "type": "server_error",
        "status": 500,
        "title": "A problem on our servers",
        "detail": "Please retry again later",
        "instance": "/api/v1/some-endpoint",
        "code": "ERR_INTERNAL_SERVER_ERROR"
    }
    """
    raise CustomException.business_logic_error(
        title=_("A problem on our servers"),
        detail=_("Please retry again later"),
        code=ErrorCode.INTERNAL_SERVER_ERROR,
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        instance="/api/v1/some-endpoint"
    )


def example_business_logic_error():
    """
    Example: Business logic error with title and details
    Response will look like:
    {
        "type": "business_logic_error",
        "status": 400,
        "title": "Insufficient Balance",
        "detail": "Your account balance is $10.50, but this transaction requires $25.00",
        "instance": "/api/v1/transactions",
        "code": "ERR_NOT_ENOUGH_BALANCE_LEFT",
        "balance": 10.50,
        "required_amount": 25.00
    }
    """
    raise CustomException.business_logic_error(
        title=_("Insufficient Balance"),
        detail=_("Your account balance is $10.50, but this transaction requires $25.00"),
        code=ErrorCode.NOT_ENOUGH_BALANCE_LEFT,
        instance="/api/v1/transactions",
        extra_data={
            "balance": 10.50,
            "required_amount": 25.00
        }
    )


def example_subscription_conflict():
    """
    Example: Business logic error for subscription conflicts
    """
    raise CustomException.business_logic_error(
        title=_("Active Subscription Exists"),
        detail=_("You already have an active subscription. Please cancel it before creating a new one."),
        code=ErrorCode.ACTIVE_SUBSCRIPTION_EXISTS,
        status_code=status.HTTP_409_CONFLICT,
        instance="/api/v1/subscriptions",
        extra_data={
            "existing_subscription_id": 12345,
            "expires_at": "2024-12-31T23:59:59Z"
        }
    )


# =============================================================================
# AUTHENTICATION & AUTHORIZATION ERRORS
# =============================================================================

def example_authentication_error():
    """
    Example: Authentication error
    Response will look like:
    {
        "type": "authentication_error",
        "status": 401,
        "title": "Authentication Failed",
        "detail": "The provided token has expired",
        "instance": "/api/v1/protected-endpoint",
        "code": "ERR_INVALID_TOKEN"
    }
    """
    raise CustomException.authentication_error(
        title=_("Authentication Failed"),
        detail=_("The provided token has expired"),
        instance="/api/v1/protected-endpoint"
    )


def example_authorization_error():
    """
    Example: Authorization error
    Response will look like:
    {
        "type": "authorization_error",
        "status": 403,
        "title": "Access Denied",
        "detail": "You need admin privileges to perform this action",
        "instance": "/api/v1/admin/users",
        "code": "ERR_PERMISSION_DENIED"
    }
    """
    raise CustomException.authorization_error(
        title=_("Access Denied"),
        detail=_("You need admin privileges to perform this action"),
        instance="/api/v1/admin/users"
    )


def example_not_found_error():
    """
    Example: Not found error
    Response will look like:
    {
        "type": "client_error",
        "status": 404,
        "title": "User Not Found",
        "detail": "User with ID 12345 does not exist",
        "instance": "/api/v1/users/12345",
        "code": "ERR_NOT_FOUND_ERROR"
    }
    """
    raise CustomException.not_found_error(
        title=_("User Not Found"),
        detail=_("User with ID 12345 does not exist"),
        instance="/api/v1/users/12345"
    )


# =============================================================================
# MIXED SCENARIOS
# =============================================================================

def example_complex_validation_with_business_logic():
    """
    Example: Complex validation that includes both field errors and business logic
    This shows how you can combine field validation with business rules
    """
    # First, check field validation
    field_errors = {}
    
    email = "invalid-email"
    password = "123"  # Too short
    age = 15  # Too young
    
    if "@" not in email:
        field_errors["email"] = ["Email must contain @ symbol"]
    
    if len(password) < 8:
        field_errors["password"] = ["Password must be at least 8 characters long"]
        
    if age < 16:
        field_errors["age"] = ["Age must be at least 16 years old"]
    
    # If there are field errors, raise validation error
    if field_errors:
        raise CustomException.validation_error(
            field_errors=field_errors,
            title=_("Registration Failed"),
            instance="/api/v1/auth/register"
        )
    
    # Then check business rules (this would be after field validation passes)
    existing_user_count = 1000  # Assume we have many users
    if existing_user_count >= 1000:
        raise CustomException.business_logic_error(
            title=_("Registration Temporarily Unavailable"),
            detail=_("We have reached our user limit. Please try again later."),
            code=ErrorCode.DUPLICATE_REQUEST,
            instance="/api/v1/auth/register",
            extra_data={"current_user_count": existing_user_count}
        )


# =============================================================================
# MIGRATION FROM OLD PATTERN
# =============================================================================

def old_pattern_example():
    """
    OLD PATTERN - This still works for backward compatibility
    """
    raise CustomException(
        detail="User not found",
        code=ErrorCode.NOT_FOUND_ERROR,
        status_code=status.HTTP_404_NOT_FOUND,
        message=_("Content not found!"),
    )


def new_pattern_equivalent():
    """
    NEW PATTERN - Equivalent to the old pattern above but with structured response
    """
    raise CustomException.not_found_error(
        title=_("Content not found!"),
        detail=_("User not found"),
        instance="/api/v1/users/123"
    )


# =============================================================================
# USAGE IN SERIALIZERS
# =============================================================================

class ExampleSerializer:
    """
    Example of how to use structured errors in serializers
    """
    
    def validate_email(self, value):
        """Field-level validation"""
        if "@" not in value:
            # This will be automatically converted to a structured field error
            from rest_framework.exceptions import ValidationError
            raise ValidationError("Email must contain @ symbol")
        return value
    
    def validate(self, attrs):
        """Object-level validation with structured errors"""
        email = attrs.get('email')
        phone = attrs.get('phone')
        
        if not email and not phone:
            # Use new structured validation error
            raise CustomException.validation_error(
                field_errors={
                    "email": ["Email is required when phone is not provided"],
                    "phone": ["Phone is required when email is not provided"]
                },
                title=_("Contact Information Required"),
                instance="/api/v1/users/create"
            )
        
        return attrs


# =============================================================================
# USAGE IN VIEWS
# =============================================================================

class ExampleViewUsage:
    """
    Example of how to use structured errors in views
    """
    
    def create_user(self, request):
        """Example view method"""
        try:
            # Business logic here
            user_id = request.data.get('user_id')
            if not user_id:
                raise CustomException.validation_error(
                    field_errors={"user_id": ["User ID is required"]},
                    instance=request.path
                )
            
            # Check business rules
            if user_already_exists(user_id):
                raise CustomException.business_logic_error(
                    title=_("User Already Exists"),
                    detail=_("A user with this ID already exists in the system"),
                    code=ErrorCode.DUPLICATE_KEY_ERROR,
                    status_code=status.HTTP_409_CONFLICT,
                    instance=request.path
                )
                
        except SomeInternalError as e:
            # Convert internal errors to structured errors
            raise CustomException.server_error(
                title=_("Internal Processing Error"),
                detail=_("An error occurred while processing your request"),
                instance=request.path
            ) from e


def user_already_exists(user_id):
    """Dummy function for example"""
    return False