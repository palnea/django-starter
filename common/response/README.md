# Structured Error Response System

This directory contains the implementation of a structured error response system for Django REST Framework that follows RFC 7807 standards and provides both field-based and general error responses.

## Overview

The structured error response system provides:

- **Field-based validation errors**: Perfect for form validation with specific field error messages
- **General error messages**: For business logic errors with title and details  
- **RFC 7807 compliance**: Industry standard for API error responses
- **Backward compatibility**: Existing code continues to work
- **Enhanced client experience**: Clients can easily parse and display errors
- **Internationalization support**: All error messages are translatable

## Files

### Core Implementation

- **`structured_error_response.py`**: Main implementation of structured error response classes
- **`../custom_exceptions/custom_exception.py`**: Updated CustomException with structured error support
- **`../exception_handling/custom_exception_handler.py`**: Updated exception handler with structured response support

### Documentation & Examples

- **`../examples/structured_error_examples.py`**: Comprehensive examples of usage patterns
- **`../examples/migration_guide.md`**: Step-by-step migration guide from old to new format
- **`../test/test_structured_errors.py`**: Tests demonstrating functionality

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
                "message": "Email must contain @ symbol",
                "value": null
            }
        ]
    }
}
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
    instance="/api/v1/auth/login"
)
```

**Response:**
```json
{
    "type": "validation_error",
    "status": 400,
    "title": "Validation Error",
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
                "code": "too_short", 
                "message": "Password must be at least 8 characters long",
                "value": null
            }
        ]
    }
}
```

### 2. General Business Logic Errors (Generic Errors with Title and Description)

Generic errors are not tied to specific fields but provide rich title and description data:

```python
# For business logic errors
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
```

**Response:**
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

**Note:** Generic errors have `title` and `detail` fields but no `errors` field (which is only for field-specific validation).

## Error Types

The system supports the following error types:

- **`validation_error`**: Field-based validation errors
- **`business_logic_error`**: Business rule violations
- **`authentication_error`**: Authentication failures (401)
- **`authorization_error`**: Permission denials (403)
- **`client_error`**: Other 4xx errors
- **`server_error`**: 5xx errors

## Configuration

Enable structured responses in your Django settings:

```python
# Enable structured error responses (default: True)
USE_STRUCTURED_ERROR_RESPONSES = True

# Your existing DRF settings
REST_FRAMEWORK = {
    'EXCEPTION_HANDLER': 'common.exception_handling.custom_exception_handler.custom_exception_handler',
    # ... other settings
}
```

## Migration

### From Old Format
```python
# OLD
raise CustomException(
    detail="User not found",
    code=ErrorCode.NOT_FOUND_ERROR,
    status_code=status.HTTP_404_NOT_FOUND,
    message=_("Content not found!"),
)
```

### To New Format
```python
# NEW
raise CustomException.not_found_error(
    title=_("Content not found!"),
    detail=_("User not found"),
    instance=request.path
)
```

## Backward Compatibility

The system maintains full backward compatibility:

- Existing `CustomException` usage continues to work
- Set `USE_STRUCTURED_ERROR_RESPONSES = False` to disable structured responses
- All existing error codes and messages are preserved

## Testing

Run the tests to verify functionality:

```bash
python manage.py test common.test.test_structured_errors
```

## Best Practices

1. **Always include instance**: Provide the request path for better debugging
2. **Use meaningful titles**: Give clear, actionable error titles
3. **Include relevant extra data**: Add context that helps clients handle errors
4. **Choose appropriate error types**: Use the right error type for the situation
5. **Maintain translations**: Ensure all error messages are translatable

## Examples

For comprehensive examples and migration patterns, see:

- `../examples/structured_error_examples.py` - Usage examples
- `../examples/migration_guide.md` - Migration guide
- `../test/test_structured_errors.py` - Tests and demonstrations

## RFC 7807 Compliance

The implementation follows RFC 7807 "Problem Details for HTTP APIs" standard:

- Uses `application/problem+json` content type
- Includes standard fields: `type`, `title`, `detail`, `status`, `instance`
- Supports extension fields for additional context
- Maintains machine-readable error codes

This provides a consistent, industry-standard approach to API error responses that clients can easily parse and handle.