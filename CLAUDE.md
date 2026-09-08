# CLAUDE.md

Guidance for Claude Code (claude.ai/code) working in this repository.

**This file is deliberately thin.** The full documentation lives in
[docs/](docs/) and is the source of truth. Duplicating it here is what caused
this file to drift out of date before. Read the linked document rather than
relying on a summary.

Start with [docs/architecture.md](docs/architecture.md).

---

## Orientation

| Question | Document |
|---|---|
| How do I run this? | [docs/getting-started.md](docs/getting-started.md) |
| How does a request flow through the code? | [docs/architecture.md](docs/architecture.md) |
| How do I write a view, service, or serializer? | [docs/conventions/](docs/conventions/) |
| How do I return an error? | [docs/conventions/errors.md](docs/conventions/errors.md) |
| How do permissions work? | [docs/conventions/permissions.md](docs/conventions/permissions.md) |
| How do I write tests? | [docs/testing.md](docs/testing.md) |
| How does app X work? | [docs/apps/](docs/apps/) |
| How is this configured or deployed? | [docs/operations/](docs/operations/) |
| What is the PR workflow? | [CONTRIBUTING.md](CONTRIBUTING.md) |

---

## Commands

```bash
bin/setup            # full environment setup, idempotent
source bin/activate  # enter the virtualenv
bin/server           # development server
bin/server --prod    # DEBUG=False, to catch static file problems
bin/celery           # Redis + worker + beat
bin/lint --fix       # black + ruff
bin/run-tests        # full suite, accepts paths and flags
```

Always generate migrations before running tests:

```bash
python manage.py makemigrations
bin/run-tests
```

Tests always use `--settings=settings.local_test`. `bin/run-tests` applies it for
you.

---

## Rules that are easy to get wrong

These are the ones where a plausible-looking change breaks something. Each links
to the document that explains why.

1. **Views return `view_response.rest_response`**, never a raw DRF `Response`.
   The rest of the pipeline keys on it.
   [views.md](docs/conventions/views.md)

2. **Never call `log_view_response()` by hand.** `LoggingMixin`, included in
   `OwnershipMixin`, calls it automatically in `finalize_response`. There is not
   one manual call left in the codebase, and adding one produces duplicate log
   lines. *An earlier version of this file instructed the opposite. It was
   wrong.* [views.md](docs/conventions/views.md)

3. **Services are `@staticmethod`, raise `CustomException`, and never log.**
   Decorator order is `@staticmethod` then `@transaction.atomic`.
   [services.md](docs/conventions/services.md)

4. **Never build an error response by hand.** Raise `CustomException` and let
   the global handler render it. Never pass `instance=`, which the handler
   derives from the request path.
   [errors.md](docs/conventions/errors.md)

5. **Permissions, never roles.** No `if user.role == ...`. Use
   `ShortCircuitOr(ActionAwareModelPermissions, IsOwner)` and `OwnershipMixin`.
   [permissions.md](docs/conventions/permissions.md)

6. **`GlobalContext` is only legal in views, permissions, middleware, and
   `common/response`.** A meta-test fails the build otherwise. Services, models,
   tasks, and serializers take explicit parameters.
   [logging-and-context.md](docs/conventions/logging-and-context.md)

7. **Wrap every user-facing string in `gettext_lazy as _`.** The exception
   handler mapper is the one documented exception, and it needs a manual
   translation marker instead. A meta-test enforces both.
   [i18n.md](docs/conventions/i18n.md)

8. **Assert against `response.data.get("response_body")`.** Successful responses
   are wrapped in an envelope.
   [testing.md](docs/testing.md)

9. **Never commit migration files.** Generate them locally. CI checks with
   `makemigrations --check --dry-run`.
   [CONTRIBUTING.md](CONTRIBUTING.md)

10. **Renaming an enum member is a breaking API change.** `ErrorCode`,
    `FieldErrorCode`, `GeneralErrorCode`, and `MessageCode` all serialize their
    member names to clients.
    [errors.md](docs/conventions/errors.md)

---

## When you change something

Documentation is part of the change. [CONTRIBUTING.md](CONTRIBUTING.md) carries
a table mapping each kind of change to the document that must change with it.

New environment variables go in `.env.example` **and**
[docs/operations/settings-and-env.md](docs/operations/settings-and-env.md).

---

## Repository shape

```
manage/     settings, urls, wsgi, asgi, celery
settings/   base.py plus one module per environment. __init__.py picks by $ENV
authy/      authentication: JWT, password flows, social providers
user/       the custom User model (AUTH_USER_MODEL, UUID primary key)
common/     response envelope, exception handling, permissions, mixins,
            middleware, plus the Locale/Translation/TranslatedFile layer
contact_verification/   email and phone verification codes
payment/ vendor/ subscription/   in-app purchases and subscription state
communications/  email and SMS       cloud_storage/  S3-compatible storage
logger/     structlog config and New Relic shipping
utils/      helpers with no app of their own
custom_test/  test base classes, mixins, recipes, repo-wide meta-tests
bin/        developer scripts. Prefer these over raw manage.py
```

Note that `communications`, `cloud_storage`, and `utils` are plain packages, not
installed Django apps.
