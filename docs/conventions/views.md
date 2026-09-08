# Views

[Back to docs index](../README.md)

Views in this project do three things: delegate to a service or serializer, wrap
the result in a `ViewResponse`, and return `view_response.rest_response`. Logging
happens on its own.

Source: `common/response/view_response.py`, `common/view_mixins.py`.

---

## The pattern

```python
from structlog import get_logger
from rest_framework.viewsets import ModelViewSet

from common.view_mixins import LoggingMixin
from common.response.view_response import ViewResponse
from common.response.response_information_codes.message_code import MessageCode

log = get_logger(__name__)


class WidgetViewSet(LoggingMixin, ModelViewSet):
    queryset = Widget.objects.all()

    def retrieve(self, request, *args, **kwargs):
        response = super().retrieve(request, *args, **kwargs)
        view_response = ViewResponse(
            response_body=response.data,
            response_status=response.status_code,
            is_successful=True,
            response_information_code=MessageCode.RETRIEVE_CONTENT_SUCCESS,
        )
        return view_response.rest_response
```

Three rules, and that is the whole convention:

1. **Mix in `LoggingMixin`**, or `OwnershipMixin`, which already contains it.
2. **Always return `view_response.rest_response`**, never a raw DRF `Response`.
3. **Never call `log_view_response()` by hand.** The mixin does it.

> **If you are reading an older `CLAUDE.md` or an old branch:** the pattern used
> to require an explicit `log_view_response(...)` call in every method. It does
> not any more. `LoggingMixin` replaced that, and there is currently not a single
> manual call left in the codebase. Adding one back produces duplicate log lines.

---

## Why logging is automatic

`ViewResponse.rest_response` stamps a back-reference onto the DRF response:

```python
response = Response(data=data_content, status=self._response_status_code)
response._view_response = self
```

`LoggingMixin.finalize_response` looks for that attribute and, when present,
calls `log_view_response()` with the view name, the action, the request body,
path, and method. That is why returning the raw `Response` breaks logging: the
back-reference is what the mixin keys on.

The log level is chosen from the response, not by you:

| Response | Level |
|---|---|
| `is_successful`, or 3xx | `info` |
| 4xx | `warning` |
| 5xx and everything else | `error` |

Each line carries `user_id` (pulled from the global context), `view_name`,
`method`, `request_body`, `request_path`, `request_method`, `is_successful`, and
the exception name, detail, and stack trace when there is one.

---

## The success envelope

Every successful response has this shape:

```json
{
  "success": true,
  "status_code": 200,
  "response_code": "MSG_RETRIEVE_CONTENT_SUCCESS",
  "response_body": { },
  "message": "Success"
}
```

Your actual payload is nested under `response_body`. This matters when writing
tests: assert against `response.data.get("response_body")`, not `response.data`.

Errors use a different envelope entirely. See [errors.md](errors.md).

---

## `ViewResponse` variants

| Class | Status | Use |
|---|---|---|
| `ViewResponse(...)` | you pass it | The general case. Requires `response_body`, `response_status`, `is_successful`, `response_information_code`. |
| `ViewSuccessResponse(...)` | 200 | Success with sensible defaults: `MessageCode.GENERAL_SUCCESS`, message `"Success"`. |
| `ViewResponseNoContent(...)` | 200 | Deletes and actions with no body. Note it returns **200 with a null body**, not 204. |
| `ViewFailResponse(error_msg, response_status, ...)` | you pass it | An explicit failure. Prefer raising `CustomException`. |
| `ViewValidationFailureResponse(error_msg)` | 400 | Validation failure. Prefer raising `CustomException`. |
| `ViewServerErrorResponse(error_msg)` | 500 | Server error. Prefer letting the exception handler do this. |

The `ViewFailResponse` family exists and works, but on new code prefer raising a
`CustomException` and letting the global handler render it. That gives you the
RFC 7807 envelope, the typed error codes, and the field errors map, none of which
`ViewFailResponse` produces.

`ViewFailResponse` adds `str(exception)` to the response body when
`settings.DEBUG` is true. Do not depend on that.

---

## `MessageCode`

Serialized as `MSG_` plus the member name, so `MessageCode.LIST_CONTENT_SUCCESS`
becomes `"MSG_LIST_CONTENT_SUCCESS"`.

Available members:

`GENERAL_SUCCESS`, `BASE_LOGIN_SUCCESS`, `USER_LOGIN_SUCCESS`,
`UPLOAD_FILE_REQUEST_SUCCESS`, `LIST_CONTENT_SUCCESS`,
`RETRIEVE_CONTENT_SUCCESS`, `CREATE_CONTENT_SUCCESS`, `UPDATE_CONTENT_SUCCESS`,
`REMOVE_CONTENT_SUCCESS`, `REGISTRATION_SUCCESS`.

Conventional mapping:

| Action | Code |
|---|---|
| `list` | `LIST_CONTENT_SUCCESS` |
| `retrieve` | `RETRIEVE_CONTENT_SUCCESS` |
| `create` | `CREATE_CONTENT_SUCCESS` |
| `update`, `partial_update` | `UPDATE_CONTENT_SUCCESS` |
| `destroy` | `ViewResponseNoContent`, which uses `GENERAL_SUCCESS` |
| a custom action | `GENERAL_SUCCESS`, unless a specific one fits |

The member name is the client-facing contract. Renaming one is a breaking change.

---

## Choosing a serializer

```python
def get_serializer_class(self):
    if self.action == "partial_update":
        return UserPartialUpdateSerializer
    return UserSerializer
```

See [serializers.md](serializers.md).

---

## Where the logic goes

Views should stay thin. Anything that is a business rule belongs in a service.

```python
def make_purchase(self, request, *args, **kwargs):
    serializer = self.get_serializer(data=request.data)
    serializer.is_valid(raise_exception=True)
    PaymentService.make_purchase(request, serializer.validated_data)
    return ViewSuccessResponse().rest_response
```

The view validates input, calls the service, wraps the result. The service raises
`CustomException` on a broken rule and the global handler turns it into a
structured error, so views rarely need a `try/except`. See
[services.md](services.md).

---

## Object permissions during updates

`ModelViewSet.partial_update` is sometimes rewritten to guarantee that object
permissions are checked before the serializer runs:

```python
def partial_update(self, request, *args, **kwargs):
    instance = self.get_object()          # triggers has_object_permission
    serializer = self.get_serializer(instance, data=request.data, partial=True)
    serializer.is_valid(raise_exception=True)
    serializer.save()
    ...
```

Calling `self.get_object()` first is deliberate. See
[permissions.md](permissions.md) for the 403-versus-404 reasoning.

---

## Webhooks are different

The two store webhook viewsets in `payment/views.py` deliberately break several
rules above:

```python
class GooglePlayWebhookViewSet(GenericViewSet):
    permission_classes = [AllowAny]

    @extend_schema(exclude=True)
    def create(self, request, *args, **kwargs):
        log.info("Google Play webhook is received", request=str(request.data))
        try:
            handler = GoogleNotificationHandler(request.data)
            handler.handle()
        except Exception as e:
            log.error("Unhandled Google notification", request_data=request.data, exception=str(e))
        return ViewSuccessResponse().rest_response
```

- `AllowAny`, because the caller is Apple or Google, not one of your users.
  Authenticity is established by signature verification inside the handler, not
  by a permission class.
- No `LoggingMixin`, and explicit `log.info` / `log.error` calls instead.
- Every exception is swallowed and a success is returned anyway, so the store
  does not enter a retry loop over a notification we cannot process. The failure
  is captured in the logs instead.
- `@extend_schema(exclude=True)` keeps them out of the public OpenAPI schema.

Copy this shape only for other third-party webhooks. It is wrong everywhere else.

---

## Related

- [errors.md](errors.md) for the failure envelope.
- [services.md](services.md) for where the logic lives.
- [permissions.md](permissions.md) for `OwnershipMixin` and permission composition.
- [logging-and-context.md](logging-and-context.md) for what the global context adds.
