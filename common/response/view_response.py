import traceback
from enum import Enum
from typing import Dict, Union, List

from django.utils.functional import cached_property
from django.utils.translation import gettext_lazy as _
from rest_framework import status
from rest_framework.response import Response

import settings
from common.middlewares.global_context_middleware import GlobalContextMiddleware
from common.response.response_information_codes.error_code import ErrorCode
from common.response.response_information_codes.message_code import MessageCode
from user.types import UserRole


class ViewResponse:
    def __init__(
        self,
        response_body: Union[None, Dict, List, str],
        response_status: int,
        is_successful: bool,
        response_information_code: Enum,
        exception: Union[None, Exception] = None,
        response_message: str = None,
    ):
        self._response_body = response_body
        self._response_status_code = response_status
        self._is_successful = is_successful
        self._response_information_code = response_information_code
        self._exception = exception
        self._response_message = response_message

    @cached_property
    def rest_response(self) -> Response:
        data_content = {
            "success": self._is_successful,
            "status_code": self._response_status_code,
            "response_code": self._response_information_code.value,
            "response_body": self._response_body,
            "message": self._response_message,
        }
        return Response(data=data_content, status=self._response_status_code)

    @property
    def error_message(self) -> Union[None, str]:
        return getattr(self, "error_msg", None)

    @property
    def exception(self) -> Union[None, Exception]:
        return self._exception

    @cached_property
    def exception_stack_trace(self) -> str:
        return str(self.exception) if self.exception else ""

    @cached_property
    def exception_name(self) -> Union[None, str]:
        return self.exception.__class__.__name__ if self.exception else None

    @property
    def response_status_code(self) -> int:
        return self._response_status_code

    @property
    def is_successful(self) -> int:
        return self._is_successful


class ViewSuccessResponse(ViewResponse):
    def __init__(
        self,
        response_body: Union[str, Dict, None] = None,
        response_status=status.HTTP_200_OK,
        response_information_code: MessageCode = MessageCode.GENERAL_SUCCESS,
        response_message: str = _("Success"),
    ):
        super().__init__(
            response_body,
            response_status,
            True,
            exception=None,
            response_information_code=response_information_code,
            response_message=response_message,
        )


class ViewResponseNoContent(ViewResponse):
    def __init__(self, response_message: str = None):
        super().__init__(
            {},
            status.HTTP_204_NO_CONTENT,
            True,
            exception=None,
            response_information_code=MessageCode.GENERAL_SUCCESS,
            response_message=response_message,
        )


class ViewFailResponse(ViewResponse):
    def __init__(
        self,
        error_msg: str,
        response_status: int,
        exception: Union[None, Exception] = None,
        response_information_code: ErrorCode = ErrorCode.UNKNOWN_ERROR,
        response_message: str = _("An error occured!"),
    ):
        response_body = {"error": error_msg}
        if settings.DEBUG:
            response_body.update({"exception": str(exception)})
        super().__init__(
            response_body,
            response_status,
            False,
            exception=exception,
            response_information_code=response_information_code,
            response_message=response_message,
        )
        self.error_msg = error_msg


class ViewValidationFailureResponse(ViewFailResponse):
    def __init__(
        self,
        error_msg: str,
        exception: Union[None, Exception] = None,
        response_status: int = status.HTTP_400_BAD_REQUEST,
        response_information_code: ErrorCode = ErrorCode.GENERAL_VALIDATION_ERROR,
        response_message: str = _("Request parameters are not valid!"),
    ):
        super().__init__(
            error_msg=error_msg,
            response_status=response_status,
            exception=exception,
            response_information_code=response_information_code,
            response_message=response_message,
        )


class ViewServerErrorResponse(ViewFailResponse):
    def __init__(
        self,
        error_msg: str,
        exception: Union[None, Exception] = None,
        response_status: int = status.HTTP_500_INTERNAL_SERVER_ERROR,
        response_information_code: ErrorCode = ErrorCode.INTERNAL_SERVER_ERROR,
        response_message: str = _("A server error occurred."),
    ):
        super().__init__(
            error_msg=error_msg,
            response_status=response_status,
            exception=exception,
            response_information_code=response_information_code,
            response_message=response_message,
        )


def log_view_response(
    struct_logger,
    view_name: str,
    method_name: str,
    request_body: Union[None, Dict, str],
    request_path,
    request_method,
    view_response: ViewResponse,
    **metrics,
):
    exception_stack_trace = (
        traceback.format_exc() if view_response.exception is not None else None
    )
    log_function = (
        struct_logger.info if view_response.is_successful else struct_logger.error
    )

    request_user_id = GlobalContextMiddleware.get_global_context().user_id
    request_user_role = GlobalContextMiddleware.get_global_context().user_role
    log_function(
        f"{view_name}.{method_name}"
        f'{" has succeeded." if view_response.is_successful else ""}'
        f'{" failed with " + view_response.exception_name if view_response.exception_name else ""}',
        user_id=request_user_id,
        view_name=view_name,
        method=method_name,
        exception_name=view_response.exception_name,
        exception_detail=view_response.exception_stack_trace,
        exception_stack_trace=exception_stack_trace,
        request_body=(
            None
            if view_response.is_successful and request_user_role < UserRole.STAFF
            else request_body
        ),
        request_path=request_path,
        request_method=request_method,
        is_successful=view_response.is_successful,
        **metrics,
    )
