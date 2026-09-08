# Logging and request context

[Back to docs index](../README.md)

Logging is structured JSON via structlog. Every request carries a correlation ID
and a request-scoped context object that infrastructure code reads instead of
threading a `request` argument through every call.

Source: `common/middlewares/global_context_middleware.py`, `logger/apps.py`,
`logger/logging_processors.py`, `common/response/view_response.py`.

---

## Getting a logger

Always at module top, always named after the module:

```python
from structlog import get_logger

log = get_logger(__name__)
```

---

## Where logging happens

You almost never call the logger yourself. Three places do it for you:

| Where | What it logs |
|---|---|
| `LoggingMixin.finalize_response` | Every view response backed by a `ViewResponse`. |
| `custom_exception_handler` | Every error it renders, at `warning` for 4xx and `error` for 5xx. |
| `GlobalContextMiddleware` | Binds `request_id` onto every line produced during the request. |

So a normal view logs once, an erroring view logs once, and neither needs a
`log.*` call. Adding one produces a duplicate.

Legitimate reasons to log directly:

- Store webhook handlers, which run outside the view logging path.
  `payment/views.py` does this deliberately.
- Background Celery work.
- Genuinely notable events inside long-running operations.

Do **not** log in services. See [services.md](services.md).

---

## What a view log line contains

`log_view_response()` emits, for every request:

`user_id`, `view_name`, `method`, `request_body`, `request_path`,
`request_method`, `is_successful`, plus `exception_name`, `exception_detail`, and
`exception_stack_trace` when there was an exception. `request_id` is merged in
from contextvars.

The level is derived, never passed:

| Response | Level |
|---|---|
| Successful, or 3xx | `info` |
| 4xx | `warning` |
| 5xx and anything else | `error` |

Note that `request_body` is logged in full. Anything secret in a request body
lands in your logs. Keep that in mind when adding endpoints that accept
credentials or tokens.

---

## Correlation IDs

`GlobalContextMiddleware` gives every request an ID:

1. Reads `X-Request-ID` from the incoming request, or generates a UUID4.
2. Stores it in a `contextvars.ContextVar`.
3. Binds it to structlog contextvars, so every line logged during that request
   carries `request_id`.
4. Sets `X-Request-ID` on the response.
5. Clears the contextvars afterwards, so nothing leaks between requests.

Read it anywhere:

```python
from common.middlewares.global_context_middleware import get_request_id

request_id = get_request_id()   # "" outside a request
```

Because clients can supply `X-Request-ID`, a mobile app can pass its own trace ID
and have it appear on every server log line for that call.

---

## The global context

`GlobalContext` is a request-scoped object holding things that would otherwise
have to be passed down through every layer.

```python
from common.middlewares.global_context_middleware import GlobalContextMiddleware

ctx = GlobalContextMiddleware.get_global_context()
ctx.user_id
ctx.language_code
```

| Property | Source |
|---|---|
| `user_id` | The `user_id` claim on the JWT |
| `user` | `request.user`, but only when it is a `User` instance |
| `account` | `request.user`, whatever it is |
| `user_groups` | The `groups` claim |
| `user_specific_permissions` | The `permissions` claim |
| `user_all_permissions` | The user's full permission set, cached for one hour under `user_{id}_perms` |
| `user_timezone` | The `User-Timezone` request header, falling back to UTC |
| `language_code` | `Accept-Language`, then a `language` or `locale_code` query parameter, then the JWT's `locale_code` claim, then `en` |

Every property is a `cached_property`, so each is computed at most once per
request.

### The permission cache

`user_all_permissions` caches for 3600 seconds under `user_{user_id}_perms`. That
makes permission checks cheap, and it means **a permission change can take up to
an hour to take effect**. If you grant or revoke permissions programmatically,
invalidate the key:

```python
from django.core.cache import cache
cache.delete(f"user_{user.id}_perms")
```

### It is safe outside a request

`get_global_context()` returns a `NullGlobalContext` when no middleware has run,
with `user_id = None`, `language_code = "en"`, and an empty permission set. So
logging and permission code does not crash in a shell, a Celery task, or a test.

It also means a permission check in a Celery task silently sees no permissions.
Do not rely on the global context in background work. Pass what you need
explicitly.

### It works under ASGI

The context lives in `contextvars`, not thread locals, so it is correct under
both threaded WSGI and async ASGI workers.

---

## Setting the context in tests

`CustomIntegrationTestCase.set_global_context(user)` builds a context for a user
so that code reading the global context behaves as it would in a request.

`custom_test/test_check_global_context_usage.py` is a repo-wide meta-test over
how the global context is used. See [../testing.md](../testing.md).

---

## The processor pipeline

Configured in `logger/apps.py`, in the app's `ready()`:

```python
structlog.configure(
    processors=[
        structlog.contextvars.merge_contextvars,   # pulls in request_id
        send_to_newrelic,                          # ships to New Relic
        structlog.processors.JSONRenderer(),       # renders JSON to stdout
    ],
)
```

Two consequences worth knowing:

- **structlog is configured by an installed app.** `settings/local_test.py`
  removes `logger` from `INSTALLED_APPS`, so tests run without the New Relic
  processor. That is deliberate. Tests should not ship logs.
- **The order matters.** `merge_contextvars` runs first so `request_id` is
  present, and `JSONRenderer` runs last.

---

## New Relic

`send_to_newrelic` posts each event to `https://log-api.eu.newrelic.com/log/v1`
on a ten-worker thread pool, so logging never blocks the request. If the New
Relic agent is not initialised, it prints the payload when `DEBUG` is true and
otherwise does nothing, which is why local development produces no traffic.

The agent itself is started per gunicorn worker:

```python
# gunicorn.conf.py
def post_fork(server, worker):
    environment = get_environment()
    newrelic.agent.initialize("settings/logger/" + environment + ".ini")
    newrelic.agent.register_application(timeout=10.0)
```

Two things to watch:

- Config files exist for `development`, `production`, and `test`. There is **no
  `staging.ini`**, so running gunicorn with `ENV=staging` will fail in
  `post_fork`. Add the file before using that environment.
- `settings/logger/*.ini` carry a `license_key` in plain text. Replace them with
  your own account's values, and treat those files as credentials.

See [../operations/deployment.md](../operations/deployment.md).

---

## Rules

- `log = get_logger(__name__)` at module top.
- Do not log in services.
- Do not call `log_view_response()` by hand. `LoggingMixin` does it.
- Log messages stay in English. Never wrap them in `gettext`. See
  [i18n.md](i18n.md).
- Pass structured key-value pairs, not interpolated strings:
  `log.info("Purchase verified", purchase_id=p.id)`, not
  `log.info(f"Purchase {p.id} verified")`.
- Do not rely on the global context in Celery tasks.

---

## Related

- [views.md](views.md) for `LoggingMixin`.
- [errors.md](errors.md) for error logging.
- [permissions.md](permissions.md) for the permission set the context caches.
