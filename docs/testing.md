# Testing

[Back to docs index](README.md)

---

## Running tests

Generate migrations first. This is the single most common cause of a confusing
failure, because migration files are not committed.

```bash
python manage.py makemigrations
bin/run-tests
```

`bin/run-tests` finds every directory containing a `test_*.py` and runs each with
`--settings=settings.local_test`. It takes paths and flags:

```bash
bin/run-tests authy                    # one app
bin/run-tests authy user --failfast    # several, with a flag
bin/run-tests . --keepdb               # reuse the test database, much faster
```

Or drive Django directly, but never forget the settings module:

```bash
python manage.py test authy.test --settings=settings.local_test
```

Without `--settings=settings.local_test` you get the development settings, which
means live throttling, real Celery, and the `logger` app trying to ship logs to
New Relic.

### What `settings/local_test.py` changes

| Change | Why |
|---|---|
| Removes `logger` from `INSTALLED_APPS` | structlog is configured in that app's `ready()`. Dropping it stops tests shipping logs. |
| `DEFAULT_THROTTLE_CLASSES = []` | Otherwise a test suite hits the 5-per-minute auth throttle and fails at random. |
| `CELERY_TASK_ALWAYS_EAGER = True` | Tasks run inline, so no worker is needed. |
| `CELERY_TASK_EAGER_PROPAGATES = True` | A failing task fails the test instead of being swallowed. |
| `VERIFICATION_ACTIVE_INTERVAL = 300` | Predictable verification-code expiry. |

---

## Base classes

Both live in `custom_test/base_test.py`.

| Class | Use for |
|---|---|
| `CustomAPITestCase` | Anything that makes HTTP requests. This is what you want almost always. |
| `CustomIntegrationTestCase` | Services, models, and helpers, with no HTTP client. |

`CustomAPITestCase` is `CustomIntegrationTestCase` plus DRF's `APITestCase`, so
every helper below is available on both.

---

## The standard `setUp`

```python
from custom_test.base_test import CustomAPITestCase


class WidgetTests(CustomAPITestCase):
    def setUp(self):
        super().setUp()                # required: initialises the phone counter
        self.create_standard_users()   # self.user, self.user_password, self.admin, self.admin_password
        self.authenticate_as(self.user)
```

Calling `super().setUp()` is not optional. It sets up the counter that
`generate_valid_phone_number()` uses, and without it user creation collides on
the unique phone field.

---

## Helpers

| Helper | Returns | Notes |
|---|---|---|
| `create_standard_users()` | nothing | Sets `self.user` / `self.user_password` and `self.admin` / `self.admin_password`. Call it in `setUp`. |
| `create_user(password="123", **kwargs)` | `(user, password)` | Generates a unique phone and email if you do not pass them, and marks the phone verified. |
| `create_admin_user(password="123", **kwargs)` | `(user, password)` | A user in the `Admin` group with `is_staff` and `is_superuser` set. |
| `authenticate_as(user)` | nothing | Force-authenticates with no HTTP round trip. Use this everywhere except auth flow tests. `authenticate_as(None)` clears it. |
| `login_user(user, password)` | `response_body` | A real HTTP login against `authy:login`. Use only when testing the login flow itself. |
| `login_admin_user()` | `response_body` | `login_user` for `self.admin`. |
| `set_global_context(user)` | nothing | Installs a `GlobalContext` for the user, cleaned up automatically. Needed when the code under test reads the context outside a request. |
| `generate_valid_phone_number()` | `str` | Sequential valid `+90` numbers. |
| `create_user_group(name)` / `create_user_permission(name)` | object | Thin `baker.make` wrappers. |
| `create_translation(...)` / `create_product(...)` / `get_locale()` | object | Convenience fixtures for the translation and buyable models. |
| `create_common_models()` | nothing | **Deprecated.** Use `create_standard_users()` plus explicit `baker.make()` calls. |

Note `create_user` and `create_admin_user` return a **tuple**. Unpack it:

```python
user, password = self.create_user(email="someone@example.com")
```

### `authenticate_as` versus `login_user`

`authenticate_as` skips HTTP entirely. It is faster, it does not touch the
throttle, and it does not depend on the login endpoint working. Use it for every
test that is not about authentication.

`login_user` performs a real `POST /auth/login`, and returns the parsed
`response_body` containing the tokens. Use it only when the login flow itself is
what you are testing.

---

## Assert against `response_body`

Successful responses are wrapped in the success envelope, so your payload is
nested:

```python
response = self.client.get(url)
self.assertEqual(response.status_code, status.HTTP_200_OK)

body = response.data.get("response_body")
self.assertEqual(body["fullname"], "Ada Lovelace")
```

Asserting on `response.data["fullname"]` fails, because that level holds
`success`, `status_code`, `response_code`, `response_body`, and `message`.

Errors use a different envelope again:

```python
self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
self.assertFalse(response.data["success"])
self.assertEqual(response.data["response_code"], "ERR_GENERAL_VALIDATION_ERROR")
self.assertIn("email", response.data["errors"])
```

See [conventions/views.md](conventions/views.md) and
[conventions/errors.md](conventions/errors.md).

---

## Test data

Use `model_bakery` rather than fixtures:

```python
from model_bakery import baker

widget = baker.make(Widget, name="test")
widgets = baker.make(Widget, _quantity=5)
```

Anything shared and non-trivial goes in `custom_test/baker_recipes.py` as a
`Recipe`:

```python
from model_bakery.recipe import Recipe

google_payment_transaction = Recipe(
    PaymentTransaction,
    payment_vendor=PaymentVendor.GOOGLE.value,
    status=PaymentStatus.SUCCEEDED,
    ...
)
```

```python
from model_bakery import baker

transaction = baker.make_recipe("custom_test.baker_recipes.google_payment_transaction")
```

---

## Permission tests

`CRUDPermissionTestsMixin` in `custom_test/mixins.py` gives you ten tests for
free, covering the regular-user and unauthenticated matrix:

```python
from model_bakery import baker
from custom_test.base_test import CustomAPITestCase
from custom_test.mixins import CRUDPermissionTestsMixin


class WidgetPermissionTests(CRUDPermissionTestsMixin, CustomAPITestCase):
    list_url_name = "widget:widget-viewset"
    detail_url_name = "widget:widget-detail-viewset"
    create_data = {"name": "test"}
    update_data = {"name": "updated"}

    def setUp(self):
        super().setUp()
        self.create_standard_users()

    def resource_factory(self):
        return baker.make(Widget)
```

| Attribute | Default | Meaning |
|---|---|---|
| `list_url_name` | required | URL name for list and create |
| `detail_url_name` | required | URL name for retrieve, update, delete |
| `detail_url_kwarg` | `"id"` | The URL keyword argument |
| `create_data` | required | POST body |
| `update_data` | required | PATCH body |
| `resource_factory()` | required | Returns an existing instance |
| `unauthenticated_read_allowed` | `True` | `False` expects 401 on read |
| `regular_user_read_allowed` | `True` | `False` expects 403 on read |

The delete tests also assert the object still exists afterwards, which catches a
permission that returns the right status while still deleting the row.

**URL names are namespaced.** Every app sets `app_name`, so it is
`authy:login`, not `login`. A test that forgets the prefix fails with
`NoReverseMatch`.

---

## The meta-tests

Four tests in `custom_test/` police the codebase itself rather than any feature.
They run as part of the normal suite. When one fails, read it before working
around it.

| File | Enforces |
|---|---|
| `test_check_permissions.py` | Every `ModelViewSet` has a coherent permission configuration and the custom action permissions it references exist. |
| `test_check_global_context_usage.py` | `GlobalContext` is used only in `views.py`, permissions, middleware, and `common/response`. Models, services, tasks, and serializers must receive data as explicit parameters, so they work in a shell, in Celery, and in tests. |
| `test_exception_translations.py` | Every exception handler string is marked for translation and translated in every language, with no orphaned markers. See [conventions/i18n.md](conventions/i18n.md). |
| `test_structured_error_responses.py` | The error envelope keeps its documented shape. See [conventions/errors.md](conventions/errors.md). |

The global context test is the one that surprises people. Calling
`GlobalContextMiddleware.get_global_context()` inside a service fails the build,
by design. Pass `user_id` or `language_code` in as an argument instead.

---

## Conventions

**Location.** `{app}/test/test_integration.py`. Anything matching `test_*.py`
under a package is picked up by both `bin/run-tests` and CI.

**Naming.** `test_{action}__{scenario}`, with a docstring stating the expected
behaviour:

```python
def test_partial_update__non_owner_gets_403(self):
    """A user patching another user's record is rejected with 403, not 404."""
```

The double underscore separates the action from the scenario and makes failures
readable at a glance.

**One behaviour per test.** If the name needs an "and", it is two tests.

---

## CI

`.github/workflows/ci.yml` runs on every PR to `develop` or `master`:

1. **Lint**: `black --check .` then `ruff check .`
2. **Test**, only if lint passed: PostgreSQL 15 service, `compilemessages`,
   `makemigrations --check --dry-run`, `collectstatic`, then the suite directory
   by directory.

Reproduce it locally with `bin/lint` and `bin/run-tests`. See
[operations/ci.md](operations/ci.md).

---

## Related

- [conventions/permissions.md](conventions/permissions.md) for what the permission tests assert.
- [conventions/errors.md](conventions/errors.md) for the error envelope.
- [getting-started.md](getting-started.md) for the migration prerequisite.
