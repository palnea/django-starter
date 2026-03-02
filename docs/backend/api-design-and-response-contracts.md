# API Design and Response Contracts

## Success Response Envelope

All successful responses are wrapped in a standard envelope by `ViewResponse`
(see `common/response/view_response.py`):

```json
{
  "success": true,
  "status_code": 200,
  "response_code": "MSG_RETRIEVE_CONTENT_SUCCESS",
  "response_body": { "id": "...", "name": "..." },
  "message": "Content retrieved successfully"
}
```

---

### Error Response Body Contract

All error responses follow the [RFC 7807 Problem Details](https://www.rfc-editor.org/rfc/rfc7807)
standard. The global `custom_exception_handler` (registered in Django settings as
`EXCEPTION_HANDLER`) converts every exception into one of the shapes below.

The `Content-Type` header for error responses is `application/problem+json`.

#### Field Validation Error

Returned when one or more request fields fail validation (HTTP 400).

```json
{
  "type": "validation_error",
  "status": 400,
  "title": "Validation Errors",
  "detail": "Multiple fields have validation errors.",
  "instance": "/api/user/",
  "response_code": "ERR_GENERAL_VALIDATION_ERROR",
  "errors": {
    "email": [
      {
        "code": "invalid_email",
        "message": "Enter a valid email address.",
        "value": "not-an-email"
      }
    ],
    "password": [
      {
        "code": "too_short",
        "message": "Ensure this field has at least 8 characters.",
        "value": null
      }
    ]
  }
}
```

**Field error object schema:**

| Field     | Type           | Description |
|-----------|----------------|-------------|
| `code`    | `string`       | Machine-readable code from `FieldErrorCode` enum (e.g., `required`, `invalid_email`, `too_short`). Full list in `common/response/response_information_codes/field_error_code.py`. |
| `message` | `string`       | Human-readable, localizable description of the error. |
| `value`   | `any \| null`  | The rejected input value, if available. |

#### General / Business Logic Error (single)

Returned for business rule violations, not-found, auth failures, etc.

```json
{
  "type": "business_logic_error",
  "status": 400,
  "title": "Already Inactive",
  "detail": "User is already deactivated.",
  "instance": "/api/user/123/deactivate/",
  "response_code": "ERR_AN_ERROR_OCCURED"
}
```

#### General Error (multiple)

Returned when multiple independent business errors apply to a single request.

```json
{
  "type": "business_logic_error",
  "status": 400,
  "title": "Multiple Issues Found",
  "detail": "Multiple issues were identified with your request.",
  "instance": "/api/payment/checkout/",
  "response_code": "ERR_AN_ERROR_OCCURED",
  "errors": {
    "general": [
      {
        "title": "Insufficient Funds",
        "detail": "Your balance is too low.",
        "code": "insufficient_funds"
      },
      {
        "title": "Daily Limit Exceeded",
        "detail": "You've exceeded your daily transaction limit.",
        "code": "daily_limit_exceeded"
      }
    ]
  }
}
```

#### Authentication / Authorization Error

```json
{
  "type": "authentication_error",
  "status": 401,
  "title": "Authentication Failed",
  "detail": "Authentication credentials were missing or invalid.",
  "instance": "/api/user/me/",
  "response_code": "ERR_AUTHENTICATION_FAILED"
}
```

```json
{
  "type": "authorization_error",
  "status": 403,
  "title": "Access Denied",
  "detail": "You do not have permission to perform this action.",
  "instance": "/api/admin/users/",
  "response_code": "ERR_PERMISSION_DENIED"
}
```

#### Server Error

```json
{
  "type": "server_error",
  "status": 500,
  "title": "Server Error",
  "detail": "An internal server error occurred. Please try again later.",
  "instance": "/api/user/"
}
```

#### Top-level field reference

| Field            | Type     | Always present | Description |
|------------------|----------|----------------|-------------|
| `type`           | `string` | Yes | One of: `validation_error`, `client_error`, `server_error`, `authentication_error`, `authorization_error`, `business_logic_error`, `not_found_error`. |
| `status`         | `int`    | Yes | HTTP status code (mirrors the response status). |
| `title`          | `string` | Yes | Short summary of the problem. |
| `detail`         | `string` | Yes | Human-readable explanation. |
| `instance`       | `string` | When available | The request path that triggered the error. |
| `response_code`  | `string` | When available | Machine-readable code from `ErrorCode` enum, prefixed with `ERR_`. |
| `errors`         | `object` | When applicable | Contains `general` (array) and/or field-name keys (array of field error objects). |

---

### API Versioning Strategy

#### Current state

The API is **unversioned**. All endpoints are served at their base paths (e.g.,
`/auth/`, `/user/`, `/payment/`) with no version prefix. The Swagger schema
declares `default_version="v1"` as metadata, but this is not enforced in URL
routing.

```
/auth/login/
/user/
/payment/checkout/
```

#### Policy for the next breaking change

When a breaking change becomes necessary, adopt **URL-prefix versioning**:

1. **Prefix new endpoints** with `/api/v2/` while keeping existing endpoints
   available at their current paths (treated as v1).
2. **Use DRF's `URLPathVersioning`** to let views branch on
   `request.version` where behavior must diverge.

   ```python
   # settings/base.py
   REST_FRAMEWORK = {
       ...
       "DEFAULT_VERSIONING_CLASS": "rest_framework.versioning.URLPathVersioning",
       "DEFAULT_VERSION": "v1",
       "ALLOWED_VERSIONS": ["v1", "v2"],
   }
   ```

3. **Deprecation timeline**: When v2 of an endpoint is released, v1 continues
   to work for at least **6 months**. Add a `Deprecation` HTTP header to v1
   responses during this window.
4. **Changelog**: Document every breaking change in a `CHANGELOG.md` entry
   before the version bump ships.

#### What counts as a breaking change

- Removing or renaming a response field.
- Changing the type of an existing response field.
- Removing an endpoint or changing its HTTP method.
- Adding a new required request field.

Non-breaking changes (safe without a version bump):

- Adding an optional request field.
- Adding a new response field.
- Adding a new endpoint.
- Fixing a bug in validation logic.
