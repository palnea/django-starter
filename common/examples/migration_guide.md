# Structured Error Response Migration Guide

This guide helps you migrate from the current error handling system to the new structured error response system that follows RFC 7807 standards and provides both field-based and general error responses.

## Overview

The new structured error response system provides:

1. **Field-based validation errors** - Perfect for form validation with specific field error messages
2. **General error messages** - For business logic errors with title and details
3. **RFC 7807 compliance** - Industry standard for API error responses
4. **Backward compatibility** - Your existing code continues to work
5. **Enhanced client experience** - Clients can easily parse and display errors

## New Error Response Formats

### Field-based Validation Errors

```json
{
    "type": "validation_error",
    "status": 400,
    "title": "Validation Error",
    "detail": "The request data is invalid.",
    "instance": "/api/v1/auth/login",
    "code": "ERR_GENERAL_VALIDATION_ERROR",
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
```

### General Error Messages

```json
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
```

## Migration Patterns

### 1. Simple Error Messages

**Before (Old Pattern):**
```python
raise CustomException(
    detail="User not found",
    code=ErrorCode.NOT_FOUND_ERROR,
    status_code=status.HTTP_404_NOT_FOUND,
    message=_("Content not found!"),
)
```

**After (New Pattern):**
```python
raise CustomException.not_found_error(
    title=_("Content not found!"),
    detail=_("User not found"),
    instance=request.path  # or specific path like "/api/v1/users/123"
)
```

### 2. Field Validation Errors

**Before (Old Pattern):**
```python
raise CustomException(
    detail={
        "email": "Cannot be empty if no phone provided",
        "phone": "Cannot be empty if no email provided",
    },
    code=ErrorCode.GENERAL_VALIDATION_ERROR,
    status_code=status.HTTP_400_BAD_REQUEST,
    message=_("Email or phone should be provided"),
)
```

**After (New Pattern):**
```python
raise CustomException.validation_error(
    field_errors={
        "email": ["Cannot be empty if no phone provided"],
        "phone": ["Cannot be empty if no email provided"]
    },
    title=_("Email or phone should be provided"),
    instance=request.path
)
```

### 3. Business Logic Errors

**Before (Old Pattern):**
```python
raise CustomException(
    detail="You already have an active subscription",
    code=ErrorCode.ACTIVE_SUBSCRIPTION_EXISTS,
    status_code=status.HTTP_409_CONFLICT,
    message=_("Subscription conflict"),
)
```

**After (New Pattern):**
```python
raise CustomException.business_logic_error(
    title=_("Active Subscription Exists"),
    detail=_("You already have an active subscription. Please cancel it before creating a new one."),
    code=ErrorCode.ACTIVE_SUBSCRIPTION_EXISTS,
    status_code=status.HTTP_409_CONFLICT,
    instance="/api/v1/subscriptions",
    extra_data={
        "existing_subscription_id": subscription.id,
        "expires_at": subscription.expires_at.isoformat()
    }
)
```

### 4. Authentication/Authorization Errors

**Before (Old Pattern):**
```python
raise CustomException(
    detail="Invalid token",
    code=ErrorCode.AUTHENTICATION_FAILED,
    status_code=status.HTTP_401_UNAUTHORIZED,
    message=_("Authentication failed"),
)
```

**After (New Pattern):**
```python
raise CustomException.authentication_error(
    title=_("Authentication Failed"),
    detail=_("The provided token has expired"),
    instance=request.path
)
```

## Specific Migration Examples

### Authy Serializers

**Current Code in `authy/serializers.py`:**
```python
if not email and not phone:
    raise CustomException(
        detail={
            "email": "Cannot be empty if no phone provided",
            "phone": "Cannot be empty if no email provided",
        },
        code=ErrorCode.GENERAL_VALIDATION_ERROR,
        status_code=status.HTTP_400_BAD_REQUEST,
        message=_("Email or phone should be provided"),
    )
```

**Updated Code:**
```python
if not email and not phone:
    raise CustomException.validation_error(
        field_errors={
            "email": ["Cannot be empty if no phone provided"],
            "phone": ["Cannot be empty if no email provided"]
        },
        title=_("Contact Information Required"),
        instance="/api/v1/auth/login"  # or appropriate endpoint
    )
```

### Payment Services

**Current Code in `payment/services.py`:**
```python
raise CustomException(
    detail="Insufficient balance",
    code=ErrorCode.NOT_ENOUGH_BALANCE_LEFT,
    status_code=status.HTTP_400_BAD_REQUEST,
    message=_("Transaction failed"),
)
```

**Updated Code:**
```python
raise CustomException.business_logic_error(
    title=_("Insufficient Balance"),
    detail=f"Your account balance is ${current_balance}, but this transaction requires ${required_amount}",
    code=ErrorCode.NOT_ENOUGH_BALANCE_LEFT,
    instance="/api/v1/transactions",
    extra_data={
        "current_balance": current_balance,
        "required_amount": required_amount
    }
)
```

## Using in Serializers

### DRF Serializer Field Validation

DRF's built-in ValidationError will automatically be converted to structured format:

```python
def validate_email(self, value):
    if "@" not in value:
        # This gets automatically converted to structured format
        raise ValidationError("Email must contain @ symbol")
    return value
```

### Custom Serializer Validation

```python
def validate(self, attrs):
    email = attrs.get('email')
    phone = attrs.get('phone')
    
    if not email and not phone:
        raise CustomException.validation_error(
            field_errors={
                "email": ["Email is required when phone is not provided"],
                "phone": ["Phone is required when email is not provided"]
            },
            title=_("Contact Information Required"),
            instance="/api/v1/users"
        )
    
    return attrs
```

## Using in Views

### APIView Error Handling

```python
class UserCreateView(APIView):
    def post(self, request):
        try:
            # Your business logic here
            if some_condition:
                raise CustomException.business_logic_error(
                    title=_("Operation Not Allowed"),
                    detail=_("This operation is not permitted at this time"),
                    instance=request.path
                )
        except SomeInternalError as e:
            raise CustomException.server_error(
                title=_("Internal Processing Error"),
                detail=_("An error occurred while processing your request"),
                instance=request.path
            ) from e
```

### ViewSet Error Handling

```python
class UserViewSet(ViewSet):
    def create(self, request):
        user_id = request.data.get('user_id')
        
        if not user_id:
            raise CustomException.validation_error(
                field_errors={"user_id": ["User ID is required"]},
                instance=request.path
            )
        
        if User.objects.filter(id=user_id).exists():
            raise CustomException.business_logic_error(
                title=_("User Already Exists"),
                detail=_("A user with this ID already exists"),
                code=ErrorCode.DUPLICATE_KEY_ERROR,
                status_code=status.HTTP_409_CONFLICT,
                instance=request.path
            )
```

## Configuration

### Enable Structured Responses

Add to your Django settings:

```python
# Enable structured error responses (default: True)
USE_STRUCTURED_ERROR_RESPONSES = True

# Your existing DRF settings
REST_FRAMEWORK = {
    'EXCEPTION_HANDLER': 'common.exception_handling.custom_exception_handler.custom_exception_handler',
    # ... other settings
}
```

### Disable for Specific Environments

If you need to disable structured responses for certain environments:

```python
# In settings/development.py
USE_STRUCTURED_ERROR_RESPONSES = False  # Falls back to legacy format
```

## Testing Structured Responses

### Test Field Validation Errors

```python
def test_field_validation_error(self):
    response = self.client.post('/api/v1/users/', {
        'email': 'invalid-email',
        'password': '123'
    })
    
    self.assertEqual(response.status_code, 400)
    data = response.json()
    
    self.assertEqual(data['type'], 'validation_error')
    self.assertEqual(data['status'], 400)
    self.assertIn('title', data)
    self.assertIn('errors', data)
    self.assertIn('email', data['errors'])
    self.assertIn('password', data['errors'])
```

### Test General Errors

```python
def test_business_logic_error(self):
    response = self.client.post('/api/v1/transactions/', {
        'amount': 100.00
    })
    
    self.assertEqual(response.status_code, 400)
    data = response.json()
    
    self.assertEqual(data['type'], 'business_logic_error')
    self.assertEqual(data['title'], 'Insufficient Balance')
    self.assertIn('detail', data)
    self.assertIn('balance', data)  # Extra data
```

## Best Practices

### 1. Always Include Instance

```python
raise CustomException.validation_error(
    field_errors={"email": ["Invalid format"]},
    instance=request.path  # Always include the request path
)
```

### 2. Use Meaningful Titles and Details

```python
# Good
raise CustomException.business_logic_error(
    title=_("Payment Processing Failed"),
    detail=_("Your credit card was declined. Please check your payment information."),
    code=ErrorCode.PAYMENT_FAILED
)

# Avoid
raise CustomException.business_logic_error(
    title=_("Error"),
    detail=_("Something went wrong"),
    code=ErrorCode.AN_ERROR_OCCURED
)
```

### 3. Include Relevant Extra Data

```python
raise CustomException.business_logic_error(
    title=_("Rate Limit Exceeded"),
    detail=_("You have exceeded the maximum number of requests per hour"),
    code=ErrorCode.THROTTLED,
    extra_data={
        "requests_made": 1000,
        "limit": 1000,
        "reset_time": "2024-01-01T15:00:00Z"
    }
)
```

### 4. Use Appropriate Error Types

- `validation_error()` - For form/input validation
- `business_logic_error()` - For business rule violations
- `authentication_error()` - For auth failures
- `authorization_error()` - For permission denials
- `not_found_error()` - For missing resources
- `server_error()` - For internal errors

## Rollback Plan

If you need to rollback to the old format:

1. Set `USE_STRUCTURED_ERROR_RESPONSES = False` in settings
2. Your existing exception handling will continue to work as before
3. No code changes required for rollback

## Summary

The new structured error response system provides:

- ✅ Better client experience with structured, parseable errors
- ✅ Field-specific validation errors for forms
- ✅ Rich general error messages with title and details
- ✅ RFC 7807 compliance for industry standards
- ✅ Full backward compatibility
- ✅ Enhanced debugging with extra data support
- ✅ Internationalization support maintained

Start migrating your most critical endpoints first, then gradually update the rest of your codebase to take advantage of the new structured error format.