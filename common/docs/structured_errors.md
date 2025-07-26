# Structured Error Response System

A comprehensive Django REST Framework error handling system that provides RFC 7807 compliant, structured error responses with automatic DRF integration and type-safe error codes.

## Overview

This system transforms inconsistent error formats into a standardized structure supporting:

- **Field-based validation errors** - Perfect for form validation with field-specific messages
- **General business logic errors** - Rich error messages with titles and details
- **Multiple error reporting** - Handle complex scenarios with multiple simultaneous issues
- **Type-safe error codes** - Python enums for IDE autocomplete and type safety
- **RFC 7807 compliance** - Industry standard for API error responses
- **Automatic DRF integration** - No code changes needed for existing serializers

## Error Response Formats

### 1. Field Validation Errors

For form validation with field-specific error messages:

```json
{
  "type": "validation_error",
  "status": 400,
  "response_code": "ERR_GENERAL_VALIDATION_ERROR", 
  "title": "Validation Error",
  "detail": "The request data is invalid.",
  "instance": "/api/v1/auth/login",
  "errors": {
    "email": [
      {
        "code": "invalid_email",
        "message": "Please enter a valid email address",
        "value": "invalid-format"
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

### 2. Single General Error

For business logic errors with rich context:

```json
{
  "type": "business_logic_error",
  "status": 400,
  "response_code": "ERR_NOT_ENOUGH_BALANCE_LEFT",
  "title": "Insufficient Funds",
  "detail": "Your account balance is $50.00, but this transaction requires $75.00.",
  "instance": "/api/v1/payments",
  "current_balance": 50.0,
  "required_amount": 75.0
}
```

### 3. Multiple General Errors

For complex scenarios with multiple simultaneous issues:

```json
{
  "type": "business_logic_error",
  "status": 400,
  "response_code": "ERR_AN_ERROR_OCCURED",
  "title": "Multiple Issues Found",
  "detail": "Multiple issues were identified with your request.",
  "instance": "/api/v1/payments",
  "errors": {
    "general": [
      {
        "title": "Insufficient Funds",
        "detail": "Your balance is $50.00, but this transaction requires $75.00.",
        "code": "insufficient_funds"
      },
      {
        "title": "Daily Limit Exceeded",
        "detail": "You have exceeded your daily transaction limit of $500.00.",
        "code": "daily_limit_exceeded"
      }
    ]
  }
}
```

### 4. Mixed Field + General Errors

Combining field validation with general notifications:

```json
{
  "type": "validation_error",
  "status": 400,
  "response_code": "ERR_GENERAL_VALIDATION_ERROR",
  "title": "Account Temporarily Locked",
  "detail": "Your account has been temporarily locked due to multiple failed attempts.",
  "instance": "/api/v1/auth/login",
  "errors": {
    "email": [
      {"code": "invalid_format", "message": "Email must contain @ symbol", "value": null}
    ],
    "password": [
      {"code": "too_weak", "message": "Password must contain special characters", "value": null}
    ],
    "general": [
      {
        "title": "Account Temporarily Locked",
        "detail": "Your account has been temporarily locked due to multiple failed login attempts.",
        "code": "account_locked"
      }
    ]
  }
}
```

## Usage Examples

### Automatic DRF Integration

**No code changes needed!** All DRF serializer errors are automatically converted:

```python
class UserSerializer(serializers.ModelSerializer):
    def validate_email(self, value):
        if "@" not in value:
            # Automatically becomes structured!
            raise ValidationError("Email must contain @ symbol")
        return value
```

### Type-Safe Error Codes

Using Python enums for IDE autocomplete and type safety:

```python
from common.response.response_information_codes.field_error_code import FieldErrorCode
from common.response.response_information_codes.general_error_code import GeneralErrorCode

# Field validation with enum codes
raise CustomException.field_validation_error(
    field="email",
    code=FieldErrorCode.INVALID_EMAIL,
    message="Please enter a valid email address",
    value="invalid-format"
)

# Business logic with enum codes  
raise CustomException.business_logic_error(
    title="Insufficient Funds",
    detail="Your account balance is $50.00, but this transaction requires $75.00.",
    code=GeneralErrorCode.INSUFFICIENT_FUNDS,
    instance="/api/v1/payments"
)
```

### Multiple Business Logic Errors

Handle complex scenarios with multiple simultaneous issues:

```python
raise CustomException.multiple_business_logic_errors(
    errors=[
        {
            "title": "Insufficient Funds",
            "detail": "Your account balance is $50.00, but this transaction requires $75.00.",
            "code": GeneralErrorCode.INSUFFICIENT_FUNDS
        },
        {
            "title": "Daily Limit Exceeded", 
            "detail": "You have exceeded your daily transaction limit of $500.00.",
            "code": GeneralErrorCode.DAILY_LIMIT_EXCEEDED
        },
        {
            "title": "Merchant Unavailable",
            "detail": "The merchant's payment system is currently unavailable.",
            "code": GeneralErrorCode.SERVICE_UNAVAILABLE
        }
    ],
    instance="/api/v1/payments"
)
```

### Custom Validation with Rich Context

```python
# Complex validation scenario
field_errors = [
    FieldError(
        field="email",
        code=FieldErrorCode.INVALID_EMAIL,
        message="Email format is invalid"
    ),
    FieldError(
        field="password", 
        code=FieldErrorCode.PASSWORD_TOO_WEAK,
        message="Password must contain special characters"
    )
]

general_errors = [
    GeneralError(
        title="Account Temporarily Locked",
        detail="Your account has been locked due to multiple failed attempts.",
        code=GeneralErrorCode.ACCOUNT_LOCKED
    )
]

response = StructuredErrorResponse(
    error_type=StructuredErrorType.VALIDATION_ERROR,
    status_code=400,
    instance="/api/v1/auth/login",
    general_errors=general_errors,
    field_errors=field_errors
)
```

## Error Types

The system supports these error types:

- **`validation_error`** - Field-based validation (automatic DRF conversion)
- **`business_logic_error`** - Business rule violations  
- **`authentication_error`** - Authentication failures (401)
- **`authorization_error`** - Permission denials (403)
- **`not_found_error`** - Resource not found (404)
- **`client_error`** - Other 4xx errors
- **`server_error`** - 5xx errors

## Configuration

Enable structured responses in Django settings:

```python
REST_FRAMEWORK = {
    'EXCEPTION_HANDLER': 'common.exception_handling.custom_exception_handler.custom_exception_handler',
    # ... other settings
}
```

## Migration Guide

### From Old Format

```python
# OLD: Inconsistent legacy format
raise CustomException(
    detail="User not found",
    code=ErrorCode.NOT_FOUND_ERROR,
    status_code=status.HTTP_404_NOT_FOUND,
    message=_("Content not found!"),
)
```

### To New Format

```python
# NEW: Structured format
raise CustomException.not_found_error(
    title=_("Content not found!"),
    detail=_("User not found"),
    instance=request.path
)
```

### Field Validation Migration

```python
# OLD: Manual field error structure
raise CustomException(
    detail={
        "email": "Cannot be empty if no phone provided",
        "phone": "Cannot be empty if no email provided",
    },
    code=ErrorCode.GENERAL_VALIDATION_ERROR,
    status_code=status.HTTP_400_BAD_REQUEST,
    message=_("Email or phone should be provided"),
)

# NEW: Structured field validation
raise CustomException.validation_error(
    field_errors={
        "email": ["Cannot be empty if no phone provided"],
        "phone": ["Cannot be empty if no email provided"]
    },
    title=_("Contact Information Required"),
    instance="/api/v1/auth/login"
)
```

### Business Logic Migration

```python
# OLD: Simple error message
raise CustomException(
    detail="Insufficient balance",
    code=ErrorCode.NOT_ENOUGH_BALANCE_LEFT,
    status_code=status.HTTP_400_BAD_REQUEST,
    message=_("Transaction failed"),
)

# NEW: Rich business logic error
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

## Type-Safe Error Codes

### Field Error Codes

Located at: `common/response/response_information_codes/field_error_code.py`

```python
class FieldErrorCode(Enum):
    # Generic validation
    REQUIRED = auto()
    INVALID = auto()
    INVALID_FORMAT = auto()
    BLANK = auto()
    
    # Email validation
    INVALID_EMAIL = auto()
    EMAIL_ALREADY_EXISTS = auto()
    
    # Password validation
    PASSWORD_TOO_WEAK = auto()
    PASSWORD_TOO_SHORT = auto()
    
    # Business validation
    USERNAME_TAKEN = auto()
    AGE_TOO_YOUNG = auto()
    # ... 75+ more codes
```

### General Error Codes

Located at: `common/response/response_information_codes/general_error_code.py`

```python
class GeneralErrorCode(Enum):
    # Authentication & Authorization
    ACCOUNT_LOCKED = auto()
    TOKEN_EXPIRED = auto()
    INSUFFICIENT_PERMISSIONS = auto()
    
    # Business Logic
    INSUFFICIENT_FUNDS = auto()
    DAILY_LIMIT_EXCEEDED = auto()
    MERCHANT_UNAVAILABLE = auto()
    
    # System Status
    SYSTEM_MAINTENANCE = auto()
    SERVICE_UNAVAILABLE = auto()
    RATE_LIMIT_EXCEEDED = auto()
    # ... 45+ more codes
```

## Frontend Integration

### JavaScript/TypeScript Example

```javascript
const handleApiError = (errorData) => {
  // Clear previous errors
  setFieldErrors({});
  setNotifications([]);
  
  if (errorData.errors) {
    // Handle field errors - show on form fields
    Object.keys(errorData.errors).forEach(field => {
      if (field !== 'general') {
        setFieldError(field, errorData.errors[field][0].message);
      }
    });
    
    // Handle general errors - show as notifications/toasts
    if (errorData.errors.general) {
      const notifications = errorData.errors.general.map(error => ({
        id: Date.now() + Math.random(),
        type: 'error',
        title: error.title,
        message: error.detail
      }));
      setNotifications(notifications);
    }
  } else if (errorData.title) {
    // Single error without field specifics
    setNotifications([{
      id: Date.now(),
      type: 'error', 
      title: errorData.title,
      message: errorData.detail
    }]);
  }
};
```

### Smart Error Handling by Code

```typescript
const handleFieldError = (field: string, error: FieldError) => {
  switch (error.code) {
    case 'required':
      showRequiredFieldError(field);
      break;
    case 'invalid_email':
      showEmailFormatError(field);
      highlightEmailField();
      break;
    case 'password_too_weak':
      showPasswordStrengthIndicator(field);
      break;
    default:
      showGenericFieldError(field, error.message);
  }
};

const handleGeneralError = (error: GeneralError) => {
  switch (error.code) {
    case 'insufficient_funds':
      showPaymentErrorDialog(error.title, error.detail);
      suggestAddFunds();
      break;
    case 'account_locked':
      showAccountLockedModal(error.detail);
      disableLoginForm();
      break;
    case 'system_maintenance':
      showMaintenanceBanner(error.detail);
      break;
    default:
      showGenericNotification(error.title, error.detail);
  }
};
```

## Benefits

### For Developers
- **🔧 Type Safety**: Compile-time error detection with enums
- **📝 IDE Support**: Autocomplete and documentation
- **🧪 Easier Testing**: Predictable error structures
- **🔄 Automatic Conversion**: DRF errors work without changes
- **📚 Self-Documenting**: Clear error types and codes

### For Frontend Teams
- **🎯 Predictable Structure**: Always check `errors.general` and `errors.field_name`
- **📱 Multiple Notifications**: Show multiple error notifications simultaneously
- **🎨 Field-Specific UI**: Form validation errors on relevant input fields  
- **🔔 General Notifications**: System-wide issues as toast notifications
- **⚡ Simultaneous Display**: Both field errors and general notifications together

### For End Users
- **📝 Complete Information**: See all issues at once instead of iterating
- **🎯 Clear Actions**: Understand both field-specific and system-wide issues
- **⚡ Faster Resolution**: Address multiple problems simultaneously
- **💬 Better Communication**: Rich, descriptive error messages

## Use Cases

### E-commerce Payment Flow
Multiple issues can occur simultaneously:
- Insufficient account balance
- Exceeded daily spending limit
- Credit card expired  
- Merchant temporarily unavailable

**Result**: All issues communicated at once, reducing user frustration.

### User Registration
Can combine:
- Field validation errors (invalid email format, weak password)
- General system notifications (account verification required, terms updated)
- Business logic warnings (similar username exists, promotional offer available)

### API Rate Limiting & Maintenance
During system maintenance or high load:
- Field errors for invalid data
- General notifications about system status
- Rate limiting warnings
- Feature availability notifications

## Testing

```python
def test_field_validation_error(self):
    response = self.client.post('/api/v1/users/', {
        'email': 'invalid-email',
        'password': '123'
    })
    
    self.assertEqual(response.status_code, 400)
    data = response.json()
    
    self.assertEqual(data['type'], 'validation_error')
    self.assertIn('errors', data)
    self.assertIn('email', data['errors'])

def test_business_logic_error(self):
    response = self.client.post('/api/v1/payments/', {
        'amount': 100.00
    })
    
    data = response.json()
    self.assertEqual(data['type'], 'business_logic_error')
    self.assertIn('title', data)
    self.assertIn('detail', data)
```

## Best Practices

1. **Always include instance**: Provide the request path for debugging
2. **Use meaningful titles**: Give clear, actionable error titles  
3. **Include relevant extra data**: Add context for smart client handling
4. **Choose appropriate error types**: Use the right type for the situation
5. **Maintain translations**: Ensure all error messages are translatable
6. **Use enum codes**: Leverage type-safe error codes for consistency

## Implementation Files

### Core Files
- `common/response/structured_error_response.py` - Main structured error classes
- `common/custom_exceptions/custom_exception.py` - Enhanced CustomException with structured support
- `common/exception_handling/custom_exception_handler.py` - DRF integration and conversion

### Error Code Enums
- `common/response/response_information_codes/field_error_code.py` - 75+ field validation codes
- `common/response/response_information_codes/general_error_code.py` - 45+ general error codes

### Tests
- `common/test/test_structured_errors.py` - Core functionality tests
- `common/test/test_drf_serializer_integration.py` - DRF integration tests

This structured error system provides a robust foundation for consistent, type-safe, and user-friendly error handling across your entire Django REST API. 