from dataclasses import dataclass
from enum import Enum
from typing import Dict, List, Any, Optional, Union
from django.utils.translation import gettext_lazy as _
from rest_framework.response import Response

from .response_information_codes.error_code import ErrorCode
from .response_information_codes.field_error_code import FieldErrorCode
from .response_information_codes.general_error_code import GeneralErrorCode


class StructuredErrorType(Enum):
    """Types of structured errors for categorization"""

    VALIDATION_ERROR = "validation_error"
    CLIENT_ERROR = "client_error"
    SERVER_ERROR = "server_error"
    AUTHENTICATION_ERROR = "authentication_error"
    AUTHORIZATION_ERROR = "authorization_error"
    BUSINESS_LOGIC_ERROR = "business_logic_error"
    NOT_FOUND_ERROR = "not_found_error"


# Every error response carries a response_code. When neither the response nor its
# general error supplies one, it is derived from the error type via this map.
DEFAULT_ERROR_CODE_BY_TYPE = {
    StructuredErrorType.VALIDATION_ERROR: ErrorCode.GENERAL_VALIDATION_ERROR,
    StructuredErrorType.AUTHENTICATION_ERROR: ErrorCode.AUTHENTICATION_FAILED,
    StructuredErrorType.AUTHORIZATION_ERROR: ErrorCode.PERMISSION_DENIED,
    StructuredErrorType.NOT_FOUND_ERROR: ErrorCode.NOT_FOUND_ERROR,
    StructuredErrorType.CLIENT_ERROR: ErrorCode.BAD_REQUEST,
    StructuredErrorType.BUSINESS_LOGIC_ERROR: ErrorCode.AN_ERROR_OCCURED,
    StructuredErrorType.SERVER_ERROR: ErrorCode.INTERNAL_SERVER_ERROR,
}


@dataclass
class FieldError:
    """Represents a field-specific validation error"""

    field: str
    code: Union[
        FieldErrorCode, str
    ]  # Support both enum and string for backward compatibility
    message: str

    def get_code_value(self) -> str:
        """Get string value regardless of input type"""
        if isinstance(self.code, FieldErrorCode):
            return self.code.value
        return str(self.code)


@dataclass
class GeneralError:
    """Represents a general error with title and description"""

    title: str
    detail: str
    code: Optional[Union[GeneralErrorCode, str]] = None  # Support both enum and string

    def get_code_value(self) -> Optional[str]:
        """Get string value regardless of input type"""
        if self.code is None:
            return None
        if isinstance(self.code, GeneralErrorCode):
            return self.code.value
        return str(self.code)


class StructuredErrorResponse:
    """
    Creates structured error responses following RFC 7807 standards
    Supports both field-based errors and multiple general errors
    """

    def __init__(
        self,
        error_type: StructuredErrorType,
        status_code: int,
        instance: str = None,
        general_errors: List[GeneralError] = None,  # Changed: now supports multiple
        field_errors: List[FieldError] = None,
        error_code: Any = None,  # Main error code for the response
        extra_data: Dict[str, Any] = None,
    ):
        self.error_type = error_type
        self.status_code = status_code
        self.instance = instance
        self.general_errors = general_errors or []  # Changed: list instead of single
        self.field_errors = field_errors or []
        self.error_code = error_code
        self.extra_data = extra_data or {}

    def resolve_response_code(self) -> str:
        """
        Resolve the response_code, which is always present on an error response.

        The response-level code wins. A lone general error supplies the code when the
        response carries none, and the error type provides the final fallback so no
        construction path can produce a body without a response_code.
        """
        if self.error_code:
            return self.error_code.value

        if len(self.general_errors) == 1 and self.general_errors[0].code:
            return self.general_errors[0].get_code_value()

        return DEFAULT_ERROR_CODE_BY_TYPE[self.error_type].value

    def to_dict(self) -> Dict[str, Any]:
        """Convert to RFC 7807 compliant dictionary"""
        response_data = {
            "success": False,
            "type": self.error_type.value,
            "status": self.status_code,
            "response_code": self.resolve_response_code(),
        }

        # Add instance if provided
        if self.instance:
            response_data["instance"] = self.instance

        # Handle general errors - now supporting multiple
        if self.general_errors:
            if len(self.general_errors) == 1:
                # Single general error: use title/detail at root level
                general_error = self.general_errors[0]
                response_data["title"] = general_error.title
                response_data["detail"] = general_error.detail
            else:
                # Multiple general errors: use array format. Entries share the
                # {code, message} shape of field entries and add their own title.
                response_data["title"] = _("Multiple Issues Found")
                response_data["detail"] = _(
                    "Multiple issues were identified with your request."
                )
                response_data["errors"] = response_data.get("errors", {})
                response_data["errors"]["general"] = [
                    {
                        "code": error.get_code_value()
                        or GeneralErrorCode.UNKNOWN_ERROR.value,
                        "message": error.detail,
                        "title": error.title,
                    }
                    for error in self.general_errors
                ]

        # Handle field errors
        if self.field_errors:
            # If no general errors exist, set default validation messages
            if not self.general_errors:
                if len(self.field_errors) == 1:
                    response_data["title"] = _("Validation Error")
                    response_data["detail"] = _("The request data is invalid.")
                else:
                    response_data["title"] = _("Validation Errors")
                    response_data["detail"] = _(
                        "Multiple fields have validation errors."
                    )

            # Add field-specific errors
            response_data["errors"] = response_data.get("errors", {})
            for field_error in self.field_errors:
                if field_error.field not in response_data["errors"]:
                    response_data["errors"][field_error.field] = []
                response_data["errors"][field_error.field].append(
                    {
                        "code": field_error.get_code_value(),
                        "message": field_error.message,
                    }
                )

        # Add extra data
        response_data.update(self.extra_data)

        return response_data

    def to_response(self) -> Response:
        """Convert to DRF Response with proper content type"""
        return Response(
            data=self.to_dict(),
            status=self.status_code,
            content_type="application/problem+json",
        )

    @classmethod
    def validation_error(
        cls,
        field_errors: List[FieldError] = None,
        general_errors: List[GeneralError] = None,  # Changed: now supports multiple
        instance: str = None,
        extra_data: Dict[str, Any] = None,
    ):
        """Create a validation error response"""
        return cls(
            error_type=StructuredErrorType.VALIDATION_ERROR,
            status_code=400,
            instance=instance,
            general_errors=general_errors,
            field_errors=field_errors,
            extra_data=extra_data,
        )


def create_field_error_from_drf_errors(
    field_name: str, errors: List
) -> List[FieldError]:
    """Convert DRF field errors to FieldError objects with structured codes"""
    field_errors = []
    for error in errors:
        # Get the error code, either from the error object or default to 'invalid'
        error_code_str = (
            getattr(error, "code", "invalid") if hasattr(error, "code") else "invalid"
        )

        # Convert string code to FieldErrorCode enum
        structured_code = FieldErrorCode.from_string(error_code_str)

        field_errors.append(
            FieldError(field=field_name, code=structured_code, message=str(error))
        )
    return field_errors


def convert_drf_validation_errors_to_structured(drf_errors: Dict) -> Dict[str, List]:
    """Convert DRF validation errors to structured format with enum codes"""
    structured_errors = {}

    for field_name, errors in drf_errors.items():
        if isinstance(errors, list):
            structured_errors[field_name] = []
            for error in errors:
                error_code_str = (
                    getattr(error, "code", "invalid")
                    if hasattr(error, "code")
                    else "invalid"
                )
                structured_code = FieldErrorCode.from_string(error_code_str)

                structured_errors[field_name].append(
                    {"code": structured_code.value, "message": str(error)}
                )
        else:
            error_code_str = (
                getattr(errors, "code", "invalid")
                if hasattr(errors, "code")
                else "invalid"
            )
            structured_code = FieldErrorCode.from_string(error_code_str)

            structured_errors[field_name] = [
                {"code": structured_code.value, "message": str(errors)}
            ]

    return structured_errors
