from django.utils.translation import gettext_lazy as _
from rest_framework import status
from rest_framework.exceptions import APIException, _get_error_details
from typing import Dict, List, Any, Optional, Union

from common.response.response_information_codes.error_code import ErrorCode
from common.response.response_information_codes.field_error_code import FieldErrorCode
from common.response.response_information_codes.general_error_code import (
    GeneralErrorCode,
)


class CustomException(APIException):
    """
    Base class for REST framework exceptions.
    Subclasses should provide `.status_code` and `.default_detail` properties.
    Now supports structured error responses with typed error codes.
    """

    status_code = status.HTTP_500_INTERNAL_SERVER_ERROR
    default_detail = _("A server error occurred.")
    default_code = ErrorCode.INTERNAL_SERVER_ERROR
    default_message = _("A server error occurred.")

    def __init__(
        self,
        detail=None,
        code=None,
        status_code=None,
        message=None,
        field_errors: Optional[Dict[str, List[Union[str, FieldErrorCode]]]] = None,
        title: Optional[str] = None,
        instance: Optional[str] = None,
        extra_data: Optional[Dict[str, Any]] = None,
        error_type: Optional[str] = None,
    ):
        if detail is None:
            detail = self.default_detail
        if code is None:
            code = self.default_code
        if message is None:
            message = self.default_message

        self.code = code
        self.message = message
        self.detail = _get_error_details(detail, code)
        self.field_errors = field_errors or {}
        self.title = title or str(
            self.default_message
        )  # Ensure all exceptions have a title
        self.instance = instance
        self.extra_data = extra_data or {}
        self.error_type = error_type

        if status_code is not None:
            self.status_code = status_code

    def __str__(self):
        return str(self.detail)

    @classmethod
    def from_exception(
        cls,
        exc: Exception,
        code=None,
        status_code=None,
        message: str = None,
        title: str = None,
        instance: str = None,
    ):
        detail = str(exc)
        return cls(detail, code, status_code, message, title=title, instance=instance)

    @classmethod
    def validation_error(
        cls,
        field_errors: Dict[str, List[Union[str, FieldErrorCode]]] = None,
        general_message: str = None,
        title: str = None,
        instance: str = None,
        status_code: int = status.HTTP_400_BAD_REQUEST,
    ):
        """Create a validation error with field-specific errors using structured codes"""
        return cls(
            detail=general_message or _("Validation failed"),
            code=ErrorCode.GENERAL_VALIDATION_ERROR,
            status_code=status_code,
            message=_("Request parameters are not valid!"),
            field_errors=field_errors,
            title=title or _("Validation Error"),
            instance=instance,
        )

    @classmethod
    def business_logic_error(
        cls,
        title: str,
        detail: str,
        code: ErrorCode = None,
        status_code: int = status.HTTP_400_BAD_REQUEST,
        instance: str = None,
        extra_data: Dict[str, Any] = None,
    ):
        """Create a business logic error"""
        return cls(
            detail=detail,
            code=code or ErrorCode.AN_ERROR_OCCURED,
            status_code=status_code,
            message=title,
            title=title,
            instance=instance,
            extra_data=extra_data,
            error_type="business_logic_error",
        )

    @classmethod
    def authentication_error(
        cls, title: str = None, detail: str = None, instance: str = None
    ):
        """Create an authentication error"""
        return cls(
            detail=detail or _("Authentication credentials were missing or invalid."),
            code=ErrorCode.AUTHENTICATION_FAILED,
            status_code=status.HTTP_401_UNAUTHORIZED,
            message=title or _("Authentication Failed"),
            title=title or _("Authentication Failed"),
            instance=instance,
            error_type="authentication_error",
        )

    @classmethod
    def authorization_error(
        cls, title: str = None, detail: str = None, instance: str = None
    ):
        """Create an authorization error"""
        return cls(
            detail=detail or _("You do not have permission to perform this action."),
            code=ErrorCode.PERMISSION_DENIED,
            status_code=status.HTTP_403_FORBIDDEN,
            message=title or _("Access Denied"),
            title=title or _("Access Denied"),
            instance=instance,
            error_type="authorization_error",
        )

    @classmethod
    def not_found_error(
        cls, title: str = None, detail: str = None, instance: str = None
    ):
        """Create a not found error"""
        return cls(
            detail=detail or _("The requested resource was not found."),
            code=ErrorCode.NOT_FOUND_ERROR,
            status_code=status.HTTP_404_NOT_FOUND,
            message=title or _("Not Found"),
            title=title or _("Not Found"),
            instance=instance,
        )

    @classmethod
    def multiple_business_logic_errors(
        cls,
        errors: List[
            Dict[str, Union[str, GeneralErrorCode]]
        ],  # Now supports typed codes
        status_code: int = status.HTTP_400_BAD_REQUEST,
        instance: str = None,
        extra_data: Dict[str, Any] = None,
    ):
        """
        Create a response with multiple business logic errors using structured codes.

        Args:
            errors: List of error dictionaries with "title", "detail", and optionally "code"
            status_code: HTTP status code
            instance: Request path or resource identifier
            extra_data: Additional response data

        Example:
            errors=[
                {
                    "title": "Insufficient Funds",
                    "detail": "Your balance is too low",
                    "code": GeneralErrorCode.INSUFFICIENT_FUNDS
                },
                {
                    "title": "Daily Limit Exceeded",
                    "detail": "You've exceeded your daily limit",
                    "code": GeneralErrorCode.DAILY_LIMIT_EXCEEDED
                }
            ]
        """
        main_title = _("Multiple Issues Found")
        main_detail = _("Multiple issues were identified with your request.")

        # Store the multiple errors in extra_data for the handler to process
        multiple_errors_data = extra_data or {}
        multiple_errors_data["multiple_general_errors"] = errors

        return cls(
            detail=main_detail,
            code=ErrorCode.AN_ERROR_OCCURED,
            status_code=status_code,
            message=main_title,
            title=main_title,
            instance=instance,
            extra_data=multiple_errors_data,
            error_type="business_logic_error",
        )

    @classmethod
    def field_validation_error(
        cls,
        field: str,
        code: FieldErrorCode,
        message: str,
        instance: str = None,
        value: Any = None,
    ):
        """
        Create a single field validation error with structured code.

        Example:
            CustomException.field_validation_error(
                field="email",
                code=FieldErrorCode.INVALID_EMAIL,
                message="Please enter a valid email address",
                value="invalid-email"
            )
        """
        field_errors = {field: [code]}  # Use the enum directly

        return cls(
            detail=message,
            code=ErrorCode.GENERAL_VALIDATION_ERROR,
            status_code=status.HTTP_400_BAD_REQUEST,
            message=_("Validation failed"),
            field_errors=field_errors,
            title=_("Validation Error"),
            instance=instance,
            extra_data={"field_value": value} if value is not None else None,
        )

    def has_field_errors(self) -> bool:
        """Check if this exception has field-specific errors"""
        return bool(self.field_errors)
