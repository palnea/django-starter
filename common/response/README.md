# Structured Error Response System

A comprehensive Django REST Framework error handling system that provides RFC 7807 compliant, structured error responses with automatic DRF integration and type-safe error codes.

## Overview

This structured error response system transforms inconsistent error formats into a standardized structure supporting:

- **Field-based validation errors** - Perfect for form validation with field-specific messages
- **General business logic errors** - Rich error messages with titles and details
- **Multiple error reporting** - Handle complex scenarios with multiple simultaneous issues
- **Type-safe error codes** - Python enums for IDE autocomplete and type safety
- **RFC 7807 compliance** - Industry standard for API error responses
- **Automatic DRF integration** - No code changes needed for existing serializers
- **Backward compatibility** - Existing code continues to work
- **Enhanced client experience** - Clients can easily parse and display errors
- **Internationalization support** - All error messages are translatable

## Files

### Core Implementation

- **`structured_error_response.py`**: Main implementation of structured error response classes
- **`../custom_exceptions/custom_exception.py`**: Updated CustomException with structured error support
- **`../exception_handling/custom_exception_handler.py`**: Updated exception handler with structured response support

### Error Code Enums

- **`response_information_codes/field_error_code.py`**: 75+ field validation codes
- **`response_information_codes/general_error_code.py`**: 45+ general error codes
- **`response_information_codes/error_code.py`**: Legacy error codes
- **`response_information_codes/message_code.py`**: Message codes

### Documentation & Examples

- **`../examples/structured_error_examples.py`**: Comprehensive examples of usage patterns
- **`../examples/migration_guide.md`**: Step-by-step migration guide from old to new format
- **`../test/test_structured_errors.py`**: Tests demonstrating functionality
- **`../test/test_drf_serializer_integration.py`**: DRF integration tests

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
        "message": "Please enter a valid email address"
      }
    ],
    "password": [
      {
        "code": "required",
        "message": "Password is required"
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
      {"code": "invalid_format", "message": "Email must contain @ symbol"}
    ],
    "password": [
      {"code": "too_weak", "message": "Password must contain special characters"}
    ],
    "general": [
      {
        "code": "account_locked",
        "message": "Your account has been temporarily locked due to multiple failed login attempts.",
        "title": "Account Temporarily Locked"
      }
    ]
  }
}
```

## Quick Start

### DRF Serializer Validation (Automatic Conversion)

**No code changes needed!** All DRF serializer validation errors are automatically converted to structured format:

```python
class UserSerializer(serializers.ModelSerializer):
    def validate_email(self, value):
        if "@" not in value:
            # This automatically becomes a structured error!
            raise ValidationError("Email must contain @ symbol")
        return value
```

**Automatic Response:**
```json
{
    "type": "validation_error",
    "status": 400,
    "title": "Validation Error",
    "detail": "The request data is invalid.",
    "instance": "/api/v1/users/",
    "errors": {
        "email": [
            {
                "code": "invalid",
                "message": "Email must contain @ symbol"
            }
        ]
    }
}
```

## Usage Examples

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
)

# Business logic with enum codes  
raise CustomException.business_logic_error(
    title="Insufficient Funds",
    detail="Your account balance is $50.00, but this transaction requires $75.00.",
    code=GeneralErrorCode.INSUFFICIENT_FUNDS,
)
```

### 1. Field-based Validation Errors

```python
# For form validation errors
raise CustomException.validation_error(
    field_errors={
        "email": ["The email format is incorrect"],
        "password": ["Password must be at least 8 characters long"]
    },
    title=_("Validation Error"),
)
```

### 2. General Business Logic Errors

Generic errors are not tied to specific fields but provide rich title and description data:

```python
# For business logic errors
raise CustomException.business_logic_error(
    title=_("Insufficient Balance"),
    detail=_("Your account balance is $10.50, but this transaction requires $25.00"),
    code=ErrorCode.NOT_ENOUGH_BALANCE_LEFT,
    extra_data={
        "balance": 10.50,
        "required_amount": 25.00
    }
)
```

### 3. Multiple Business Logic Errors

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
)
```

### 4. Custom Validation with Rich Context

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

## Type-Safe Error Codes

### Field Error Codes

Located at: `response_information_codes/field_error_code.py`

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

Located at: `response_information_codes/general_error_code.py`

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

## Configuration

Enable structured responses in your Django settings:

```python
# Your existing DRF settings
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
    extra_data={
        "current_balance": current_balance,
        "required_amount": required_amount
    }
)
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

## Backward Compatibility

The system maintains full backward compatibility:

- Existing `CustomException` usage continues to work
- All existing error codes and messages are preserved

## Testing

Run the tests to verify functionality:

```bash
python manage.py test common.test.test_structured_errors
python manage.py test common.test.test_drf_serializer_integration
```

### Test Examples

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

## Best Practices

1. **Always include instance**: Provide the request path for better debugging
2. **Use meaningful titles**: Give clear, actionable error titles
3. **Include relevant extra data**: Add context that helps clients handle errors
4. **Choose appropriate error types**: Use the right error type for the situation
5. **Maintain translations**: Ensure all error messages are translatable
6. **Use enum codes**: Leverage type-safe error codes for consistency

## Examples

For comprehensive examples and migration patterns, see:

- `../examples/structured_error_examples.py` - Usage examples
- `../examples/migration_guide.md` - Migration guide
- `../test/test_structured_errors.py` - Tests and demonstrations
- `../test/test_drf_serializer_integration.py` - DRF integration tests

## RFC 7807 Compliance

The implementation follows RFC 7807 "Problem Details for HTTP APIs" standard:

- Uses `application/problem+json` content type
- Includes standard fields: `type`, `title`, `detail`, `status`, `instance`
- Supports extension fields for additional context
- Maintains machine-readable error codes

This provides a consistent, industry-standard approach to API error responses that clients can easily parse and handle.