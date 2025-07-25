from enum import Enum
from typing import Dict, Union, List, Any, Optional
from dataclasses import dataclass
from django.utils.translation import gettext_lazy as _
from rest_framework import status
from rest_framework.response import Response

from common.response.response_information_codes.error_code import ErrorCode


class StructuredErrorType(Enum):
    """Error types following RFC 7807 standards"""
    VALIDATION_ERROR = "validation_error"
    CLIENT_ERROR = "client_error"
    SERVER_ERROR = "server_error"
    AUTHENTICATION_ERROR = "authentication_error"
    AUTHORIZATION_ERROR = "authorization_error"
    BUSINESS_LOGIC_ERROR = "business_logic_error"


@dataclass
class FieldError:
    """Represents a field-specific validation error"""
    field: str
    code: str
    message: str
    value: Any = None


@dataclass
class GeneralError:
    """Represents a general error with title and details"""
    title: str
    detail: str
    code: str = None


class StructuredErrorResponse:
    """
    Creates structured error responses following RFC 7807 standards
    Supports both field-based errors and general errors
    """
    
    def __init__(
        self,
        error_type: StructuredErrorType,
        status_code: int,
        instance: str = None,
        general_error: GeneralError = None,
        field_errors: List[FieldError] = None,
        error_code: ErrorCode = None,
        extra_data: Dict[str, Any] = None
    ):
        self.error_type = error_type
        self.status_code = status_code
        self.instance = instance
        self.general_error = general_error
        self.field_errors = field_errors or []
        self.error_code = error_code
        self.extra_data = extra_data or {}
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to RFC 7807 compliant dictionary"""
        response_data = {
            "type": self.error_type.value,
            "status": self.status_code,
        }
        
        # Add instance if provided
        if self.instance:
            response_data["instance"] = self.instance
        
        # Add error code if provided
        if self.error_code:
            response_data["code"] = self.error_code.value
        
        # Handle general errors
        if self.general_error:
            response_data["title"] = self.general_error.title
            response_data["detail"] = self.general_error.detail
            if self.general_error.code:
                response_data["code"] = self.general_error.code
        
        # Handle field errors
        if self.field_errors:
            if len(self.field_errors) == 1:
                # Single field error - provide a general title and detail
                field_error = self.field_errors[0]
                response_data["title"] = _("Validation Error")
                response_data["detail"] = _("The request data is invalid.")
            else:
                # Multiple field errors
                response_data["title"] = _("Validation Errors")
                response_data["detail"] = _("Multiple fields have validation errors.")
            
            # Add field-specific errors
            response_data["errors"] = {}
            for field_error in self.field_errors:
                if field_error.field not in response_data["errors"]:
                    response_data["errors"][field_error.field] = []
                response_data["errors"][field_error.field].append({
                    "code": field_error.code,
                    "message": field_error.message,
                    "value": field_error.value
                })
        
        # Add any extra data
        response_data.update(self.extra_data)
        
        return response_data
    
    def to_response(self) -> Response:
        """Convert to Django REST Framework Response"""
        return Response(
            data=self.to_dict(),
            status=self.status_code,
            content_type="application/problem+json"
        )
    
    @classmethod
    def validation_error(
        cls,
        field_errors: List[FieldError] = None,
        general_error: GeneralError = None,
        instance: str = None,
        extra_data: Dict[str, Any] = None
    ):
        """Create a validation error response"""
        return cls(
            error_type=StructuredErrorType.VALIDATION_ERROR,
            status_code=status.HTTP_400_BAD_REQUEST,
            field_errors=field_errors,
            general_error=general_error,
            instance=instance,
            extra_data=extra_data
        )
    
    @classmethod
    def authentication_error(
        cls,
        title: str = None,
        detail: str = None,
        code: str = None,
        instance: str = None,
        extra_data: Dict[str, Any] = None
    ):
        """Create an authentication error response"""
        general_error = GeneralError(
            title=title or _("Authentication Failed"),
            detail=detail or _("Authentication credentials were missing or invalid."),
            code=code
        )
        return cls(
            error_type=StructuredErrorType.AUTHENTICATION_ERROR,
            status_code=status.HTTP_401_UNAUTHORIZED,
            general_error=general_error,
            instance=instance,
            extra_data=extra_data
        )
    
    @classmethod
    def authorization_error(
        cls,
        title: str = None,
        detail: str = None,
        code: str = None,
        instance: str = None,
        extra_data: Dict[str, Any] = None
    ):
        """Create an authorization error response"""
        general_error = GeneralError(
            title=title or _("Access Denied"),
            detail=detail or _("You do not have permission to perform this action."),
            code=code
        )
        return cls(
            error_type=StructuredErrorType.AUTHORIZATION_ERROR,
            status_code=status.HTTP_403_FORBIDDEN,
            general_error=general_error,
            instance=instance,
            extra_data=extra_data
        )
    
    @classmethod
    def not_found_error(
        cls,
        title: str = None,
        detail: str = None,
        code: str = None,
        instance: str = None,
        extra_data: Dict[str, Any] = None
    ):
        """Create a not found error response"""
        general_error = GeneralError(
            title=title or _("Not Found"),
            detail=detail or _("The requested resource was not found."),
            code=code
        )
        return cls(
            error_type=StructuredErrorType.CLIENT_ERROR,
            status_code=status.HTTP_404_NOT_FOUND,
            general_error=general_error,
            instance=instance,
            extra_data=extra_data
        )
    
    @classmethod
    def server_error(
        cls,
        title: str = None,
        detail: str = None,
        code: str = None,
        instance: str = None,
        extra_data: Dict[str, Any] = None
    ):
        """Create a server error response"""
        general_error = GeneralError(
            title=title or _("Server Error"),
            detail=detail or _("An internal server error occurred. Please try again later."),
            code=code
        )
        return cls(
            error_type=StructuredErrorType.SERVER_ERROR,
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            general_error=general_error,
            instance=instance,
            extra_data=extra_data
        )
    
    @classmethod
    def business_logic_error(
        cls,
        title: str,
        detail: str,
        code: str = None,
        status_code: int = status.HTTP_400_BAD_REQUEST,
        instance: str = None,
        extra_data: Dict[str, Any] = None
    ):
        """Create a business logic error response"""
        general_error = GeneralError(
            title=title,
            detail=detail,
            code=code
        )
        return cls(
            error_type=StructuredErrorType.BUSINESS_LOGIC_ERROR,
            status_code=status_code,
            general_error=general_error,
            instance=instance,
            extra_data=extra_data
        )


def create_field_error_from_drf_errors(field_name: str, field_errors: List[str]) -> List[FieldError]:
    """Convert DRF field errors to FieldError objects"""
    errors = []
    for error in field_errors:
        # Extract error code if available
        error_code = getattr(error, 'code', 'invalid') if hasattr(error, 'code') else 'invalid'
        error_message = str(error)
        
        errors.append(FieldError(
            field=field_name,
            code=error_code,
            message=error_message
        ))
    return errors


def convert_drf_validation_errors_to_structured(validation_errors: Dict[str, List]) -> List[FieldError]:
    """Convert DRF validation errors to structured field errors"""
    field_errors = []
    
    for field_name, errors in validation_errors.items():
        if field_name == 'non_field_errors':
            # Handle non-field errors as general errors
            continue
        
        field_errors.extend(create_field_error_from_drf_errors(field_name, errors))
    
    return field_errors