import contextvars
import uuid
from typing import TYPE_CHECKING
from typing import Union

import structlog
from django.utils.functional import cached_property
from pytz.tzinfo import DstTzInfo, StaticTzInfo
from rest_framework.request import Request
from rest_framework.response import Response

from common.types import LocaleCode
from utils.date import timezone_with_fallback
from django.core.cache import cache

if TYPE_CHECKING:
    from user.models import User

_global_context_var: contextvars.ContextVar["GlobalContext"] = contextvars.ContextVar(
    "global_context"
)
_request_id_var: contextvars.ContextVar[str] = contextvars.ContextVar("request_id")


def get_request_id() -> str:
    """Return the current request's correlation ID, or empty string if not in a request."""
    return _request_id_var.get("")


class GlobalContext:
    def __init__(self, request: Request):
        self.request = request

    @cached_property
    def user_id(self) -> int:
        return (
            self.request.auth.payload.get("user_id")
            if hasattr(self.request, "auth")
            and self.request.auth
            and self.request.auth.payload
            else None
        )

    @cached_property
    def user_groups(self) -> [str]:
        return (
            self.request.auth.payload.get("groups", [])
            if self.request.auth and self.request.auth.payload
            else []
        )

    @cached_property
    def user_specific_permissions(self) -> [str]:
        return (
            self.request.auth.payload.get("permissions", [])
            if self.request.auth and self.request.auth.payload
            else []
        )

    @cached_property
    def user_all_permissions(self) -> [str]:
        cache_key = f"user_{self.user_id}_perms"
        permissions = cache.get(cache_key)
        if permissions is None:
            user = self.user
            permissions = (
                set(user.get_all_permissions())
                if user and user.is_authenticated
                else set()
            )
            cache.set(cache_key, permissions, timeout=3600)
        return permissions

    @cached_property
    def user_timezone(self) -> Union[StaticTzInfo, DstTzInfo]:
        timezone_header = self.request.META.get("HTTP_USER_TIMEZONE", "UTC")
        return timezone_with_fallback(timezone_header)

    @cached_property
    def user(self) -> Union["User", None]:
        user = self.request.user
        if str(user.__class__.__name__) == "User":
            return user
        return None

    @cached_property
    def account(self) -> Union["User", None]:
        return self.request.user

    @cached_property
    def language_code(self) -> str:
        """Returns selected language code If language or locale fields are provided in query_params set to that value
        Else if user is logged in return user locale_code.
        """
        language_code = (
            self.request.META.get("HTTP_ACCEPT_LANGUAGE")
            or self.request.GET.get("language", None)
            or self.request.GET.get("locale_code", None)
        )
        if language_code in [choice.value for choice in LocaleCode]:
            return language_code

        token_language_code = (
            self.request.auth.payload.get("locale_code", None)
            if self.request.auth and self.request.auth.payload
            else None
        )
        return token_language_code or LocaleCode.EN.value


class NullGlobalContext:
    """Safety-net fallback when no middleware is active (shell, Celery, tests). Returns safe defaults so infrastructure
    code (logging, permissions) won't crash.
    """

    user_id = None
    user = None
    account = None
    user_groups = []
    user_specific_permissions = []
    user_all_permissions = set()
    user_timezone = "UTC"
    language_code = "en"


class GlobalContextMiddleware:
    """Provides storage for the "current" request context using contextvars, which is safe for both WSGI (threaded)
    and ASGI (async) servers. Also generates/propagates a correlation ID (X-Request-ID) for every request.
    """

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request: Request):
        # Generate or propagate correlation ID
        request_id = request.META.get("HTTP_X_REQUEST_ID") or str(uuid.uuid4())
        _request_id_var.set(request_id)

        # Bind request_id to structlog contextvars so it appears in all log entries
        structlog.contextvars.clear_contextvars()
        structlog.contextvars.bind_contextvars(request_id=request_id)

        self.process_request(request)
        response = self.get_response(request)
        self.process_response(request, response)

        # Attach correlation ID to response
        response["X-Request-ID"] = request_id
        return response

    def process_request(self, request: Request):
        """Store the current request."""
        global_context = GlobalContext(request)
        self.__class__.set_global_context(global_context)

    def process_response(self, request: Request, response: Response):
        """Clean up context to avoid leaking between requests."""
        self.__class__.del_global_context()
        structlog.contextvars.clear_contextvars()
        return response

    @classmethod
    def get_global_context(cls, default=None) -> "GlobalContext":
        """Retrieve the GlobalContext for the current execution context (thread or async task)."""
        return _global_context_var.get(default or NullGlobalContext())

    @classmethod
    def set_global_context(cls, context: GlobalContext) -> None:
        """Save the given context into the current execution context."""
        _global_context_var.set(context)

    @classmethod
    def del_global_context(cls) -> None:
        """Remove the context for the current execution context."""
        _global_context_var.set(NullGlobalContext())
