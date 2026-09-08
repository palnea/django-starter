# Architecture

[Back to docs index](README.md)

This is the document to read first. Everything under `conventions/` and `apps/`
is detail hanging off what follows.

---

## The shape of it

An ordinary Django REST Framework monolith, with four opinions layered on top:

1. **One response envelope.** Every success looks the same, every error looks
   the same, and both carry a machine-readable code.
2. **One exception handler.** Nothing constructs an error response by hand.
3. **Automatic logging.** Views do not log. The infrastructure does.
4. **Permissions, never roles.** Access is Django model permissions plus
   object-level ownership, with no `if user.role == ...` anywhere.

Break any of them and the API stops being uniform, which is the entire value on
offer.

---

## A request, end to end

```
HTTP request
    |
    v
HealthCheckMiddleware ......... /health short-circuits here, before routing
CorsMiddleware
SecurityMiddleware
WhiteNoiseMiddleware .......... static files in production
SessionMiddleware
CommonMiddleware
CsrfViewMiddleware
AuthenticationMiddleware ...... request.user for session-authenticated callers
GlobalContextMiddleware ....... request_id + GlobalContext, bound to structlog
MessageMiddleware
XFrameOptionsMiddleware
SwaggerAccessMiddleware ....... passcode gate on /swagger/, /redoc/, /api/schema/
LocaleMiddleware .............. activates the language
    |
    v
URL routing (manage/urls.py -> {app}/urls.py)
    |
    v
CustomJWTAuthentication ....... validates the Bearer token, tags New Relic
    |
    v
Permission classes ............ ActionAwareModelPermissions / IsOwner / ...
    |
    v
View ........................... OwnershipMixin filters or injects, serializer validates
    |
    v
Service ........................ business rules, transactions
    |
    v
Model .......................... persistence
    |
    v
ViewResponse ................... wraps the result in the success envelope
    |
    v
LoggingMixin.finalize_response . logs the whole exchange
    |
    v
HTTP response (+ X-Request-ID)
```

When anything raises, control jumps out of that chain into
`custom_exception_handler`, which renders the error envelope and logs it. There
is no path that produces an unstructured error.

### Middleware worth knowing

| Middleware | Why it matters |
|---|---|
| `HealthCheckMiddleware` | Returns `ok` for `/health` before routing, authentication, or the database. A health check that passes even when the app is broken is the point. |
| `GlobalContextMiddleware` | Creates the request ID and the request-scoped context. Everything downstream that needs the current user, language, or permissions reads it from here. See [conventions/logging-and-context.md](conventions/logging-and-context.md). |
| `SwaggerAccessMiddleware` | Session-based passcode gate on the API docs. See [operations/api-schema.md](operations/api-schema.md). |
| `LocaleMiddleware` | Last, so it sees everything the earlier middleware set up. |

---

## The layers

| Layer | File | Responsibility |
|---|---|---|
| View | `{app}/views.py` | HTTP. Pick a serializer, call a service, wrap the result. |
| Serializer | `{app}/serializers.py` | Shape and field validation. |
| Service | `{app}/services.py` | Business rules, orchestration, transactions. |
| Model | `{app}/models.py` | Persistence and model-level invariants. |

The direction is strictly downward. A service that imports `ViewResponse` is
reaching up, and a view that queries a model across app boundaries is reaching
sideways. Both are bugs in the making.

Read [conventions/views.md](conventions/views.md) and
[conventions/services.md](conventions/services.md) before writing either.

### Where the exceptions to this live

- **Strategies**, in `payment/subscription/strategies.py`. Stateful objects,
  subclassed per store, holding a receipt through a multi-step verification. Not
  services, and not in `services.py`.
- **Notification handlers**, in `vendor/notification_handlers/`. They react to
  store webhooks, run outside the view path, and log for themselves.
- **Clients**, in `communications/clients/`, `vendor/clients/`, and
  `cloud_storage/`. Thin adapters over an external API, with no business rules.

---

## The two envelopes

Success, produced by `ViewResponse`:

```json
{
  "success": true,
  "status_code": 200,
  "response_code": "MSG_RETRIEVE_CONTENT_SUCCESS",
  "response_body": { },
  "message": "Success"
}
```

Failure, produced by `custom_exception_handler`, RFC 7807 shaped and served as
`application/problem+json`:

```json
{
  "success": false,
  "type": "validation_error",
  "status": 400,
  "response_code": "ERR_GENERAL_VALIDATION_ERROR",
  "instance": "/auth/register",
  "title": "Validation Error",
  "detail": "The request data is invalid.",
  "errors": { "email": [{ "code": "invalid_email", "message": "..." }] }
}
```

They are different shapes. A client checks `success` first, then reads
`response_body` or `errors`. Payload always lives under `response_body`, which is
why tests assert against `response.data.get("response_body")`.

Details: [conventions/views.md](conventions/views.md),
[conventions/errors.md](conventions/errors.md).

---

## Authentication

JWT via `djangorestframework-simplejwt`, behind `CustomJWTAuthentication`, which
adds one thing to the stock class: it tags the New Relic transaction with the
user ID.

```python
SIMPLE_JWT = {
    "ACCESS_TOKEN_LIFETIME": timedelta(minutes=15),
    "REFRESH_TOKEN_LIFETIME": timedelta(days=30),
    "ROTATE_REFRESH_TOKENS": True,
    "BLACKLIST_AFTER_ROTATION": True,
    "USER_ID_CLAIM": "account_id",
    "AUTH_HEADER_TYPES": ("Bearer",),
}
```

Refresh tokens rotate and the old one is blacklisted, via
`rest_framework_simplejwt.token_blacklist`. Note `USER_ID_CLAIM` is
`account_id`, while `GlobalContext.user_id` reads a separate `user_id` claim that
the token serializer adds. Session and Basic authentication are also enabled,
which is what makes the Django admin work.

See [apps/authy.md](apps/authy.md).

---

## Authorisation

Default is `IsAuthenticated` for the whole API. Beyond that:

- `ActionAwareModelPermissions`, Django model permissions that also require
  `view_*` on GET and give custom actions their own permission.
- `IsOwner`, a side-effect-free ownership check.
- `ShortCircuitOr(...)`, composition that stops at the first pass.
- `OwnershipMixin`, which filters list querysets and injects `user_id` on create.

The list-versus-object asymmetry is deliberate and produces 403 rather than 404
for another user's object. See
[conventions/permissions.md](conventions/permissions.md).

---

## Settings

`manage/settings.py` is one line, `from settings import *`. The real selection
happens in `settings/__init__.py`, keyed on the `ENV` environment variable:

```
              settings/base.py
                     |
      +--------------+--------------+
      |              |              |
   prod.py        test.py     development.py
                                    |
                          +---------+---------+
                          |                   |
                   local_test.py       local_prod.py
```

| `ENV` | Module |
|---|---|
| `prod`, `production` | `settings/prod.py` |
| `test` | `settings/test.py` |
| `dev`, `local`, `development`, unset, or anything unrecognised | `settings/development.py` |
| `staging` | falls through to `settings/development.py` |

`local_test.py` and `local_prod.py` are never selected by `ENV`. You name them
explicitly with `--settings=`, which is why every test command in this repository
carries `--settings=settings.local_test`.

`local_test.py` drops `logger` from `INSTALLED_APPS`, disables throttling, and
makes Celery tasks eager. `local_prod.py` exists purely to run locally with
`DEBUG=False` so whitenoise behaves as it does in production.

See [operations/settings-and-env.md](operations/settings-and-env.md).

---

## The apps

### Core, useful in any project

| App | Owns |
|---|---|
| `user` | The `User` model, which is `AUTH_USER_MODEL`, keyed by UUID, soft-deletable, and combines authentication and profile |
| `authy` | Login, registration, token refresh, password flows, Google, Facebook and Apple sign-in |
| `common` | The response envelope, exception handling, permissions, mixins, pagination, throttles, middleware, plus the `Locale`/`Translation`/`TranslatedFile` content translation layer |
| `contact_verification` | Email and phone verification codes |
| `communications` | Email and SMS delivery. Not an installed app, just a package |
| `cloud_storage` | S3-compatible file storage. Also just a package |
| `logger` | structlog configuration and New Relic shipping |
| `utils` | Helpers with no app of their own |

### Domain-specific, delete if you do not sell subscriptions

| App | Owns |
|---|---|
| `payment` | `Buyable`, `PaymentTransaction`, `Purchase`, `PurchasedBuyable`, receipt verification, the store webhook endpoints |
| `vendor` | Store-side clients, webhook signature verifiers, notification strategies and handlers |
| `subscription` | `UserSubscription` and `UserSubscriptionChangeRecord` |

These three only make sense together. They are documented as one flow in
[apps/payments-and-subscriptions.md](apps/payments-and-subscriptions.md).

---

## Data model highlights

- **`User` is unified.** One model for authentication and profile, extending
  `AbstractBaseUser`, `SoftDeleteModel`, and `PermissionsMixin`, with a UUID
  primary key. There is no separate profile model to keep in sync.
- **Soft delete is the default** on most models, through `django-soft-delete`. A
  `destroy` sets `deleted_at` rather than removing the row, which is why the
  `User` viewset treats a repeat delete as a success.
- **Translations are rows, not files.** `Locale`, `Translation`, and
  `TranslatedFile` hold user-facing content in many languages. Separate from the
  `gettext` catalogues that translate the application's own strings.
- **Migrations are not committed.** Generate them locally. CI checks with
  `makemigrations --check --dry-run`.

---

## Asynchronous work

Celery 5.5 on Redis, with results in the database via `django-celery-results` and
schedules in the database via `django-celery-beat`.

```
web    gunicorn -c gunicorn.conf.py -w 3 manage.wsgi:application --timeout 15 --preload
worker celery -A manage worker -l INFO
beat   celery -A manage beat -l INFO --scheduler django_celery_beat.schedulers:DatabaseScheduler
```

The global context is **not** available inside a task. Anything a task needs must
be passed to it explicitly. See [operations/celery.md](operations/celery.md).

---

## Where to go next

| You want to | Read |
|---|---|
| Write an endpoint | [conventions/views.md](conventions/views.md), then [conventions/services.md](conventions/services.md) |
| Return an error | [conventions/errors.md](conventions/errors.md) |
| Restrict access | [conventions/permissions.md](conventions/permissions.md) |
| Write tests | [testing.md](testing.md) |
| Understand purchases | [apps/payments-and-subscriptions.md](apps/payments-and-subscriptions.md) |
| Deploy | [operations/deployment.md](operations/deployment.md) |
| Start a fresh project | [starting-a-new-project.md](starting-a-new-project.md) |
