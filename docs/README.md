# Documentation

Two ways in, depending on why you are here.

---

## Track A: you are joining a codebase built on this

Read in order. Each one assumes the previous.

1. **[getting-started.md](getting-started.md)** Get it running on your machine.
2. **[architecture.md](architecture.md)** The request lifecycle end to end. This
   is the single most useful document here. Everything else is detail hanging
   off it.
3. **[conventions/](conventions/)** How code is written here. The view and
   service patterns are not optional style preferences, they are load bearing:
   the response envelope, the logging, and the error contract all depend on
   every endpoint following them.
4. **[testing.md](testing.md)** Base classes, helpers, and the repo-wide
   meta-tests that will fail your PR if you skip a convention.
5. **[apps/](apps/)** The specific app you are about to touch. Read only that one.

Then write code. Come back to [operations/](operations/) when you need to
deploy, add an environment variable, or understand a CI failure.

---

## Track B: you are starting a new project from this template

1. **[getting-started.md](getting-started.md)** Get it running first, unchanged.
2. **[starting-a-new-project.md](starting-a-new-project.md)** Rename the
   project, decide which apps to keep, delete the rest.
3. **[architecture.md](architecture.md)** and **[conventions/](conventions/)**
   The patterns your own apps should follow.
4. **[operations/settings-and-env.md](operations/settings-and-env.md)** Wire up
   your own credentials and environments.

---

## Everything, by area

### Cross-cutting

| Document | Covers |
|---|---|
| [getting-started.md](getting-started.md) | `bin/setup`, the `bin/` scripts, PostgreSQL behaviour, troubleshooting |
| [architecture.md](architecture.md) | Middleware, authentication, permissions, views, services, models, the response envelope, exception handling |
| [starting-a-new-project.md](starting-a-new-project.md) | Renaming `myapp`, core vs optional apps, adding your own app |
| [testing.md](testing.md) | `CustomAPITestCase`, helpers, `model_bakery`, `CRUDPermissionTestsMixin`, meta-tests |

### Conventions

| Document | Covers |
|---|---|
| [conventions/views.md](conventions/views.md) | `ViewResponse`, `log_view_response`, `MessageCode`, the success envelope |
| [conventions/services.md](conventions/services.md) | Static-method services, where business logic belongs |
| [conventions/serializers.md](conventions/serializers.md) | Action-specific serializers, validation vs business logic |
| [conventions/errors.md](conventions/errors.md) | `CustomException`, the RFC 7807 error envelope, error code enums |
| [conventions/permissions.md](conventions/permissions.md) | `ShortCircuitOr`, `ActionAwareModelPermissions`, `IsOwner`, ownership mixins |
| [conventions/i18n.md](conventions/i18n.md) | `gettext_lazy`, message catalogues, translating exception handlers |
| [conventions/logging-and-context.md](conventions/logging-and-context.md) | structlog, the global context middleware, request correlation, New Relic |

### Apps

| Document | Covers |
|---|---|
| [apps/authy.md](apps/authy.md) | Register, login, refresh, password reset, the three social providers |
| [apps/user.md](apps/user.md) | The unified `User` model, UUID keys, soft delete |
| [apps/contact-verification.md](apps/contact-verification.md) | Email and phone verification code lifecycle |
| [apps/payments-and-subscriptions.md](apps/payments-and-subscriptions.md) | `payment` + `vendor` + `subscription`: purchases, receipt verification, store webhooks, subscription state |
| [apps/common.md](apps/common.md) | Locale, Translation, TranslatedFile, pagination, throttling, soft-delete managers |
| [apps/communications.md](apps/communications.md) | Email and SMS delivery, sync and async |
| [apps/cloud-storage.md](apps/cloud-storage.md) | S3-compatible storage, public vs private buckets |

### Operations

| Document | Covers |
|---|---|
| [operations/settings-and-env.md](operations/settings-and-env.md) | The settings modules, how `$ENV` selects one, every environment variable |
| [operations/deployment.md](operations/deployment.md) | `Procfile`, gunicorn, the release phase, static files |
| [operations/celery.md](operations/celery.md) | Broker, worker, beat, the `--preload` caveat |
| [operations/ci.md](operations/ci.md) | What `ci.yml` runs and how to reproduce it locally |
| [operations/api-schema.md](operations/api-schema.md) | drf-spectacular, Swagger, ReDoc, the passcode gate |

---

## Keeping these current

These documents are the source of truth. `CLAUDE.md` at the repository root is
deliberately thin and points here, so there is only one place to update.

[CONTRIBUTING.md](../CONTRIBUTING.md) carries a table mapping the kind of change
you are making to the document that has to change with it. Check it before
opening a PR.
