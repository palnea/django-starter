from rest_framework.exceptions import APIException, ValidationError
from structlog import get_logger
from django.utils.translation import gettext_lazy as _
from typing import Dict, Any

from common.custom_exceptions.custom_exception import CustomException
from common.exception_handling.exception_handler_mapper import (
    EXCEPTION_HANDLER_MAPPER,
    API_EXCEPTION_HANDLER_MAPPER,
)

# Legacy imports removed - now using only structured responses
from common.response.structured_error_response import (
    StructuredErrorResponse,
    FieldError,
    GeneralError,
    StructuredErrorType,
)
from common.response.response_information_codes.error_code import ErrorCode
from common.response.response_information_codes.field_error_code import FieldErrorCode
from common.response.response_information_codes.general_error_code import (
    GeneralErrorCode,
)

log = get_logger(__name__)


def get_request_path(context):
    """Get the request path from context"""
    request = context.get("request")
    if request:
        return request.get_full_path()
    return None


def create_structured_response_from_custom_exception(
    exc: CustomException, context: Dict[str, Any]
):
    """Create structured error response from CustomException"""
    request_path = get_request_path(context)

    # Handle field errors if present
    field_errors = []
    if exc.has_field_errors():
        for field_name, errors in exc.field_errors.items():
            for error in errors:
                # Convert string error codes to FieldErrorCode enum
                if isinstance(error, FieldErrorCode):
                    # Already a structured code, as built by field_validation_error.
                    # The human-readable message lives on the exception detail.
                    error_code = error
                    error_message = str(exc.detail)
                elif isinstance(error, str):
                    # Simple string error - use invalid code
                    error_code = FieldErrorCode.INVALID
                    error_message = error
                else:
                    # Error object with code attribute
                    error_code_str = getattr(error, "code", "invalid")
                    error_code = FieldErrorCode.from_string(error_code_str)
                    error_message = str(error)

                field_errors.append(
                    FieldError(field=field_name, code=error_code, message=error_message)
                )

    # Handle general errors - check for multiple errors in extra_data
    general_errors = []
    if exc.extra_data and "multiple_general_errors" in exc.extra_data:
        # Multiple general errors case
        for error_data in exc.extra_data["multiple_general_errors"]:
            # Convert string code to GeneralErrorCode enum if provided
            code = error_data.get("code", None)
            if code and isinstance(code, str):
                code = GeneralErrorCode.from_string(code)

            general_errors.append(
                GeneralError(
                    title=error_data.get("title", "Error"),
                    detail=error_data.get("detail", "An error occurred"),
                    code=code,
                )
            )
    elif exc.title:
        # Single general error case
        general_errors.append(
            GeneralError(
                title=exc.title,
                detail=str(exc.detail),
                code=exc.code.value if exc.code else None,
            )
        )

    # Determine error type
    if hasattr(exc, "error_type") and exc.error_type:
        # Use explicitly set error type
        if exc.error_type == "business_logic_error":
            error_type = StructuredErrorType.BUSINESS_LOGIC_ERROR
        elif exc.error_type == "authentication_error":
            error_type = StructuredErrorType.AUTHENTICATION_ERROR
        elif exc.error_type == "authorization_error":
            error_type = StructuredErrorType.AUTHORIZATION_ERROR
        elif exc.error_type == "validation_error":
            error_type = StructuredErrorType.VALIDATION_ERROR
        elif exc.error_type == "not_found_error":
            error_type = StructuredErrorType.NOT_FOUND_ERROR
        elif exc.error_type == "client_error":
            error_type = StructuredErrorType.CLIENT_ERROR
        elif exc.error_type == "server_error":
            error_type = StructuredErrorType.SERVER_ERROR
        else:
            error_type = StructuredErrorType.CLIENT_ERROR
    elif field_errors:
        error_type = StructuredErrorType.VALIDATION_ERROR
    elif exc.status_code == 401:
        error_type = StructuredErrorType.AUTHENTICATION_ERROR
    elif exc.status_code == 403:
        error_type = StructuredErrorType.AUTHORIZATION_ERROR
    elif exc.status_code == 404:
        error_type = StructuredErrorType.NOT_FOUND_ERROR
    elif 400 <= exc.status_code < 500:
        error_type = StructuredErrorType.CLIENT_ERROR
    else:
        error_type = StructuredErrorType.SERVER_ERROR

    # Filter out multiple_general_errors from extra_data for the response
    response_extra_data = {
        k: v for k, v in exc.extra_data.items() if k != "multiple_general_errors"
    }

    structured_response = StructuredErrorResponse(
        error_type=error_type,
        status_code=exc.status_code,
        instance=request_path,
        general_errors=general_errors,
        field_errors=field_errors,
        error_code=exc.code,
        extra_data=response_extra_data,
    )

    return structured_response.to_response()


def create_structured_response_from_validation_error(
    exc: ValidationError, context: Dict[str, Any]
):
    """Create structured error response from DRF ValidationError with structured codes"""
    request_path = get_request_path(context)

    # Convert DRF validation errors to structured format
    field_errors = []
    general_errors = []

    def process_error_detail(detail, field_prefix=""):
        """Recursively process error details to handle nested serializers and lists"""
        if isinstance(detail, dict):
            for field_name, errors in detail.items():
                current_field = (
                    f"{field_prefix}.{field_name}" if field_prefix else field_name
                )

                if field_name == "non_field_errors":
                    # Handle non-field errors as general errors
                    if isinstance(errors, list):
                        for error in errors:
                            general_errors.append(
                                GeneralError(
                                    title=_("Validation Error"),
                                    detail=str(error),
                                    code=GeneralErrorCode.VALIDATION_ERROR,
                                )
                            )
                    else:
                        general_errors.append(
                            GeneralError(
                                title=_("Validation Error"),
                                detail=str(errors),
                                code=GeneralErrorCode.VALIDATION_ERROR,
                            )
                        )
                else:
                    # Handle field-specific errors
                    process_error_detail(errors, current_field)

        elif isinstance(detail, list):
            for idx, error in enumerate(detail):
                if isinstance(error, dict):
                    # Handle list of objects (list serializer errors)
                    current_field = (
                        f"{field_prefix}.{idx}" if field_prefix else str(idx)
                    )
                    process_error_detail(error, current_field)
                else:
                    # Handle list of error messages for a single field
                    error_code_str = (
                        getattr(error, "code", "invalid")
                        if hasattr(error, "code")
                        else "invalid"
                    )
                    error_code = FieldErrorCode.from_string(error_code_str)

                    field_errors.append(
                        FieldError(
                            field=field_prefix, code=error_code, message=str(error)
                        )
                    )
        else:
            # Handle single error message
            error_code_str = (
                getattr(detail, "code", "invalid")
                if hasattr(detail, "code")
                else "invalid"
            )
            error_code = FieldErrorCode.from_string(error_code_str)

            field_errors.append(
                FieldError(field=field_prefix, code=error_code, message=str(detail))
            )

    # Process the validation error detail
    if hasattr(exc, "detail"):
        process_error_detail(exc.detail)
    else:
        general_errors.append(
            GeneralError(
                title=_("Validation Error"),
                detail=str(exc),
                code=GeneralErrorCode.VALIDATION_ERROR,
            )
        )

    structured_response = StructuredErrorResponse(
        error_type=StructuredErrorType.VALIDATION_ERROR,
        status_code=exc.status_code,
        instance=request_path,
        general_errors=general_errors,
        field_errors=field_errors,
        error_code=ErrorCode.GENERAL_VALIDATION_ERROR,
    )

    return structured_response.to_response()


def create_structured_response_from_api_exception(
    exc: APIException, context: Dict[str, Any]
):
    """Create structured error response from other API exceptions"""
    request_path = get_request_path(context)

    exception_parameters = API_EXCEPTION_HANDLER_MAPPER.get(
        exc.__class__, API_EXCEPTION_HANDLER_MAPPER.get(APIException)
    )

    # Determine error type
    if exc.status_code == 401:
        error_type = StructuredErrorType.AUTHENTICATION_ERROR
    elif exc.status_code == 403:
        error_type = StructuredErrorType.AUTHORIZATION_ERROR
    elif 400 <= exc.status_code < 500:
        error_type = StructuredErrorType.CLIENT_ERROR
    else:
        error_type = StructuredErrorType.SERVER_ERROR

    general_error = GeneralError(
        title=_(exception_parameters.response_message),
        detail=str(exc.detail),
        code=exception_parameters.response_information_code.value,
    )

    structured_response = StructuredErrorResponse(
        error_type=error_type,
        status_code=exc.status_code,
        instance=request_path,
        general_errors=[general_error],
        error_code=exception_parameters.response_information_code,
    )

    return structured_response.to_response()


def create_structured_response_from_django_exception(
    exc: Exception, context: Dict[str, Any]
):
    """Create structured error response from Django exceptions using the exception mapper"""
    request_path = get_request_path(context)

    exception_handler_func = EXCEPTION_HANDLER_MAPPER.get(exc.__class__)
    if callable(exception_handler_func):
        exception_parameters = exception_handler_func(exc)
    else:
        # Fallback to generic handling
        exception_parameters = EXCEPTION_HANDLER_MAPPER[Exception](exc)

    # Determine error type based on status code
    if exception_parameters.response_status == 401:
        error_type = StructuredErrorType.AUTHENTICATION_ERROR
    elif exception_parameters.response_status == 403:
        error_type = StructuredErrorType.AUTHORIZATION_ERROR
    elif 400 <= exception_parameters.response_status < 500:
        error_type = StructuredErrorType.CLIENT_ERROR
    else:
        error_type = StructuredErrorType.SERVER_ERROR

    general_error = GeneralError(
        title=_(exception_parameters.response_message),
        detail=_(exception_parameters.error_msg),
        code=exception_parameters.response_information_code.value,
    )

    structured_response = StructuredErrorResponse(
        error_type=error_type,
        status_code=exception_parameters.response_status,
        instance=request_path,
        general_errors=[general_error],
        error_code=exception_parameters.response_information_code,
    )

    return structured_response.to_response()


def create_structured_response_from_generic_exception(
    exc: Exception, context: Dict[str, Any]
):
    """Create structured error response from generic exception"""
    request_path = get_request_path(context)

    general_error = GeneralError(
        title=_("Server Error"),
        detail=_("An internal server error occurred. Please try again later."),
        code=GeneralErrorCode.UNKNOWN_ERROR,
    )

    structured_response = StructuredErrorResponse(
        error_type=StructuredErrorType.SERVER_ERROR,
        status_code=500,
        instance=request_path,
        general_errors=[general_error],
        error_code=ErrorCode.INTERNAL_SERVER_ERROR,
    )

    return structured_response.to_response()


def custom_exception_handler(exc, context):
    """
    Custom exception handler that returns structured error responses
    """
    # Handle CustomException with structured responses
    if isinstance(exc, CustomException):
        response = create_structured_response_from_custom_exception(exc, context)
        log_structured_response(exc, context, response)
        return response

    # Handle DRF ValidationError with structured responses
    if isinstance(exc, ValidationError):
        response = create_structured_response_from_validation_error(exc, context)
        log_structured_response(exc, context, response)
        return response

    # Handle other API exceptions with structured responses
    if isinstance(exc, APIException):
        response = create_structured_response_from_api_exception(exc, context)
        log_structured_response(exc, context, response)
        return response

    # Handle Django exceptions (like IntegrityError) using the exception mapper
    if exc.__class__ in EXCEPTION_HANDLER_MAPPER:
        response = create_structured_response_from_django_exception(exc, context)
        log_structured_response(exc, context, response)
        return response

    # Handle any other exceptions as server errors
    response = create_structured_response_from_generic_exception(exc, context)
    log_structured_response(exc, context, response)
    return response


def log_structured_response(exc, context, response):
    """Log structured error responses"""
    view_class = (
        context.get("view").__class__.__name__
        if context.get("view", None) is not None
        else None
    )
    request_data = None
    request = context.get("request", None)
    if request is not None:
        # Try to get data from DRF request, fallback to None if not available
        request_data = getattr(request, "data", None)
    path = (
        context.get("request").get_full_path()
        if context.get("request", None) is not None
        else None
    )
    request_method = None
    request = context.get("request", None)
    if request is not None:
        # Try to get method from request, fallback to None if not available
        request_method = getattr(request, "method", None)

    # Determine log level based on status code
    if 400 <= response.status_code < 500:
        log_func = log.warning
    else:
        log_func = log.error

    log_func(
        f"Structured error response: {view_class}",
        view_name=view_class,
        exception_name=exc.__class__.__name__,
        exception_detail=str(exc),
        request_body=request_data,
        request_path=path,
        request_method=request_method,
        response_status=response.status_code,
        response_data=response.data,
        is_successful=False,
    )
