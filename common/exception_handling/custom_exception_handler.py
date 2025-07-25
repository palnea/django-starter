from django.conf import settings
from rest_framework.exceptions import APIException, ValidationError
from rest_framework.views import exception_handler as drf_exception_handler
from structlog import get_logger
from django.utils.translation import gettext_lazy as _
from typing import Dict, List, Any

from common.custom_exceptions.custom_exception import CustomException
from common.exception_handling.exception_handler_mapper import (
    EXCEPTION_HANDLER_MAPPER,
    API_EXCEPTION_HANDLER_MAPPER,
)
from common.response.view_response import ViewFailResponse, log_view_response
from common.response.structured_error_response import (
    StructuredErrorResponse, 
    FieldError, 
    GeneralError,
    StructuredErrorType,
    convert_drf_validation_errors_to_structured
)

log = get_logger(__name__)


def get_request_path(context):
    """Get the request path from context"""
    request = context.get("request")
    if request:
        return request.get_full_path()
    return None


def create_structured_response_from_custom_exception(exc: CustomException, context: Dict[str, Any]):
    """Create structured error response from CustomException"""
    request_path = get_request_path(context)
    
    # Handle field errors if present
    field_errors = []
    if exc.has_field_errors():
        for field_name, errors in exc.field_errors.items():
            for error in errors:
                field_errors.append(FieldError(
                    field=field_name,
                    code=getattr(error, 'code', 'invalid') if hasattr(error, 'code') else 'invalid',
                    message=str(error)
                ))
    
    # Create general error if needed
    general_error = None
    if exc.title:
        general_error = GeneralError(
            title=exc.title,
            detail=str(exc.detail),
            code=exc.code.value if exc.code else None
        )
    
    # Determine error type
    if field_errors:
        error_type = StructuredErrorType.VALIDATION_ERROR
    elif exc.status_code == 401:
        error_type = StructuredErrorType.AUTHENTICATION_ERROR
    elif exc.status_code == 403:
        error_type = StructuredErrorType.AUTHORIZATION_ERROR
    elif 400 <= exc.status_code < 500:
        error_type = StructuredErrorType.CLIENT_ERROR
    else:
        error_type = StructuredErrorType.SERVER_ERROR
    
    structured_response = StructuredErrorResponse(
        error_type=error_type,
        status_code=exc.status_code,
        instance=exc.instance or request_path,
        general_error=general_error,
        field_errors=field_errors,
        error_code=exc.code,
        extra_data=exc.extra_data
    )
    
    return structured_response.to_response()


def create_structured_response_from_validation_error(exc: ValidationError, context: Dict[str, Any]):
    """Create structured error response from DRF ValidationError"""
    request_path = get_request_path(context)
    
    # Convert DRF validation errors to structured format
    field_errors = []
    general_errors = []
    
    def process_error_detail(detail, field_prefix=""):
        """Recursively process error details to handle nested serializers and lists"""
        if isinstance(detail, dict):
            for field_name, errors in detail.items():
                current_field = f"{field_prefix}.{field_name}" if field_prefix else field_name
                
                if field_name == 'non_field_errors':
                    # Handle non-field errors as general errors
                    if isinstance(errors, list):
                        for error in errors:
                            general_errors.append(str(error))
                    else:
                        general_errors.append(str(errors))
                else:
                    # Handle field-specific errors
                    process_error_detail(errors, current_field)
                    
        elif isinstance(detail, list):
            for idx, error in enumerate(detail):
                if isinstance(error, dict):
                    # Handle list of objects (list serializer errors)
                    current_field = f"{field_prefix}.{idx}" if field_prefix else str(idx)
                    process_error_detail(error, current_field)
                else:
                    # Handle list of error messages for a single field
                    field_errors.append(FieldError(
                        field=field_prefix,
                        code=getattr(error, 'code', 'invalid') if hasattr(error, 'code') else 'invalid',
                        message=str(error)
                    ))
        else:
            # Handle single error message
            field_errors.append(FieldError(
                field=field_prefix,
                code=getattr(detail, 'code', 'invalid') if hasattr(detail, 'code') else 'invalid',
                message=str(detail)
            ))
    
    # Process the validation error detail
    if hasattr(exc, 'detail'):
        process_error_detail(exc.detail)
    else:
        general_errors.append(str(exc))
    
    # Create general error if we have non-field errors
    general_error = None
    if general_errors:
        # If we have multiple general errors, combine them appropriately
        if len(general_errors) == 1:
            general_error = GeneralError(
                title=_("Validation Error"),
                detail=general_errors[0],
                code="validation_error"
            )
        else:
            # Multiple general errors - create a comprehensive message
            combined_detail = ". ".join(general_errors)
            general_error = GeneralError(
                title=_("Validation Errors"),
                detail=combined_detail,
                code="validation_error"
            )
    
    structured_response = StructuredErrorResponse(
        error_type=StructuredErrorType.VALIDATION_ERROR,
        status_code=exc.status_code,
        instance=request_path,
        general_error=general_error,
        field_errors=field_errors
    )
    
    return structured_response.to_response()


def create_structured_response_from_api_exception(exc: APIException, context: Dict[str, Any]):
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
        code=exception_parameters.response_information_code.value
    )
    
    structured_response = StructuredErrorResponse(
        error_type=error_type,
        status_code=exc.status_code,
        instance=request_path,
        general_error=general_error,
        error_code=exception_parameters.response_information_code
    )
    
    return structured_response.to_response()


def custom_exception_handler(exc, context):
    """
    Custom exception handler that supports both legacy and structured error responses
    """
    # Check if we should use structured responses (can be controlled via settings)
    use_structured_responses = getattr(settings, 'USE_STRUCTURED_ERROR_RESPONSES', True)
    
    # Handle CustomException with structured responses
    if isinstance(exc, CustomException) and use_structured_responses and exc.is_structured():
        response = create_structured_response_from_custom_exception(exc, context)
        log_structured_response(exc, context, response)
        return response
    
    # Handle DRF ValidationError with structured responses
    if isinstance(exc, ValidationError) and use_structured_responses:
        response = create_structured_response_from_validation_error(exc, context)
        log_structured_response(exc, context, response)
        return response
    
    # Handle other API exceptions with structured responses
    if isinstance(exc, APIException) and use_structured_responses:
        response = create_structured_response_from_api_exception(exc, context)
        log_structured_response(exc, context, response)
        return response
    
    # Fall back to legacy handling for backward compatibility
    if isinstance(exc, CustomException):
        view_response = ViewFailResponse(
            exception=exc,
            error_msg=exc.detail,
            response_status=exc.status_code,
            response_information_code=exc.code,
            response_message=exc.message,
        )
    elif isinstance(exc, APIException):
        exception_parameters = API_EXCEPTION_HANDLER_MAPPER.get(
            exc.__class__, API_EXCEPTION_HANDLER_MAPPER.get(APIException)
        )
        view_response = ViewFailResponse(
            exception=exc,
            error_msg=exc.detail,
            response_status=exc.status_code,
            response_information_code=exception_parameters.response_information_code,
            response_message=_(exception_parameters.response_message),
        )
    else:
        exception_handling_parameters = EXCEPTION_HANDLER_MAPPER.get(
            exc.__class__, EXCEPTION_HANDLER_MAPPER.get(Exception)
        )(exc)
        if settings.DEBUG:
            exception_handling_parameters.error_msg += " Exception: " + str(exc)
        view_response = ViewFailResponse(
            exception=exc,
            error_msg=exception_handling_parameters.error_msg,
            response_status=exception_handling_parameters.response_status,
            response_information_code=exception_handling_parameters.response_information_code,
            response_message=_(exception_handling_parameters.response_message),
        )

    view_class = (
        context.get("view").__class__.__name__
        if context.get("view", None) is not None
        else None
    )
    request_data = (
        context.get("request").data
        if context.get("request", None) is not None
        else None
    )
    path = (
        context.get("request").get_full_path()
        if context.get("request", None) is not None
        else None
    )
    request_method = (
        context.get("request").method
        if context.get("request", None) is not None
        else None
    )

    log_view_response(
        struct_logger=log,
        view_name=view_class,
        method_name="",
        request_body=request_data,
        request_path=path,
        request_method=request_method,
        view_response=view_response,
    )
    
    return view_response.rest_response


def log_structured_response(exc, context, response):
    """Log structured error responses"""
    view_class = (
        context.get("view").__class__.__name__
        if context.get("view", None) is not None
        else None
    )
    request_data = (
        context.get("request").data
        if context.get("request", None) is not None
        else None
    )
    path = (
        context.get("request").get_full_path()
        if context.get("request", None) is not None
        else None
    )
    request_method = (
        context.get("request").method
        if context.get("request", None) is not None
        else None
    )
    
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
