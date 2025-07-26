from django.contrib.sessions.exceptions import SessionInterrupted
from django.core.exceptions import (
    ObjectDoesNotExist,
    PermissionDenied,
    ViewDoesNotExist,
    MiddlewareNotUsed,
    ImproperlyConfigured,
    FieldError,
    ValidationError as CoreValidationError,
    BadRequest,
    RequestAborted,
    SynchronousOnlyOperation,
)
from django.db import IntegrityError
from django.db.transaction import TransactionManagementError
from django.http import UnreadablePostError, Http404
from django.utils.translation import gettext_lazy as _, gettext
from rest_framework import status
from rest_framework.exceptions import (
    APIException,
    ValidationError,
    ParseError,
    AuthenticationFailed,
    PermissionDenied as APIPermissionDenied,
    NotAuthenticated,
    NotFound,
    MethodNotAllowed,
    NotAcceptable,
    UnsupportedMediaType,
    Throttled,
)
from rest_framework_simplejwt.exceptions import InvalidToken

from common.response.response_information_codes.error_code import ErrorCode


def translate_message(message_key):
    """
    Translate message at runtime based on current language context.
    This allows us to mark strings for translation while maintaining
    dynamic language detection in exception handlers.
    """
    return gettext(message_key)


# Mark strings for translation - these will be picked up by makemessages
# but we'll translate them dynamically in the exception handlers
_("Already exist!")
_("Already exists!")
_("Integrity Error!")
_("Unknown error!")
_("An error occured!")
_("Object doesn't exist!")
_("Content not found!")
_("This operations is not permitted!")
_("You don't have permission for this action!")
_("View doesn't exist!")
_("Middleware not used!")
_("Improperly configured!")
_("Field Error!")
_("Data is not valid!")
_("Request parameters are not valid!")
_("Bad request!")
_("Request aborted!")
_("SynchronousOnlyOperation!")
_("Upload is aborted!")
_("Session interrupted!")
_("Something bad occurred on transaction management!")
_("No content!")
_("Authentication failed!")
_("Not authenticated!")
_("Unsupported media type!")


class ExceptionHandlingParameters(object):
    def __init__(
        self,
        error_msg: str,
        response_status: int,
        response_information_code: ErrorCode,
        response_message: str = "An error occured!",
    ):
        self.error_msg = error_msg
        self.response_status = response_status
        self.response_information_code = response_information_code
        self.response_message = response_message


class APIExceptionHandlingParameters(object):
    def __init__(
        self, response_information_code: ErrorCode, response_message: str
    ) -> None:
        self.response_information_code = response_information_code
        self.response_message = response_message


def get_integrity_error_parameters(error: Exception):
    if "duplicate key" in str(error):
        return ExceptionHandlingParameters(
            "Already exists!",
            status.HTTP_400_BAD_REQUEST,
            ErrorCode.DUPLICATE_KEY_ERROR,
            "Already exist!",
        )
    return ExceptionHandlingParameters(
        "Integrity Error!",
        status.HTTP_500_INTERNAL_SERVER_ERROR,
        ErrorCode.INTEGRITY_ERROR,
    )


EXCEPTION_HANDLER_MAPPER = {
    Exception: lambda x: ExceptionHandlingParameters(
        "Unknown error!",
        status.HTTP_500_INTERNAL_SERVER_ERROR,
        ErrorCode.UNKNOWN_ERROR,
        "An error occured!",
    ),
    IntegrityError: get_integrity_error_parameters,
    ObjectDoesNotExist: lambda x: ExceptionHandlingParameters(
        "Object doesn't exist!",
        status.HTTP_404_NOT_FOUND,
        ErrorCode.NOT_FOUND_ERROR,
        "Content not found!",
    ),
    PermissionDenied: lambda x: ExceptionHandlingParameters(
        "This operations is not permitted!",
        status.HTTP_403_FORBIDDEN,
        ErrorCode.PERMISSION_DENIED,
        "You don't have permission for this action!",
    ),
    ViewDoesNotExist: lambda x: ExceptionHandlingParameters(
        "View doesn't exist!",
        status.HTTP_500_INTERNAL_SERVER_ERROR,
        ErrorCode.VIEW_DOESNT_EXIST,
        "An error occured!",
    ),
    MiddlewareNotUsed: lambda x: ExceptionHandlingParameters(
        "Middleware not used!",
        status.HTTP_500_INTERNAL_SERVER_ERROR,
        ErrorCode.MIDDLEWARE_NOT_USED,
        "An error occured!",
    ),
    ImproperlyConfigured: lambda x: ExceptionHandlingParameters(
        "Improperly configured!",
        status.HTTP_500_INTERNAL_SERVER_ERROR,
        ErrorCode.IMPROPERLY_CONFIGURED,
        "An error occured!",
    ),
    FieldError: lambda x: ExceptionHandlingParameters(
        "Field Error!",
        status.HTTP_500_INTERNAL_SERVER_ERROR,
        ErrorCode.FIELD_ERROR,
        "An error occured!",
    ),
    CoreValidationError: lambda x: ExceptionHandlingParameters(
        "Data is not valid!",
        status.HTTP_400_BAD_REQUEST,
        ErrorCode.INVALID_INPUT,
        "Request parameters are not valid!",
    ),
    BadRequest: lambda x: ExceptionHandlingParameters(
        "Bad request!",
        status.HTTP_400_BAD_REQUEST,
        ErrorCode.BAD_REQUEST,
        "Bad request!",
    ),
    RequestAborted: lambda x: ExceptionHandlingParameters(
        "Request aborted!",
        499,
        ErrorCode.REQUEST_ABORTED,
        "Request aborted!",
    ),
    SynchronousOnlyOperation: lambda x: ExceptionHandlingParameters(
        "SynchronousOnlyOperation!",
        status.HTTP_500_INTERNAL_SERVER_ERROR,
        ErrorCode.INTERNAL_SERVER_ERROR,
        "An error occured!",
    ),
    UnreadablePostError: lambda x: ExceptionHandlingParameters(
        "Upload is aborted!",
        status.HTTP_400_BAD_REQUEST,
        ErrorCode.FILE_UNREADABLE,
        "Upload is aborted!",
    ),
    SessionInterrupted: lambda x: ExceptionHandlingParameters(
        "Session interrupted!",
        status.HTTP_400_BAD_REQUEST,
        ErrorCode.SESSION_INTERRUPTED,
        "Session interrupted!",
    ),
    TransactionManagementError: lambda x: ExceptionHandlingParameters(
        "Something bad occurred on transaction management!",
        status.HTTP_500_INTERNAL_SERVER_ERROR,
        ErrorCode.TRANSACTION_MANAGEMENT_ERROR,
        "An error occured!",
    ),
    Http404: lambda x: ExceptionHandlingParameters(
        "No content!",
        status.HTTP_404_NOT_FOUND,
        ErrorCode.NOT_FOUND_ERROR,
        "Content not found!",
    ),
}

API_EXCEPTION_HANDLER_MAPPER = {
    APIException: APIExceptionHandlingParameters(
        ErrorCode.UNKNOWN_ERROR, "An error occured!"
    ),
    ValidationError: APIExceptionHandlingParameters(
        ErrorCode.INVALID_INPUT, "Request parameters are not valid!"
    ),
    ParseError: APIExceptionHandlingParameters(
        ErrorCode.PARSE_ERROR, "An error occured!"
    ),
    AuthenticationFailed: APIExceptionHandlingParameters(
        ErrorCode.AUTHENTICATION_FAILED, "Authentication failed!"
    ),
    NotAuthenticated: APIExceptionHandlingParameters(
        ErrorCode.NOT_AUTHENTICATED, "Not authenticated!"
    ),
    APIPermissionDenied: APIExceptionHandlingParameters(
        ErrorCode.PERMISSION_DENIED, "You don't have permission for this action!"
    ),
    NotFound: APIExceptionHandlingParameters(
        ErrorCode.NOT_FOUND_ERROR, "Content not found!"
    ),
    MethodNotAllowed: APIExceptionHandlingParameters(
        ErrorCode.METHOD_NOT_ALLOWED, "You don't have permission for this action!"
    ),
    NotAcceptable: APIExceptionHandlingParameters(
        ErrorCode.NOT_ACCEPTABLE, "You don't have permission for this action!"
    ),
    UnsupportedMediaType: APIExceptionHandlingParameters(
        ErrorCode.UNSUPPORTED_MEDIA_TYPE, "Unsupported media type!"
    ),
    Throttled: APIExceptionHandlingParameters(ErrorCode.THROTTLED, "An error occured!"),
    InvalidToken: APIExceptionHandlingParameters(
        ErrorCode.INVALID_TOKEN, "Not authenticated!"
    ),
}
