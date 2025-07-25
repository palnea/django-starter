"""
Examples of Generic (Non-Field) Errors with Title and Description

This file demonstrates how to create and handle generic errors that are not tied
to specific fields but provide rich title and description information for clients.
"""

from django.utils.translation import gettext_lazy as _
from rest_framework import serializers, status
from rest_framework.exceptions import ValidationError

from common.custom_exceptions.custom_exception import CustomException
from common.response.response_information_codes.error_code import ErrorCode


# =============================================================================
# DRF SERIALIZER NON-FIELD ERRORS (AUTOMATIC CONVERSION)
# =============================================================================

def demo_drf_non_field_errors():
    """DRF serializers can raise non-field errors that become generic errors"""
    
    class BusinessRuleSerializer(serializers.Serializer):
        start_date = serializers.DateField(required=True)
        end_date = serializers.DateField(required=True)
        user_type = serializers.ChoiceField(choices=['admin', 'user'], required=True)
        
        def validate(self, attrs):
            start_date = attrs.get('start_date')
            end_date = attrs.get('end_date')
            user_type = attrs.get('user_type')
            
            # Non-field error - not tied to any specific field
            if start_date and end_date and start_date > end_date:
                raise ValidationError(
                    'Start date cannot be after end date. Please check your date range.'
                )
            
            # Another non-field error with business logic
            if user_type == 'user' and (end_date - start_date).days > 30:
                raise ValidationError(
                    'Regular users cannot create reports longer than 30 days. Please reduce the date range or contact an administrator.'
                )
            
            return attrs
    
    """
    When the above serializer validation fails, it automatically becomes:
    
    {
        "type": "validation_error",
        "status": 400,
        "title": "Validation Error",
        "detail": "Start date cannot be after end date. Please check your date range.",
        "instance": "/api/v1/reports/create"
    }
    
    The client can show this as a general error message with the title and detail.
    """


def demo_multiple_drf_non_field_errors():
    """Multiple non-field errors get combined into a comprehensive message"""
    
    class ComplexBusinessRuleSerializer(serializers.Serializer):
        budget = serializers.DecimalField(max_digits=10, decimal_places=2, required=True)
        duration_days = serializers.IntegerField(required=True)
        project_type = serializers.CharField(required=True)
        
        def validate(self, attrs):
            budget = attrs.get('budget')
            duration_days = attrs.get('duration_days')
            project_type = attrs.get('project_type')
            
            errors = []
            
            # Multiple business rule violations
            if budget < 1000 and project_type == 'enterprise':
                errors.append('Enterprise projects require a minimum budget of $1,000')
            
            if duration_days > 365:
                errors.append('Projects cannot exceed 365 days duration')
            
            if budget > 100000 and duration_days < 30:
                errors.append('High-budget projects must have a minimum duration of 30 days')
            
            if errors:
                # Raise multiple non-field errors
                raise ValidationError(errors)
            
            return attrs
    
    """
    When multiple non-field errors occur, they get combined:
    
    {
        "type": "validation_error",
        "status": 400,
        "title": "Validation Errors",
        "detail": "Enterprise projects require a minimum budget of $1,000. Projects cannot exceed 365 days duration. High-budget projects must have a minimum duration of 30 days.",
        "instance": "/api/v1/projects/create"
    }
    """


# =============================================================================
# CUSTOM BUSINESS LOGIC ERRORS (EXPLICIT CONTROL)
# =============================================================================

def demo_business_logic_generic_errors():
    """Custom business logic errors with rich title and description"""
    
    # Example 1: Payment Processing Error
    def process_payment(amount, user_balance, user_type):
        if user_balance < amount:
            raise CustomException.business_logic_error(
                title=_("Insufficient Funds"),
                detail=f"Your account balance is ${user_balance:.2f}, but this transaction requires ${amount:.2f}. Please add funds to your account or reduce the transaction amount.",
                code=ErrorCode.NOT_ENOUGH_BALANCE_LEFT,
                instance="/api/v1/payments/process",
                extra_data={
                    "current_balance": float(user_balance),
                    "required_amount": float(amount),
                    "shortfall": float(amount - user_balance)
                }
            )
        
        if user_type == 'trial' and amount > 100:
            raise CustomException.business_logic_error(
                title=_("Transaction Limit Exceeded"),
                detail=_("Trial accounts are limited to transactions of $100 or less. Please upgrade your account to process larger transactions."),
                code=ErrorCode.PERMISSION_DENIED,
                instance="/api/v1/payments/process",
                extra_data={
                    "account_type": user_type,
                    "transaction_limit": 100,
                    "attempted_amount": float(amount)
                }
            )
    
    """
    Response:
    {
        "type": "business_logic_error",
        "status": 400,
        "title": "Insufficient Funds",
        "detail": "Your account balance is $50.00, but this transaction requires $75.00. Please add funds to your account or reduce the transaction amount.",
        "instance": "/api/v1/payments/process",
        "code": "ERR_NOT_ENOUGH_BALANCE_LEFT",
        "current_balance": 50.0,
        "required_amount": 75.0,
        "shortfall": 25.0
    }
    """


def demo_system_maintenance_errors():
    """System-level generic errors with informative titles and descriptions"""
    
    def check_system_availability():
        # Simulate various system states
        system_status = "maintenance"  # Could be "maintenance", "overloaded", "partial_outage"
        
        if system_status == "maintenance":
            raise CustomException.business_logic_error(
                title=_("System Maintenance in Progress"),
                detail=_("Our systems are currently undergoing scheduled maintenance. Please try again in 30 minutes. We apologize for any inconvenience."),
                code=ErrorCode.AN_ERROR_OCCURED,
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                instance="/api/v1/system/status",
                extra_data={
                    "maintenance_type": "scheduled",
                    "estimated_completion": "2024-01-01T15:30:00Z",
                    "alternative_endpoints": ["/api/v1/status"]
                }
            )
        
        elif system_status == "overloaded":
            raise CustomException.business_logic_error(
                title=_("High Traffic Volume"),
                detail=_("Our servers are experiencing high traffic. Your request has been queued and will be processed shortly. Please do not retry immediately."),
                code=ErrorCode.THROTTLED,
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                instance="/api/v1/heavy-operation",
                extra_data={
                    "queue_position": 42,
                    "estimated_wait_seconds": 120,
                    "retry_after": 60
                }
            )
    
    """
    Response:
    {
        "type": "business_logic_error",
        "status": 503,
        "title": "System Maintenance in Progress",
        "detail": "Our systems are currently undergoing scheduled maintenance. Please try again in 30 minutes. We apologize for any inconvenience.",
        "instance": "/api/v1/system/status",
        "code": "ERR_AN_ERROR_OCCURED",
        "maintenance_type": "scheduled",
        "estimated_completion": "2024-01-01T15:30:00Z",
        "alternative_endpoints": ["/api/v1/status"]
    }
    """


def demo_business_rule_violations():
    """Business rule violations as generic errors"""
    
    def create_subscription(user, plan_type, existing_subscriptions):
        # Check business rules
        if existing_subscriptions and plan_type != 'upgrade':
            raise CustomException.business_logic_error(
                title=_("Active Subscription Exists"),
                detail=_("You already have an active subscription. To change your plan, please use the upgrade option or cancel your current subscription first."),
                code=ErrorCode.ACTIVE_SUBSCRIPTION_EXISTS,
                status_code=status.HTTP_409_CONFLICT,
                instance="/api/v1/subscriptions/create",
                extra_data={
                    "existing_subscription": {
                        "id": existing_subscriptions[0].id,
                        "plan": existing_subscriptions[0].plan,
                        "expires_at": existing_subscriptions[0].expires_at.isoformat()
                    },
                    "suggested_actions": ["upgrade", "cancel_current"]
                }
            )
        
        if plan_type == 'premium' and user.account_age_days < 30:
            raise CustomException.business_logic_error(
                title=_("Account Too New for Premium"),
                detail=_("Premium subscriptions are only available to accounts that have been active for at least 30 days. Your account is {days} days old.").format(days=user.account_age_days),
                code=ErrorCode.VERIFICATION_PREREQUISITE_NOT_SATISFIED,
                instance="/api/v1/subscriptions/create",
                extra_data={
                    "account_age_days": user.account_age_days,
                    "required_age_days": 30,
                    "alternative_plans": ["basic", "standard"]
                }
            )
    
    """
    Response:
    {
        "type": "business_logic_error",
        "status": 409,
        "title": "Active Subscription Exists",
        "detail": "You already have an active subscription. To change your plan, please use the upgrade option or cancel your current subscription first.",
        "instance": "/api/v1/subscriptions/create",
        "code": "ERR_ACTIVE_SUBSCRIPTION_EXISTS",
        "existing_subscription": {
            "id": 12345,
            "plan": "standard",
            "expires_at": "2024-12-31T23:59:59Z"
        },
        "suggested_actions": ["upgrade", "cancel_current"]
    }
    """


# =============================================================================
# AUTHENTICATION & AUTHORIZATION GENERIC ERRORS
# =============================================================================

def demo_authentication_generic_errors():
    """Authentication errors as generic errors with title and description"""
    
    def authenticate_user(token):
        if not token:
            raise CustomException.authentication_error(
                title=_("Authentication Required"),
                detail=_("This endpoint requires authentication. Please provide a valid access token in the Authorization header."),
                instance="/api/v1/protected-resource"
            )
        
        if token == "expired":
            raise CustomException.authentication_error(
                title=_("Session Expired"),
                detail=_("Your authentication token has expired. Please log in again to continue."),
                instance="/api/v1/protected-resource"
            )
        
        if token == "invalid":
            raise CustomException.authentication_error(
                title=_("Invalid Authentication"),
                detail=_("The provided authentication token is invalid or malformed. Please check your credentials and try again."),
                instance="/api/v1/protected-resource"
            )
    
    """
    Response:
    {
        "type": "authentication_error",
        "status": 401,
        "title": "Session Expired",
        "detail": "Your authentication token has expired. Please log in again to continue.",
        "instance": "/api/v1/protected-resource",
        "code": "ERR_AUTHENTICATION_FAILED"
    }
    """


def demo_authorization_generic_errors():
    """Authorization errors as generic errors with title and description"""
    
    def check_permissions(user, resource, action):
        if not user.is_active:
            raise CustomException.authorization_error(
                title=_("Account Suspended"),
                detail=_("Your account has been temporarily suspended. Please contact support for assistance."),
                instance=f"/api/v1/{resource}"
            )
        
        if action == "delete" and user.role != "admin":
            raise CustomException.authorization_error(
                title=_("Insufficient Permissions"),
                detail=_("You need administrator privileges to delete resources. Please contact your system administrator if you believe this is an error."),
                instance=f"/api/v1/{resource}"
            )
        
        if action == "export" and not user.has_export_permission:
            raise CustomException.authorization_error(
                title=_("Export Permission Required"),
                detail=_("Data export functionality requires special permissions. Please request export access from your administrator."),
                instance=f"/api/v1/{resource}/export"
            )
    
    """
    Response:
    {
        "type": "authorization_error",
        "status": 403,
        "title": "Insufficient Permissions",
        "detail": "You need administrator privileges to delete resources. Please contact your system administrator if you believe this is an error.",
        "instance": "/api/v1/users",
        "code": "ERR_PERMISSION_DENIED"
    }
    """


# =============================================================================
# MIXED SCENARIOS: FIELD ERRORS + GENERIC ERRORS
# =============================================================================

def demo_mixed_field_and_generic_errors():
    """Handling both field-specific and generic errors in the same response"""
    
    class UserRegistrationSerializer(serializers.Serializer):
        username = serializers.CharField(required=True, min_length=3)
        email = serializers.EmailField(required=True)
        password = serializers.CharField(required=True, min_length=8)
        terms_accepted = serializers.BooleanField(required=True)
        
        def validate_username(self, value):
            if value.lower() in ['admin', 'root', 'system']:
                raise serializers.ValidationError(
                    "This username is reserved", 
                    code='reserved_username'
                )
            return value
        
        def validate(self, attrs):
            # Check if this validation should result in generic errors
            # vs field-specific errors
            terms_accepted = attrs.get('terms_accepted')
            username = attrs.get('username')
            
            # If terms not accepted, this is a general business rule
            if not terms_accepted:
                raise ValidationError(
                    'You must accept the terms and conditions to create an account. Please review our terms of service and privacy policy.'
                )
            
            # Additional business rule check
            if username and len(username) < 5:
                # This could be a field error, but we're treating it as a business rule
                raise ValidationError(
                    'For security reasons, usernames must be at least 5 characters long in our system. This helps protect against automated attacks.'
                )
            
            return attrs
    
    """
    If both field validation and object validation fail:
    
    Field errors response (username = 'admin', password = '123'):
    {
        "type": "validation_error",
        "status": 400,
        "title": "Validation Error",
        "detail": "The request data is invalid.",
        "instance": "/api/v1/auth/register",
        "errors": {
            "username": [
                {
                    "code": "reserved_username",
                    "message": "This username is reserved",
                    "value": null
                }
            ],
            "password": [
                {
                    "code": "min_length",
                    "message": "Ensure this field has at least 8 characters.",
                    "value": null
                }
            ]
        }
    }
    
    Generic error response (terms_accepted = false):
    {
        "type": "validation_error",
        "status": 400,
        "title": "Validation Error",
        "detail": "You must accept the terms and conditions to create an account. Please review our terms of service and privacy policy.",
        "instance": "/api/v1/auth/register"
    }
    """


# =============================================================================
# CLIENT-SIDE HANDLING EXAMPLES
# =============================================================================

def client_side_handling_example():
    """
    Example of how clients can handle both field and generic errors
    """
    
    javascript_example = '''
    // JavaScript/TypeScript client handling
    async function handleApiCall(apiResponse) {
        const data = await apiResponse.json();
        
        if (data.type === 'validation_error') {
            // Check if it's field-specific errors
            if (data.errors) {
                // Handle field-specific errors
                Object.keys(data.errors).forEach(fieldName => {
                    const fieldErrors = data.errors[fieldName];
                    fieldErrors.forEach(error => {
                        showFieldError(fieldName, error.message, error.code);
                    });
                });
            } else {
                // Handle generic validation error
                showGenericError(data.title, data.detail);
            }
        } else if (data.type === 'business_logic_error') {
            // Always generic error with title and detail
            showBusinessError(data.title, data.detail, data);
        } else if (data.type === 'authentication_error') {
            // Generic authentication error
            showAuthError(data.title, data.detail);
            redirectToLogin();
        } else if (data.type === 'authorization_error') {
            // Generic authorization error
            showPermissionError(data.title, data.detail);
        }
    }
    
    function showFieldError(fieldName, message, code) {
        // Show error next to specific form field
        const fieldElement = document.querySelector(`[name="${fieldName}"]`);
        displayErrorMessage(fieldElement, message);
    }
    
    function showGenericError(title, detail) {
        // Show generic error at top of form or in modal
        displayNotification({
            type: 'error',
            title: title,
            message: detail,
            position: 'top'
        });
    }
    
    function showBusinessError(title, detail, data) {
        // Show business logic error with potential additional actions
        displayNotification({
            type: 'warning',
            title: title,
            message: detail,
            actions: data.suggested_actions || [],
            extraData: data
        });
    }
    '''
    
    return javascript_example


# =============================================================================
# SUMMARY OF GENERIC ERROR BENEFITS
# =============================================================================

"""
Benefits of Generic Errors with Title and Description:

1. **Clear Communication**: Title provides immediate context, detail gives full explanation
2. **Better UX**: Users understand what went wrong and how to fix it
3. **Consistent Structure**: All generic errors follow same title/detail pattern
4. **Business Logic Focus**: Perfect for rules that aren't tied to specific fields
5. **Rich Context**: Extra data provides additional information for smart clients
6. **Internationalization**: Both title and detail are translatable
7. **Error Categorization**: Type field helps clients handle different error categories

Usage Guidelines:

- Use **field errors** for validation tied to specific form fields
- Use **generic errors** for business rules, system states, permissions
- Provide **clear titles** that immediately convey the issue type
- Write **helpful details** that explain the problem and suggest solutions
- Include **extra data** when it helps clients provide better user experience
- Consider **error codes** for programmatic handling of specific scenarios

The system automatically handles DRF non-field errors as generic errors,
while providing explicit control for custom business logic scenarios.
"""