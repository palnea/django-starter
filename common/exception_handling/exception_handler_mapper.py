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
from django.utils.translation import gettext_lazy as _
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


class ExceptionHandlingParameters(object):
    def __init__(
        self,
        error_msg: str,
        response_status: int,
        response_information_code: ErrorCode,
        response_message: str = _("An error occured!"),
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
            _("Already exist!"),
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
        _("An error occured!"),
    ),
    IntegrityError: get_integrity_error_parameters,
    ObjectDoesNotExist: lambda x: ExceptionHandlingParameters(
        "Object doesn't exist!",
        status.HTTP_404_NOT_FOUND,
        ErrorCode.NOT_FOUND_ERROR,
        _("Content not found!"),
    ),
    PermissionDenied: lambda x: ExceptionHandlingParameters(
        "This operations is not permitted!",
        status.HTTP_403_FORBIDDEN,
        ErrorCode.PERMISSION_DENIED,
        _("You don't have permission for this action!"),
    ),
    ViewDoesNotExist: lambda x: ExceptionHandlingParameters(
        "View doesn't exist!",
        status.HTTP_500_INTERNAL_SERVER_ERROR,
        ErrorCode.VIEW_DOESNT_EXIST,
        _("An error occured!"),
    ),
    MiddlewareNotUsed: lambda x: ExceptionHandlingParameters(
        "Middleware not used!",
        status.HTTP_500_INTERNAL_SERVER_ERROR,
        ErrorCode.MIDDLEWARE_NOT_USED,
        _("An error occured!"),
    ),
    ImproperlyConfigured: lambda x: ExceptionHandlingParameters(
        "Improperly configured!",
        status.HTTP_500_INTERNAL_SERVER_ERROR,
        ErrorCode.IMPROPERLY_CONFIGURED,
        _("An error occured!"),
    ),
    FieldError: lambda x: ExceptionHandlingParameters(
        "Field Error!",
        status.HTTP_500_INTERNAL_SERVER_ERROR,
        ErrorCode.FIELD_ERROR,
        _("An error occured!"),
    ),
    CoreValidationError: lambda x: ExceptionHandlingParameters(
        "Data is not valid!",
        status.HTTP_400_BAD_REQUEST,
        ErrorCode.INVALID_INPUT,
        _("Request parameters are not valid!"),
    ),
    BadRequest: lambda x: ExceptionHandlingParameters(
        "Bad request!",
        status.HTTP_400_BAD_REQUEST,
        ErrorCode.BAD_REQUEST,
        _("Bad request!"),
    ),
    RequestAborted: lambda x: ExceptionHandlingParameters(
        "Request aborted!", 499, ErrorCode.REQUEST_ABORTED, _("Request aborted!")
    ),
    SynchronousOnlyOperation: lambda x: ExceptionHandlingParameters(
        "SynchronousOnlyOperation!",
        status.HTTP_500_INTERNAL_SERVER_ERROR,
        ErrorCode.INTERNAL_SERVER_ERROR,
        _("An error occured!"),
    ),
    UnreadablePostError: lambda x: ExceptionHandlingParameters(
        "Upload is aborted!",
        status.HTTP_400_BAD_REQUEST,
        ErrorCode.FILE_UNREADABLE,
        _("Upload is aborted!"),
    ),
    SessionInterrupted: lambda x: ExceptionHandlingParameters(
        "Session interrupted!",
        status.HTTP_400_BAD_REQUEST,
        ErrorCode.SESSION_INTERRUPTED,
        _("Session interrupted!"),
    ),
    TransactionManagementError: lambda x: ExceptionHandlingParameters(
        "Something bad occurred on transaction management!",
        status.HTTP_500_INTERNAL_SERVER_ERROR,
        ErrorCode.TRANSACTION_MANAGEMENT_ERROR,
        _("An error occured!"),
    ),
    Http404: lambda x: ExceptionHandlingParameters(
        "No content!",
        status.HTTP_404_NOT_FOUND,
        ErrorCode.NOT_FOUND_ERROR,
        _("Content not found!"),
    ),
}

API_EXCEPTION_HANDLER_MAPPER = {
    APIException: APIExceptionHandlingParameters(
        ErrorCode.UNKNOWN_ERROR, _("An error occured!")
    ),
    ValidationError: APIExceptionHandlingParameters(
        ErrorCode.INVALID_INPUT, _("Request parameters are not valid!")
    ),
    ParseError: APIExceptionHandlingParameters(
        ErrorCode.PARSE_ERROR, _("An error occured!")
    ),
    AuthenticationFailed: APIExceptionHandlingParameters(
        ErrorCode.AUTHENTICATION_FAILED, _("Authentication failed!")
    ),
    NotAuthenticated: APIExceptionHandlingParameters(
        ErrorCode.NOT_AUTHENTICATED, _("Not authenticated!")
    ),
    APIPermissionDenied: APIExceptionHandlingParameters(
        ErrorCode.PERMISSION_DENIED, _("You don't have permission for this action!")
    ),
    NotFound: APIExceptionHandlingParameters(
        ErrorCode.NOT_FOUND_ERROR, _("Content not found!")
    ),
    MethodNotAllowed: APIExceptionHandlingParameters(
        ErrorCode.METHOD_NOT_ALLOWED, _("You don't have permission for this action!")
    ),
    NotAcceptable: APIExceptionHandlingParameters(
        ErrorCode.NOT_ACCEPTABLE, _("You don't have permission for this action!")
    ),
    UnsupportedMediaType: APIExceptionHandlingParameters(
        ErrorCode.UNSUPPORTED_MEDIA_TYPE, _("Unsupported media type!")
    ),
    Throttled: APIExceptionHandlingParameters(
        ErrorCode.THROTTLED, _("An error occured!")
    ),
    InvalidToken: APIExceptionHandlingParameters(
        ErrorCode.INVALID_TOKEN, _("Not authenticated!")
    ),
}
