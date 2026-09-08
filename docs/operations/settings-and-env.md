# Settings and environment variables

[Back to docs index](../README.md)

---

## How a settings module is chosen

```python
# manage/settings.py
from settings import *
```

```python
# settings/__init__.py
environment = get_environment(ENV)
if environment == Environment.PRODUCTION.value:
    from .prod import *
elif environment == Environment.TEST.value:
    from .test import *
else:
    from .development import *
```

So `DJANGO_SETTINGS_MODULE=manage.settings` defers the choice to the `ENV`
variable:

| `ENV` | Loads |
|---|---|
| `prod`, `production` | `settings/prod.py` |
| `test` | `settings/test.py` |
| `dev`, `local`, `development` | `settings/development.py` |
| `staging` | `settings/development.py` |
| unset, or unrecognised | `settings/development.py` |

`staging` is a recognised `Environment` value but has no branch, so it falls
through to development. It also has no `settings/logger/staging.ini`, which
breaks gunicorn's `post_fork`. Treat `ENV=staging` as unsupported until both are
added. See [deployment.md](deployment.md).

Naming a module directly, as `DJANGO_SETTINGS_MODULE=settings.development`, skips
`ENV` entirely. `bin/setup` writes that form into a fresh `.env`, and `bin/celery`
defaults to it.

## The module tree

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

| Module | Purpose |
|---|---|
| `base.py` | Everything shared. `DEBUG = False`, an insecure development `SECRET_KEY` |
| `development.py` | `DEBUG = True`, permissive CORS, placeholder defaults for every external credential. Tries `settings/local_overrides.py` at the end, which is gitignored |
| `test.py` | The deployed test environment. Reads `SECRET_KEY` from the environment |
| `prod.py` | Production. Reads `SECRET_KEY` from the environment. `ALLOWED_HOSTS` and `CORS_ALLOWED_ORIGINS` are placeholders you must edit |
| `local_test.py` | **Running the test suite.** Never selected by `ENV`, always named explicitly |
| `local_prod.py` | Running locally with `DEBUG=False`, via `bin/server --prod` |

### Local overrides

`settings/development.py` ends with:

```python
try:
    from settings.local_overrides import *
except Exception:
    pass
```

`local_overrides.py` is gitignored. Put personal machine settings there rather
than editing tracked files. Note the bare `except`, so an error inside your
overrides file is silently ignored, and the file simply appears not to work.

### `local_test.py`

| Change | Reason |
|---|---|
| `logger` removed from `INSTALLED_APPS` | That app's `ready()` configures structlog with the New Relic processor |
| `DEFAULT_THROTTLE_CLASSES = []` | Otherwise the suite trips the 5-per-minute auth throttle |
| `CELERY_TASK_ALWAYS_EAGER`, `CELERY_TASK_EAGER_PROPAGATES` | Tasks run inline and failures surface |
| `TEST_MODE = True` | A flag application code can check |
| `VERIFICATION_ACTIVE_INTERVAL = 300` | Note nothing reads this name. The real settings are `EMAIL_VERIFICATION_ACTIVE_INTERVAL` and `PHONE_VERIFICATION_ACTIVE_INTERVAL` |

---

## How `.env` is read

`settings/base.py` uses `django-environ`:

```python
ENV = environ.Env(DEBUG=(bool, False))
env_file = os.path.join(BASE_DIR, ".env")
if os.path.isfile(env_file):
    ENV.read_env(env_file)
```

It also **appends a `PWD=` line to your `.env`** if one is missing. That is why
`.env` sometimes changes without you editing it.

Most settings then use plain `os.environ.get`, so they are strings with no type
coercion. `CLOUD_STORAGE_BUCKET_IS_PUBLIC` is the trap: it is the string
`"false"`, which is truthy. Compare explicitly.

`.env` is gitignored. `.env.example` is the checked-in inventory.

---

## Variables

Full annotated list in [`.env.example`](../../.env.example). Grouped summary:

### Core

| Variable | Required | Notes |
|---|---|---|
| `ENV` | no | Selects the settings module. Defaults to development |
| `DJANGO_SETTINGS_MODULE` | yes | `manage.settings`, or a module name directly |
| `SECRET_KEY` | in test and prod | Also the JWT signing key. `base.py` ships an insecure default that `test.py` and `prod.py` deliberately do not use |
| `DEBUG` | no | `development.py` forces `True` regardless |
| `DATABASE_URL` | yes | Parsed by dj-database-url |

### Celery and Redis

`CELERY_BROKER_URL` (default `redis://localhost:6379/0`), `CELERY_RESULT_BACKEND`
(default `django-db`). `REDIS_PORT`, `CELERY_APP`, and `CELERY_LOG_LEVEL` are read
by `bin/celery` only. See [celery.md](celery.md).

### Email

`EMAIL_HOST`, `EMAIL_PORT`, `EMAIL_USE_TLS`, `EMAIL_HOST_USER`,
`EMAIL_HOST_PASSWORD`. Note `base.py` reads `EMAIL_USE_TLS` and `EMAIL_PORT` as
raw strings, while `development.py` re-reads them properly with `ENV.bool` and
`ENV.int`. In production they stay strings, and Django coerces the port.

### SMS

`NETGSM_USER_CODE`, `NETGSM_PASSWORD`, `SMS_HEADER`.

### Cloud storage

`CLOUD_STORAGE_VENDOR` (only `idrive` is implemented),
`CLOUD_STORAGE_BUCKET_NAME`, `CLOUD_STORAGE_PUBLIC_BUCKET_NAME`,
`CLOUD_STORAGE_BUCKET_IS_PUBLIC`, `IDRIVE_ENDPOINT_URL`, `IDRIVE_ACCESS_KEY`,
`IDRIVE_SECRET_ACCESS_KEY`, `IDRIVE_BUCKET_NAME`. `AWS_S3_ACCESS_KEY_ID` and
`AWS_S3_SECRET_ACCESS_KEY` are read into settings but no code path uses them.
See [../apps/cloud-storage.md](../apps/cloud-storage.md).

### Social authentication

`SOCIAL_SECRET`, which is effectively a master password for every socially
created account. `SOCIAL_AUTH_APPLE_KEY_ID`, `SOCIAL_AUTH_APPLE_TEAM_ID`,
`SOCIAL_AUTH_APPLE_PRIVATE_KEY` for Sign in with Apple.

> `GOOGLE_CLIENT_ID` is read by `authy/serializers.py` but **is not defined in
> any settings module**, so Google sign-in raises `AttributeError` at runtime.
> Add `GOOGLE_CLIENT_ID = os.environ.get("GOOGLE_CLIENT_ID")` to `base.py` before
> relying on it. Likewise `DEFAULT_USER_KEY`, read by
> `CustomUserManager.create_user_with_default_password`, is undefined. Nothing
> calls that method today. See [../apps/authy.md](../apps/authy.md) and
> [../apps/user.md](../apps/user.md).

### In-app purchases

`APPLE_BUNDLE_ID`, `APPLE_APP_ID`, `APPLE_IN_APP_SIGNING_KEY`,
`APPLE_DEVELOPER_KEY_ID`, `APPLE_DEVELOPER_ISSUER_ID`,
`APPLE_CONNECT_API_KEY_ID`, `APPLE_CONNECT_API_SIGNING_KEY`, plus the whole
`GOOGLE_PLAY_*` block, which is a service-account JSON split across variables.
The Apple notification verifier also reads `APPLE_ROOT_CA` directly from the
environment. See [../apps/payments-and-subscriptions.md](../apps/payments-and-subscriptions.md).

### Documentation

`SWAGGER_ACCESS_PASSCODE`. See [api-schema.md](api-schema.md).

### Setup script only

`DB_PORT` and `PG_FRESH_INSTALL_PORT`, read by `bin/setup`, not by Django. See
[../getting-started.md](../getting-started.md).

---

## Non-environment constants worth knowing

Hard-coded in `base.py`, and reasonable things to change:

| Setting | Value | Meaning |
|---|---|---|
| `SIMPLE_JWT["ACCESS_TOKEN_LIFETIME"]` | 15 minutes | |
| `SIMPLE_JWT["REFRESH_TOKEN_LIFETIME"]` | 30 days | |
| `DEFAULT_THROTTLE_RATES` | anon 20/min, user 60/min, auth 5/min | |
| `PAGE_SIZE` | 100 | With `?size=` up to `max_page_size` 100 |
| `EMAIL_VERIFICATION_ACTIVE_INTERVAL` | 1500 seconds | 25 minutes, despite the `# a day` comment |
| `PHONE_VERIFICATION_ACTIVE_INTERVAL` | 300 seconds | |
| `MAX_VERIFICATION_ATTEMPTS` | 3 | |
| `LOGO_URL` | a third-party CDN URL | Used in verification emails. Replace it |
| `TRANSLATED_FILE_DIRECTORY` | `translated_file/` | Storage key prefix |
| `USE_TZ` | `False` | Naive datetimes throughout. See [../apps/common.md](../apps/common.md) |
| `TIME_ZONE` | `UTC` | |
| `AUTO_RETRY_WRONG_ENVIRONMENT_REQUEST` | `True` | Apple receipts retry against sandbox or production |
| `API_SCHEMA_CACHE_TIMEOUT` | 3600 in practice | See [api-schema.md](api-schema.md) |

---

## Adding a variable

1. Read it in the right settings module, usually `base.py`.
2. Add it to `.env.example`, marked `[required]` or `[optional]`, with a note on
   what it controls.
3. Add it to the right group above.
4. Mention it in the pull request, so whoever deploys sets it first.

Steps 2 and 3 are not optional. They are in the
[CONTRIBUTING.md](../../CONTRIBUTING.md) change table.

---

## Related

- [deployment.md](deployment.md) for production values.
- [../getting-started.md](../getting-started.md) for local setup.
