# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Django Project Structure

This is a Django REST Framework project with the following key structure:

- **manage/**: Django project root containing settings.py, urls.py, wsgi.py, asgi.py
- **settings/**: Environment-specific Django settings
  - `base.py`: Base settings imported by all environments
  - `development.py`: Development-specific settings
  - `test.py`: Test environment settings
  - `prod.py`: Production settings
  - `local_test.py`: Local test settings (removes logger app)
- **Custom Apps**: authy, user, common, contact_verification, payment, subscription, vendor, logger
- **utils/**: Shared utilities and helpers
- **custom_test/**: Custom test base classes and utilities
- **staticfiles/**: Static files for production
- **locale/**: Internationalization files (en, tr)

## Key Configuration

- **Authentication**: Custom JWT authentication via `authy.utils.custom_jwt_authentication.CustomJWTAuthentication`
- **Custom User Model**: `user.User` (AUTH_USER_MODEL) - Unified model combining authentication and user profile
- **Database**: PostgreSQL with dj-database-url
- **API Documentation**: Swagger UI at `/swagger/` and ReDoc at `/redoc/`
- **Internationalization**: Supports English and Turkish. Wrap all user-facing strings in `gettext_lazy as _`
- **Cloud Storage**: IDrive/AWS S3 integration
- **Payment**: Apple App Store and Google Play Store integration
- **Monitoring**: New Relic integration via gunicorn.conf.py
- **Admin UI**: django-unfold. Accessible with email/username + password via unified `User` model.

## Development Commands

```bash
# Run all tests (always generate migrations first)
python manage.py makemigrations
python manage.py test --settings=settings.local_test

# Run tests for specific app
python manage.py test authy.test --settings=settings.local_test

# Format code
black .

# i18n
python manage.py makemessages -l tr
python manage.py compilemessages
```

## Architecture

### View Layer (CRITICAL — replicate exactly)

Every view method must follow this pattern:

```python
from structlog import get_logger
from common.response.view_response import ViewResponse, ViewResponseNoContent, log_view_response
from common.response.response_information_codes.message_code import MessageCode

log = get_logger(__name__)  # module-level, always

class MyViewSet(OwnershipMixin, ModelViewSet):
    def retrieve(self, request, *args, **kwargs):
        response = super().retrieve(request, *args, **kwargs)
        view_response = ViewResponse(
            response_body=response.data,
            response_status=response.status_code,
            is_successful=True,
            response_information_code=MessageCode.RETRIEVE_CONTENT_SUCCESS,
        )
        log_view_response(
            struct_logger=log,
            view_name=self.__class__.__name__,
            method_name="retrieve",
            request_body=request.data,
            request_path=request.get_full_path(),
            request_method=request.method,
            view_response=view_response,
        )
        return view_response.rest_response  # ALWAYS return this, not raw DRF Response
```

**Rules:**

- Always call `log_view_response()` after every action
- Always `return view_response.rest_response`, never a raw `Response`
- `log_view_response` auto-picks log level: `info` (success), `warning` (4xx), `error` (5xx)

**Response envelope** (all responses share this shape):

```json
{ "success": true, "status_code": 200, "response_code": "MSG_...", "response_body": {}, "message": "..." }
```

**ViewResponse variants** (from `common/response/view_response.py`):

- `ViewSuccessResponse(response_body, response_status, response_information_code)` — success
- `ViewResponseNoContent()` — 204 delete/action with no body
- `ViewFailResponse(error_msg, response_status, exception, response_information_code)` — explicit failure
- `ViewValidationFailureResponse(error_msg)` — 400 validation
- `ViewServerErrorResponse(error_msg)` — 500

**MessageCode** values (from `common/response/response_information_codes/message_code.py`):
`GENERAL_SUCCESS`, `LIST_CONTENT_SUCCESS`, `RETRIEVE_CONTENT_SUCCESS`, `CREATE_CONTENT_SUCCESS`, `UPDATE_CONTENT_SUCCESS`

### Service Layer

Business logic lives in `{app}/services.py`. Views call services; services call models.

```python
class UserService:
    @staticmethod
    def deactivate(user_id: str) -> User:
        user = User.objects.get(id=user_id)
        if not user.is_active:
            raise CustomException.business_logic_error(
                title="Already Inactive",
                detail="User is already deactivated.",
            )
        user.is_active = False
        user.save()
        return user
```

**Rules:**

- All methods are `@staticmethod`
- Services raise `CustomException` (never raw DRF exceptions)
- Views call service methods and wrap results in a `ViewResponse`

### Serializer Pattern

```python
def get_serializer_class(self):
    if self.action == "partial_update":
        return UserPartialUpdateSerializer
    return UserSerializer
```

Use action-specific serializers via `get_serializer_class()`. Serializers handle validation; services handle business logic.

### Permission System

Key components from `common/permissions/generic_permissions.py`:

- **`ActionAwareModelPermissions`**: Enhanced `DjangoModelPermissions` that includes `view_*` permission on GET. Custom action permissions named `{app_label}.{view_name}_{action}` (e.g., `user.user_reset_password`).
- **`ShortCircuitOr(*permissions)`**: True short-circuit OR. Prefer over `|` operator to avoid side effects.
- **`IsOwner`**: Pure ownership check, safe for composition.
- **`IsReadonly`**: Allows only safe HTTP methods.
- **`ConditionalPermission({lambda: PermClass})`**: Applies different permissions based on runtime conditions.

Most common pattern (admin OR owner):

```python
from common.permissions.generic_permissions import ShortCircuitOr, ActionAwareModelPermissions, IsOwner
from common.view_mixins import OwnershipMixin

class MyViewSet(OwnershipMixin, ModelViewSet):
    permission_classes = [ShortCircuitOr(ActionAwareModelPermissions, IsOwner)]
```

### View Mixins (`common/view_mixins.py`)

- **`OwnershipMixin`**: Combines filtering + `user_id` injection. For `list`, filters to user's own objects; for object-level actions, returns unfiltered queryset (relies on `has_object_permission` for 403 vs 404).
- **`OwnershipFilterMixin`**: Queryset filtering only.
- **`UserIDInjectionMixin`**: Auto-injects `user_id` on create for users without broad permissions.

### Error Handling (CRITICAL)

Services and views raise `CustomException` (from `common/custom_exceptions/custom_exception.py`). The global `custom_exception_handler` converts all exceptions to structured RFC 7807 responses automatically.

**Factory methods:**

```python
CustomException.validation_error(field_errors={"email": [FieldErrorCode.INVALID_EMAIL]})
CustomException.field_validation_error(field="email", code=FieldErrorCode.INVALID_EMAIL, message="...", value="bad@")
CustomException.business_logic_error(title="Conflict", detail="Already exists.")
CustomException.multiple_business_logic_errors(errors=[{"title": "...", "detail": "...", "code": GeneralErrorCode.X}])
CustomException.not_found_error(title="Not Found", detail="Resource missing.")
CustomException.authentication_error()
CustomException.authorization_error()
CustomException.client_error(title="Bad Request", detail="...")
CustomException.server_error()
```

**Error codes:**

- `ErrorCode` enum — values serialized as `ERR_{NAME}` (e.g., `ERR_NOT_FOUND_ERROR`)
- `FieldErrorCode` enum — field-level validation codes
- `GeneralErrorCode` enum — for `multiple_business_logic_errors`

**Error response shape** (from exception handler):

```json
{
  "type": "...",
  "status": 400,
  "title": "...",
  "detail": "...",
  "instance": "...",
  "response_code": "ERR_...",
  "errors": { "field": [{ "code": "FIELD_ERR_...", "message": "...", "value": "..." }] }
}
```

### Logging

```python
from structlog import get_logger
log = get_logger(__name__)  # always at module top
```

All logging goes through `log_view_response()` inside view methods — do not log separately in services. Logs include `user_id`, `view_name`, `method`, exception details, request/response context. Production logs ship to New Relic via `logger/logging_processors.py`.

## Testing Guidelines

- **Base classes**: `CustomAPITestCase` (API tests) and `CustomIntegrationTestCase` (non-API) from `custom_test/base_test.py`
- **Test location**: `{app}/test/test_integration.py`
- **Test settings**: always `--settings=settings.local_test`
- **Always generate migrations before running tests**: `python manage.py makemigrations`

### Standard setUp

```python
class MyTestCase(CustomAPITestCase):
    def setUp(self):
        super().setUp()
        self.create_standard_users()   # creates self.user/self.user_password + self.admin/self.admin_password
        self.authenticate_as(self.user)
```

### Key Test Helpers

- `create_standard_users()` — Creates `self.user`/`self.user_password` and `self.admin`/`self.admin_password`. Call in `setUp()`.
- `authenticate_as(user)` — Force-authenticates without HTTP. Use for all non-auth tests.
- `create_user(**kwargs)` / `create_admin_user(**kwargs)` — Create users via `model_bakery`, auto-generating phone and email if omitted.
- `login_user(user, password)` — Real HTTP login; returns `response_body`. Use only for auth flow tests.
- `create_common_models()` — **Deprecated.** Use `create_standard_users()` and explicit `baker.make()` calls instead.

### Permission Testing

Use `CRUDPermissionTestsMixin` from `custom_test/mixins.py` for standard permission test coverage. Subclasses must define `list_url_name`, `detail_url_name`, `create_data`, `update_data`, and `resource_factory()`.

```python
class MyPermissionTests(CRUDPermissionTestsMixin, CustomAPITestCase):
    list_url_name = "my-model-list"
    detail_url_name = "my-model-detail"
    create_data = {"name": "test"}
    update_data = {"name": "updated"}
    unauthenticated_read_allowed = False  # override defaults as needed

    def resource_factory(self):
        return baker.make(MyModel)
```

### Test Data & Naming

- Use `model_bakery` (`baker.make(MyModel)`) for object creation
- Complex shared fixtures go in `custom_test/baker_recipes.py`
- Name tests: `test_{action}__{scenario}` with a docstring explaining expected behavior
- Assert against `response.data.get("response_body")` due to the response envelope

## CI/CD

GitHub Actions (`.github/workflows/pr_check.yml`) runs on every PR:

- Black code formatting check
- Migration generation and compilation
- Django test suite with PostgreSQL

## Important Notes

- **Migration Files**: Always generate locally before testing. **Never commit migration files.**
- **Settings Import**: `manage/settings.py` imports from `settings/*`
- **Environment Variables**: Managed via `django-environ` and `.env` files
- **Soft Delete**: `django-soft-delete` on applicable models
- **Phone Numbers**: `django-phonenumber-field`
- **Pagination**: `CustomPageNumberPagination` from `common.pagination`
- **UUIDs**: Used as primary keys for `User` model
- **Social Auth**: Apple, Google, Facebook in `authy/social_auth/`. Uses `SOCIAL_SECRET` setting.
