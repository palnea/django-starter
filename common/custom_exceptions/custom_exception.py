from django.utils.translation import gettext_lazy as _
from rest_framework import status
from rest_framework.exceptions import APIException, _get_error_details
from typing import Dict, List, Any, Optional

from common.response.response_information_codes.error_code import ErrorCode


class CustomException(APIException):
    """
    Base class for REST framework exceptions.
    Subclasses should provide `.status_code` and `.default_detail` properties.
    Now supports structured error responses.
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
        field_errors: Optional[Dict[str, List[str]]] = None,
        title: Optional[str] = None,
        instance: Optional[str] = None,
        extra_data: Optional[Dict[str, Any]] = None
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
        self.title = title
        self.instance = instance
        self.extra_data = extra_data or {}
        
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
        instance: str = None
    ):
        detail = str(exc)
        return cls(detail, code, status_code, message, title=title, instance=instance)
    
    @classmethod
    def validation_error(
        cls,
        field_errors: Dict[str, List[str]] = None,
        general_message: str = None,
        title: str = None,
        instance: str = None,
        status_code: int = status.HTTP_400_BAD_REQUEST
    ):
        """Create a validation error with field-specific errors"""
        return cls(
            detail=general_message or _("Validation failed"),
            code=ErrorCode.GENERAL_VALIDATION_ERROR,
            status_code=status_code,
            message=_("Request parameters are not valid!"),
            field_errors=field_errors,
            title=title or _("Validation Error"),
            instance=instance
        )
    
    @classmethod
    def business_logic_error(
        cls,
        title: str,
        detail: str,
        code: ErrorCode = None,
        status_code: int = status.HTTP_400_BAD_REQUEST,
        instance: str = None,
        extra_data: Dict[str, Any] = None
    ):
        """Create a business logic error"""
        return cls(
            detail=detail,
            code=code or ErrorCode.AN_ERROR_OCCURED,
            status_code=status_code,
            message=title,
            title=title,
            instance=instance,
            extra_data=extra_data
        )
    
    @classmethod
    def authentication_error(
        cls,
        title: str = None,
        detail: str = None,
        instance: str = None
    ):
        """Create an authentication error"""
        return cls(
            detail=detail or _("Authentication credentials were missing or invalid."),
            code=ErrorCode.AUTHENTICATION_FAILED,
            status_code=status.HTTP_401_UNAUTHORIZED,
            message=title or _("Authentication Failed"),
            title=title or _("Authentication Failed"),
            instance=instance
        )
    
    @classmethod
    def authorization_error(
        cls,
        title: str = None,
        detail: str = None,
        instance: str = None
    ):
        """Create an authorization error"""
        return cls(
            detail=detail or _("You do not have permission to perform this action."),
            code=ErrorCode.PERMISSION_DENIED,
            status_code=status.HTTP_403_FORBIDDEN,
            message=title or _("Access Denied"),
            title=title or _("Access Denied"),
            instance=instance
        )
    
    @classmethod
    def not_found_error(
        cls,
        title: str = None,
        detail: str = None,
        instance: str = None
    ):
        """Create a not found error"""
        return cls(
            detail=detail or _("The requested resource was not found."),
            code=ErrorCode.NOT_FOUND_ERROR,
            status_code=status.HTTP_404_NOT_FOUND,
            message=title or _("Not Found"),
            title=title or _("Not Found"),
            instance=instance
        )
    
    def has_field_errors(self) -> bool:
        """Check if this exception has field-specific errors"""
        return bool(self.field_errors)
    
    def is_structured(self) -> bool:
        """Check if this exception should use structured error response"""
        return bool(self.field_errors or self.title or self.extra_data)
