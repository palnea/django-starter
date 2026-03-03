"""
Examples demonstrating the new structured error response system with multiple general errors support.
This system allows for multiple notifications to be shown to users alongside field-specific validation errors.
"""

from common.custom_exceptions.custom_exception import CustomException
from common.response.structured_error_response import (
    StructuredErrorResponse,
    FieldError,
    GeneralError,
    StructuredErrorType,
)
from common.response.response_information_codes.error_code import ErrorCode


def example_field_validation_errors():
    """Example: Field validation errors only"""
    try:
        raise CustomException.validation_error(
            field_errors={
                "email": ["Invalid email format", "Email is required"],
                "password": ["Password is too short"],
            },
            title="Form Validation Failed",
            instance="/api/v1/users",
        )
    except CustomException:
        # Would produce:
        # {
        #   "type": "validation_error",
        #   "status": 400,
        #   "response_code": "ERR_GENERAL_VALIDATION_ERROR",
        #   "title": "Form Validation Failed",
        #   "detail": "Validation failed",
        #   "instance": "/api/v1/users",
        #   "errors": {
        #     "email": [
        #       {"code": "invalid", "message": "Invalid email format", "value": null},
        #       {"code": "invalid", "message": "Email is required", "value": null}
        #     ],
        #     "password": [
        #       {"code": "invalid", "message": "Password is too short", "value": null}
        #     ]
        #   }
        # }
        pass


def example_single_general_error():
    """Example: Single general error (notification)"""
    try:
        raise CustomException.business_logic_error(
            title="Insufficient Funds",
            detail="Your account balance of $50.00 is insufficient for this $75.00 transaction.",
            code=ErrorCode.NOT_ENOUGH_BALANCE_LEFT,
            instance="/api/v1/payments",
        )
    except CustomException:
        # Would produce:
        # {
        #   "type": "business_logic_error",
        #   "status": 400,
        #   "response_code": "ERR_NOT_ENOUGH_BALANCE_LEFT",
        #   "title": "Insufficient Funds",
        #   "detail": "Your account balance of $50.00 is insufficient for this $75.00 transaction.",
        #   "instance": "/api/v1/payments"
        # }
        pass


def example_multiple_general_errors():
    """Example: Multiple general errors (multiple notifications)"""
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
                {
                    "title": "Merchant Unavailable",
                    "detail": "The merchant's payment system is currently unavailable. Please try again later.",
                    "code": "merchant_unavailable",
                },
            ],
            instance="/api/v1/payments",
        )
    except CustomException:
        # Would produce:
        # {
        #   "type": "business_logic_error",
        #   "status": 400,
        #   "response_code": "ERR_AN_ERROR_OCCURED",
        #   "title": "Multiple Issues Found",
        #   "detail": "Multiple issues were identified with your request.",
        #   "instance": "/api/v1/payments",
        #   "errors": {
        #     "general": [
        #       {
        #         "title": "Insufficient Funds",
        #         "detail": "Your account balance is $50.00, but this transaction requires $75.00.",
        #         "code": "insufficient_funds"
        #       },
        #       {
        #         "title": "Daily Limit Exceeded",
        #         "detail": "You have exceeded your daily transaction limit of $500.00.",
        #         "code": "daily_limit_exceeded"
        #       },
        #       {
        #         "title": "Merchant Unavailable",
        #         "detail": "The merchant's payment system is currently unavailable. Please try again later.",
        #         "code": "merchant_unavailable"
        #       }
        #     ]
        #   }
        # }
        pass


def example_mixed_field_and_general_errors():
    """Example: Field errors + general notifications"""
    # Using StructuredErrorResponse directly for this complex scenario
    field_errors = [
        FieldError(
            field="email", code="invalid_format", message="Email must contain @ symbol"
        ),
        FieldError(
            field="password",
            code="too_weak",
            message="Password must contain special characters",
        ),
    ]

    general_errors = [
        GeneralError(
            title="Account Temporarily Locked",
            detail="Your account has been temporarily locked due to multiple failed login attempts.",
            code="account_locked",
        ),
        GeneralError(
            title="System Maintenance",
            detail="Our authentication system is undergoing maintenance. Some features may be limited.",
            code="system_maintenance",
        ),
    ]

    _response = StructuredErrorResponse(
        error_type=StructuredErrorType.VALIDATION_ERROR,
        status_code=400,
        instance="/api/v1/auth/login",
        general_errors=general_errors,
        field_errors=field_errors,
        error_code=ErrorCode.GENERAL_VALIDATION_ERROR,
    )

    # Would produce:
    # {
    #   "type": "validation_error",
    #   "status": 400,
    #   "response_code": "ERR_GENERAL_VALIDATION_ERROR",
    #   "title": "Multiple Issues Found",
    #   "detail": "Multiple issues were identified with your request.",
    #   "instance": "/api/v1/auth/login",
    #   "errors": {
    #     "general": [
    #       {
    #         "title": "Account Temporarily Locked",
    #         "detail": "Your account has been temporarily locked due to multiple failed login attempts.",
    #         "code": "account_locked"
    #       },
    #       {
    #         "title": "System Maintenance",
    #         "detail": "Our authentication system is undergoing maintenance. Some features may be limited.",
    #         "code": "system_maintenance"
    #       }
    #     ],
    #     "email": [
    #       {"code": "invalid_format", "message": "Email must contain @ symbol", "value": null}
    #     ],
    #     "password": [
    #       {"code": "too_weak", "message": "Password must contain special characters", "value": null}
    #     ]
    #   }
    # }


def example_client_side_usage():
    """
    Example of how clients can handle the structured response:

    Frontend JavaScript example:

    ```javascript
    fetch('/api/v1/users', {
        method: 'POST',
        body: JSON.stringify(userData)
    })
    .then(response => response.json())
    .then(data => {
        if (data.errors) {
            // Handle field errors - show on form fields
            if (data.errors.email) {
                showFieldError('email', data.errors.email[0].message);
            }
            if (data.errors.password) {
                showFieldError('password', data.errors.password[0].message);
            }

            // Handle general errors - show as notifications/toasts
            if (data.errors.general) {
                data.errors.general.forEach(error => {
                    showNotification(error.title, error.detail, 'error');
                });
            }
        }

        // Also show main title/detail if no specific errors
        if (data.title && !data.errors) {
            showNotification(data.title, data.detail, 'error');
        }
    });
    ```

    React example:

    ```jsx
    const handleSubmit = async (formData) => {
        try {
            const response = await api.post('/users', formData);
        } catch (error) {
            const errorData = error.response.data;

            // Clear previous errors
            setFieldErrors({});
            setNotifications([]);

            if (errorData.errors) {
                // Set field errors for form validation display
                const newFieldErrors = {};
                Object.keys(errorData.errors).forEach(field => {
                    if (field !== 'general') {
                        newFieldErrors[field] = errorData.errors[field][0].message;
                    }
                });
                setFieldErrors(newFieldErrors);

                // Add general notifications
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
        }
    };
    ```
    """
    pass


def example_drf_serializer_conversion():
    """
    Example showing how DRF ValidationError gets converted:

    Original DRF ValidationError:
    {
        "email": ["This field is required.", "Enter a valid email."],
        "non_field_errors": ["User already exists.", "Terms must be accepted."]
    }

    Converted to structured format:
    {
        "type": "validation_error",
        "status": 400,
        "title": "Multiple Issues Found",
        "detail": "Multiple issues were identified with your request.",
        "errors": {
            "email": [
                {"code": "required", "message": "This field is required.", "value": null},
                {"code": "invalid", "message": "Enter a valid email.", "value": null}
            ],
            "general": [
                {"title": "Validation Error", "detail": "User already exists.", "code": "validation_error"},
                {"title": "Validation Error", "detail": "Terms must be accepted.", "code": "validation_error"}
            ]
        }
    }
    """
    pass


# Migration examples showing before/after patterns
def migration_examples():
    """
    BEFORE (Old way):
    ```python
    raise CustomException(
        detail="Insufficient funds",
        code=ErrorCode.NOT_ENOUGH_BALANCE_LEFT,
        status_code=400
    )
    ```

    AFTER (New way - single error):
    ```python
    raise CustomException.business_logic_error(
        title="Insufficient Funds",
        detail="Your account balance is $50.00, but this transaction requires $75.00.",
        code=ErrorCode.NOT_ENOUGH_BALANCE_LEFT
    )
    ```

    NEW (Multiple errors):
    ```python
    raise CustomException.multiple_business_logic_errors(
        errors=[
            {"title": "Insufficient Funds", "detail": "Balance: $50.00, Required: $75.00"},
            {"title": "Daily Limit", "detail": "Transaction exceeds daily limit of $500.00"}
        ]
    )
    ```
    """
    pass


# =============================================================================
# NEW: STRUCTURED CODE EXAMPLES
# =============================================================================


def example_structured_field_codes():
    """Example: Using structured field error codes"""
    from common.response.response_information_codes.field_error_code import (
        FieldErrorCode,
    )

    try:
        # Type-safe field validation error
        raise CustomException.field_validation_error(
            field="email",
            code=FieldErrorCode.INVALID_EMAIL,
            message="Please enter a valid email address",
            value="invalid-email-format",
        )
    except CustomException:
        # Would produce:
        # {
        #   "type": "validation_error",
        #   "status": 400,
        #   "response_code": "ERR_GENERAL_VALIDATION_ERROR",
        #   "title": "Validation Error",
        #   "detail": "Please enter a valid email address",
        #   "errors": {
        #     "email": [
        #       {
        #         "code": "invalid_email",
        #         "message": "Please enter a valid email address",
        #         "value": "invalid-email-format"
        #       }
        #     ]
        #   }
        # }
        pass


def example_structured_general_codes():
    """Example: Using structured general error codes"""
    from common.response.response_information_codes.general_error_code import (
        GeneralErrorCode,
    )

    try:
        raise CustomException.multiple_business_logic_errors(
            errors=[
                {
                    "title": "Insufficient Funds",
                    "detail": "Your account balance is $50.00, but this transaction requires $75.00.",
                    "code": GeneralErrorCode.INSUFFICIENT_FUNDS,
                },
                {
                    "title": "Daily Limit Exceeded",
                    "detail": "You have exceeded your daily transaction limit of $500.00.",
                    "code": GeneralErrorCode.DAILY_LIMIT_EXCEEDED,
                },
                {
                    "title": "Service Maintenance",
                    "detail": "Our payment system is undergoing scheduled maintenance.",
                    "code": GeneralErrorCode.SYSTEM_MAINTENANCE,
                },
            ],
            instance="/api/v1/payments",
        )
    except CustomException:
        # Would produce:
        # {
        #   "type": "business_logic_error",
        #   "status": 400,
        #   "response_code": "ERR_AN_ERROR_OCCURED",
        #   "title": "Multiple Issues Found",
        #   "detail": "Multiple issues were identified with your request.",
        #   "instance": "/api/v1/payments",
        #   "errors": {
        #     "general": [
        #       {
        #         "title": "Insufficient Funds",
        #         "detail": "Your account balance is $50.00, but this transaction requires $75.00.",
        #         "code": "insufficient_funds"
        #       },
        #       {
        #         "title": "Daily Limit Exceeded",
        #         "detail": "You have exceeded your daily transaction limit of $500.00.",
        #         "code": "daily_limit_exceeded"
        #       },
        #       {
        #         "title": "Service Maintenance",
        #         "detail": "Our payment system is undergoing scheduled maintenance.",
        #         "code": "system_maintenance"
        #       }
        #     ]
        #   }
        # }
        pass


def example_mixed_structured_codes():
    """Example: Mixed field and general errors with structured codes"""
    from common.response.structured_error_response import (
        StructuredErrorResponse,
        FieldError,
        GeneralError,
    )
    from common.response.response_information_codes.field_error_code import (
        FieldErrorCode,
    )
    from common.response.response_information_codes.general_error_code import (
        GeneralErrorCode,
    )

    field_errors = [
        FieldError(
            field="email",
            code=FieldErrorCode.INVALID_EMAIL,
            message="Email format is invalid",
        ),
        FieldError(
            field="password",
            code=FieldErrorCode.PASSWORD_TOO_WEAK,
            message="Password must contain special characters",
        ),
    ]

    general_errors = [
        GeneralError(
            title="Account Temporarily Locked",
            detail="Your account has been temporarily locked due to multiple failed login attempts.",
            code=GeneralErrorCode.ACCOUNT_LOCKED,
        ),
        GeneralError(
            title="System Maintenance",
            detail="Our authentication system is undergoing maintenance. Some features may be limited.",
            code=GeneralErrorCode.SYSTEM_MAINTENANCE,
        ),
    ]

    _response = StructuredErrorResponse(
        error_type=StructuredErrorType.VALIDATION_ERROR,
        status_code=400,
        instance="/api/v1/auth/login",
        general_errors=general_errors,
        field_errors=field_errors,
        error_code=ErrorCode.GENERAL_VALIDATION_ERROR,
    )

    # Would produce structured response with typed error codes


def example_drf_auto_conversion():
    """Example: DRF ValidationError auto-conversion to structured codes"""
    from rest_framework.exceptions import ValidationError

    # DRF raises this validation error
    _drf_error = ValidationError(
        {
            "email": ["This field is required.", "Enter a valid email address."],
            "password": ["This field may not be blank."],
            "non_field_errors": ["User with this email already exists."],
        }
    )

    # Our handler automatically converts it to:
    # {
    #   "type": "validation_error",
    #   "status": 400,
    #   "title": "Multiple Issues Found",
    #   "detail": "Multiple issues were identified with your request.",
    #   "errors": {
    #     "email": [
    #       {"code": "required", "message": "This field is required.", "value": null},
    #       {"code": "invalid_email", "message": "Enter a valid email address.", "value": null}
    #     ],
    #     "password": [
    #       {"code": "blank", "message": "This field may not be blank.", "value": null}
    #     ],
    #     "general": [
    #       {
    #         "title": "Validation Error",
    #         "detail": "User with this email already exists.",
    #         "code": "validation_error"
    #       }
    #     ]
    #   }
    # }


def example_client_side_code_handling():
    """
    Example of how clients can handle structured error codes:

    Frontend TypeScript example:

    ```typescript
    interface ErrorResponse {
      type: string;
      status: number;
      response_code: string;
      title: string;
      detail: string;
      errors?: {
        [field: string]: FieldError[];
        general?: GeneralError[];
      };
    }

    interface FieldError {
      code: 'required' | 'invalid_email' | 'password_too_weak' | 'too_short';
      message: string;
      value: any;
    }

    interface GeneralError {
      title: string;
      detail: string;
      code: 'insufficient_funds' | 'account_locked' | 'system_maintenance';
    }

    const handleApiError = (errorData: ErrorResponse) => {
      if (errorData.errors) {
        // Handle field errors with specific code logic
        Object.entries(errorData.errors).forEach(([field, errors]) => {
          if (field !== 'general') {
            errors.forEach(error => {
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
            });
          }
        });

        // Handle general errors with specific code logic
        if (errorData.errors.general) {
          errorData.errors.general.forEach(error => {
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
          });
        }
      } else {
        // Single error
        showGenericNotification(errorData.title, errorData.detail);
      }
    };
    ```
    """
    pass
