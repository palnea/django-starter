# Contributing

Start with [docs/README.md](docs/README.md) if you have not already. This file
covers workflow, not architecture.

---

## Before you start

```bash
bin/setup            # once
source bin/activate  # each new shell
```

Branch off `master`. CI runs on pull requests targeting `develop` and `master`.

---

## The loop

```bash
python manage.py makemigrations   # models changed, or you just pulled
bin/lint --fix                    # black + ruff, writes
bin/run-tests                     # full suite
```

All three must be clean before you open a pull request. The pre-commit hook that
`bin/setup` installs runs `bin/lint` and `bin/check-translations` for you and
refuses the commit if either fails.

---

## Migrations are never committed

This repository does not track migration files. Generate them locally:

```bash
python manage.py makemigrations
```

CI enforces it with `makemigrations --check --dry-run`, which fails when your
committed models would produce a migration nobody has. So if that step fails,
the fix is almost always that a model change went in without the corresponding
field or option being complete.

Do not add migration files to a commit. Do not add them to `.gitignore`
exceptions either. If this convention needs to change, that is a discussion, not
a pull request.

---

## Style

| Tool | Command | Enforced by |
|---|---|---|
| Black | `bin/lint --fix` | CI, pre-commit |
| Ruff | `bin/lint --fix` | CI, pre-commit |

`bin/lint` with no arguments checks without writing. Configuration lives in
`pyproject.toml`.

---

## Things CI will catch

Beyond lint and the feature tests, four repo-wide meta-tests fail builds:

| Failure | Cause | Fix |
|---|---|---|
| `test_check_permissions` | A viewset's permission configuration is incoherent, or a custom action permission does not exist | [docs/conventions/permissions.md](docs/conventions/permissions.md) |
| `test_check_global_context_usage` | `GlobalContext` used outside views, permissions, middleware, or `common/response` | Pass the value in as a parameter. [docs/conventions/logging-and-context.md](docs/conventions/logging-and-context.md) |
| `test_exception_translations` | A handler string is unmarked, untranslated, or an orphaned marker was left behind | [docs/conventions/i18n.md](docs/conventions/i18n.md) |
| `test_structured_error_responses` | The error envelope changed shape | [docs/conventions/errors.md](docs/conventions/errors.md) |

These exist to keep the API uniform. If one blocks you, the answer is almost
never to weaken the test.

---

## Which document to update

Documentation is part of the change, not a follow-up. `docs/` is the source of
truth, and `CLAUDE.md` deliberately points at it rather than repeating it.

| If you change | Update |
|---|---|
| A view pattern, the success envelope, `MessageCode` | [docs/conventions/views.md](docs/conventions/views.md) |
| A service pattern, the layer boundaries | [docs/conventions/services.md](docs/conventions/services.md) |
| Serializer selection or validation conventions | [docs/conventions/serializers.md](docs/conventions/serializers.md) |
| `CustomException`, the error envelope, any error code enum | [docs/conventions/errors.md](docs/conventions/errors.md) |
| A permission class, a mixin, the ownership rules | [docs/conventions/permissions.md](docs/conventions/permissions.md) |
| An exception handler string, a language, translation flow | [docs/conventions/i18n.md](docs/conventions/i18n.md) |
| structlog, the global context, correlation IDs, New Relic | [docs/conventions/logging-and-context.md](docs/conventions/logging-and-context.md) |
| Middleware order, the request lifecycle, the settings tree | [docs/architecture.md](docs/architecture.md) |
| A test base class, helper, mixin, or meta-test | [docs/testing.md](docs/testing.md) |
| Anything inside one app: models, endpoints, flows | the matching file in [docs/apps/](docs/apps/) |
| **A new environment variable** | `.env.example` **and** [docs/operations/settings-and-env.md](docs/operations/settings-and-env.md) |
| A `bin/` script, or setup behaviour | [docs/getting-started.md](docs/getting-started.md) |
| `Procfile`, gunicorn, the release phase, static files | [docs/operations/deployment.md](docs/operations/deployment.md) |
| Celery config, a worker, a schedule | [docs/operations/celery.md](docs/operations/celery.md) |
| `ci.yml` | [docs/operations/ci.md](docs/operations/ci.md) |
| drf-spectacular settings, the docs passcode | [docs/operations/api-schema.md](docs/operations/api-schema.md) |
| Which apps are core versus optional | [docs/starting-a-new-project.md](docs/starting-a-new-project.md) |

Adding a new app means adding a `docs/apps/<app>.md` and linking it from
[docs/README.md](docs/README.md).

### Environment variables deserve their own line

`.env.example` is the checked-in inventory of every variable the project reads.
Adding a variable without adding it there means the next person to set up the
project finds out at runtime. Mark it `[required]` or `[optional]` and say what
it controls.

---

## Pull requests

- One concern per pull request.
- Say what changed and why. The what is visible in the diff, the why is not.
- Note any new environment variable explicitly, so whoever deploys knows to set
  it before the release phase runs.
- If you touched the error envelope, the response envelope, or a permission
  class, say so prominently. Those are client-facing contracts.

### Breaking changes to watch for

These look like refactors and are not:

- Renaming a member of `ErrorCode`, `FieldErrorCode`, `GeneralErrorCode`, or
  `MessageCode`. The member name is serialized, so clients switch on it.
- Widening a serializer's `fields`, which can expose or permit writes to
  something previously protected.
- Changing a permission class from 403 to 404 behaviour, or the reverse.
- Changing the shape of `response_body` for an existing endpoint.

---

## Conventions in short

- Views return `view_response.rest_response`, never a raw `Response`.
- Views never call `log_view_response()`. `LoggingMixin` does it.
- Services are static methods that raise `CustomException` and never log.
- Every user-facing string is wrapped in `gettext_lazy as _`.
- Permissions, never roles.
- Assert against `response.data.get("response_body")`.

Each of these has a document behind it. Follow the links above.
