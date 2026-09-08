# Errors

[Back to docs index](../README.md)

Every error this API returns has the same shape, and every one of them carries a
machine-readable code. You get that for free by raising `CustomException`. You do
not build error responses by hand.

Source: `common/custom_exceptions/custom_exception.py`,
`common/response/structured_error_response.py`,
`common/exception_handling/custom_exception_handler.py`.

---

## How it works

`settings/base.py` registers one exception handler for the entire API:

```python
REST_FRAMEWORK = {
    "EXCEPTION_HANDLER": "common.exception_handling.custom_exception_handler.custom_exception_handler",
}
```

Anything raised inside a view, a serializer, or a service reaches that handler,
which classifies it and renders a structured body. There are five paths through
it, tried in order:

| Raised | Handled as |
|---|---|
| `CustomException` | Your explicit error. Field errors, title, detail, and code all come from what you passed. |
| DRF `ValidationError` | Walked recursively, including nested serializers and list serializers, into per-field entries. `non_field_errors` become general errors. |
| Any other `APIException` | Looked up in `API_EXCEPTION_HANDLER_MAPPER`. |
| A Django exception listed in `EXCEPTION_HANDLER_MAPPER` | For example `IntegrityError`. Mapped to a message, status, and code. |
| Anything else | A generic 500 with `ERR_INTERNAL_SERVER_ERROR`. The real exception is logged, never returned. |

All five log through structlog before returning: `warning` for 4xx, `error` for
5xx.

---

## The error envelope

```json
{
  "success": false,
  "type": "validation_error",
  "status": 400,
  "response_code": "ERR_GENERAL_VALIDATION_ERROR",
  "instance": "/auth/register",
  "title": "Validation Error",
  "detail": "The request data is invalid.",
  "errors": {
    "email": [
      { "code": "invalid_email", "message": "Please enter a valid email address" }
    ]
  }
}
```

Served with content type `application/problem+json`.

| Field | Notes |
|---|---|
| `success` | Always `false` on this envelope. |
| `type` | One of `validation_error`, `client_error`, `server_error`, `authentication_error`, `authorization_error`, `business_logic_error`, `not_found_error`. |
| `status` | Mirrors the HTTP status. |
| `response_code` | **Always present**, always `ERR_`-prefixed, including on errors raised by DRF's own validators. |
| `instance` | Derived from the request path by the handler. There is no `instance=` argument. Never pass it. |
| `title`, `detail` | Human-readable. From your `CustomException`, or from the handler's defaults. |
| `errors` | Present only when there are field errors, or more than one general error. |

### How `response_code` is resolved

`StructuredErrorResponse.resolve_response_code()` tries three sources in order,
so no construction path can produce a body without one:

1. The response-level `error_code`.
2. If there is exactly one general error and it carries a code, that code.
3. `DEFAULT_ERROR_CODE_BY_TYPE[error_type]`, mapping for instance
   `AUTHORIZATION_ERROR` to `ERR_PERMISSION_DENIED`.

### The `errors` map

Every entry shares a `{code, message}` core.

```json
"errors": {
  "email":    [{ "code": "invalid_email", "message": "..." }],
  "password": [{ "code": "password_too_short", "message": "..." }]
}
```

Entries under the reserved `general` key, used when there are multiple non-field
errors, add a `title` on top of that core:

```json
"errors": {
  "general": [
    { "code": "insufficient_funds",   "title": "Insufficient Funds",   "message": "Your balance is too low" },
    { "code": "daily_limit_exceeded", "title": "Daily Limit Exceeded", "message": "You have exceeded your daily limit" }
  ]
}
```

Field entries never echo the submitted value back. Nested serializer fields are
flattened with dots: `address.postcode`. List serializer entries use the index:
`items.0.quantity`.

---

## Raising errors

Nine factory methods on `CustomException`. Prefer them over the constructor.

```python
from common.custom_exceptions.custom_exception import CustomException
from common.response.response_information_codes.field_error_code import FieldErrorCode
from common.response.response_information_codes.general_error_code import GeneralErrorCode
```

| Factory | Status | Use for |
|---|---|---|
| `validation_error(field_errors=..., general_message=..., title=...)` | 400 | Several fields failed at once. |
| `field_validation_error(field=..., code=..., message=...)` | 400 | Exactly one field failed. |
| `business_logic_error(title=..., detail=..., code=..., extra_data=...)` | 400 | A rule was broken, not a format. |
| `multiple_business_logic_errors(errors=[...])` | 400 | Several rules broken at once. |
| `client_error(title=..., detail=...)` | 400 | A malformed request that is not field-shaped. |
| `authentication_error(title=..., detail=...)` | 401 | Missing or invalid credentials. |
| `authorization_error(title=..., detail=...)` | 403 | Authenticated, but not allowed. |
| `not_found_error(title=..., detail=...)` | 404 | Resource does not exist. |
| `server_error(title=..., detail=...)` | 500 | Something on our side. |

Also available: `CustomException.from_exception(exc, code=..., status_code=...)`,
to wrap a third-party exception without losing its message.

### Examples

One field:

```python
raise CustomException.field_validation_error(
    field="email",
    code=FieldErrorCode.EMAIL_ALREADY_EXISTS,
    message=_("An account with this email already exists."),
)
```

Several fields:

```python
raise CustomException.validation_error(
    field_errors={
        "email": [FieldErrorCode.INVALID_EMAIL],
        "password": [FieldErrorCode.PASSWORD_TOO_SHORT],
    }
)
```

A broken rule:

```python
raise CustomException.business_logic_error(
    title=_("Already Inactive"),
    detail=_("User is already deactivated."),
    code=ErrorCode.AN_ERROR_OCCURED,
)
```

Several broken rules:

```python
raise CustomException.multiple_business_logic_errors(
    errors=[
        {
            "title": _("Insufficient Funds"),
            "detail": _("Your balance is too low."),
            "code": GeneralErrorCode.INSUFFICIENT_FUNDS,
        },
        {
            "title": _("Daily Limit Exceeded"),
            "detail": _("You have exceeded your daily limit."),
            "code": GeneralErrorCode.DAILY_LIMIT_EXCEEDED,
        },
    ]
)
```

---

## The three code enums

They are different things. Mixing them up is the most common mistake here.

| Enum | Serialized as | Appears in | Example |
|---|---|---|---|
| `ErrorCode` | `ERR_` + member name | The top-level `response_code` | `ERR_NOT_FOUND_ERROR` |
| `FieldErrorCode` | lowercased member name | `errors.<field>[].code` | `invalid_email` |
| `GeneralErrorCode` | lowercased member name | `errors.general[].code` | `insufficient_funds` |

All three override `value` through `DynamicClassAttribute`, so the member name is
the contract. Renaming a member is a breaking API change for clients.

`FieldErrorCode` and `GeneralErrorCode` both offer `from_string()`, which the
handler uses to map DRF's own string codes onto the enums.

Adding a code means adding a member to the relevant enum. Do not invent free-form
strings: they will pass through, because both fields accept `str` for backward
compatibility, but clients cannot switch on them reliably.

---

## Rules

- Raise `CustomException` from services and serializers. Never construct an error
  `Response` by hand.
- Never pass `instance=`. The handler derives it from the request.
- Wrap every user-facing `title` and `detail` in `gettext_lazy as _`. See
  [i18n.md](i18n.md).
- Do not catch an exception just to re-raise it as a 500. Unhandled exceptions
  already become a safe, logged 500.
- `ViewFailResponse` includes `str(exception)` in the body when `settings.DEBUG`
  is true. That is a development aid. Do not rely on it, and do not run with
  `DEBUG=True` anywhere real.

---

## Related

- [views.md](views.md) for the success envelope, which is a different shape.
- [i18n.md](i18n.md) for translating handler strings.
- `custom_test/test_structured_error_responses.py` is a repo-wide meta-test that
  asserts the contract described above. If you change the envelope, that test
  changes with it.
