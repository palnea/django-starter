# Django Starter

A Django 5.2 + Django REST Framework backend template for mobile-first products.
It ships with the parts most apps end up needing anyway: JWT and social
authentication, email/SMS contact verification, App Store and Google Play in-app
purchases with subscription state tracking, a translation/locale layer, cloud
file storage, Celery, and a structured logging and error-response system that
every endpoint follows.

It is a *starting point*, not a framework. Everything here is ordinary Django
you are meant to read, change, and delete.

---

## Quickstart

Requires macOS or Debian/Ubuntu, and Homebrew or `apt`. Everything else
(pyenv, Python 3.14.3, PostgreSQL, Poetry, the virtualenv, the database)
is installed and configured by the setup script.

```bash
git clone <your-fork> && cd django-starter
bin/setup                 # one-time: installs and configures everything
source bin/activate       # enter the virtualenv
bin/server                # http://127.0.0.1:8000/
```

Then:

```bash
bin/run-tests             # full suite
bin/lint --fix            # black + ruff
bin/celery                # Redis + Celery worker + beat, all in the foreground
```

If `bin/setup` fails, or you would rather set things up by hand, read
[docs/getting-started.md](docs/getting-started.md). It covers what the script
does, its PostgreSQL port behaviour, and the manual path.

---

## Documentation

Start at **[docs/README.md](docs/README.md)**, which lays out two reading tracks:
joining an existing codebase built on this, or starting a new project from it.

| | |
|---|---|
| [Getting started](docs/getting-started.md) | Setup, the `bin/` scripts, troubleshooting |
| [Architecture](docs/architecture.md) | The request lifecycle, layer by layer |
| [Starting a new project](docs/starting-a-new-project.md) | Renaming, what to keep, what to delete |
| [Conventions](docs/conventions/) | Views, services, serializers, errors, permissions, i18n, logging |
| [Testing](docs/testing.md) | Base classes, helpers, fixtures, the meta-tests |
| [Apps](docs/apps/) | What each app owns, and how its flows actually run |
| [Operations](docs/operations/) | Settings and env vars, deployment, Celery, CI, API schema |
| [Contributing](CONTRIBUTING.md) | Branching, PR checklist, which doc to update when |

---

## Stack

| | |
|---|---|
| Python | 3.14.3 (pinned in `.python-version` / `runtime.txt`) |
| Framework | Django 5.2, Django REST Framework 3.16 |
| Database | PostgreSQL, configured via `DATABASE_URL` (dj-database-url) |
| Auth | `djangorestframework-simplejwt` behind a custom authentication class |
| Async | Celery 5.5 on Redis, with `django-celery-results` and `django-celery-beat` |
| API docs | drf-spectacular, serving Swagger UI and ReDoc |
| Admin | django-unfold |
| Storage | IDrive e2 / S3-compatible, via boto3 |
| Logging | structlog, shipped to New Relic in production |
| i18n | English and Turkish, `gettext_lazy` throughout |
| Tooling | Poetry, Black, Ruff, model-bakery |

---

## Endpoint map

| Prefix | App | What lives there |
|---|---|---|
| `/auth/` | `authy` | `login`, `register`, `token/refresh/`, `reset_password`, `update_password/`, `google/`, `facebook/`, `apple/` |
| `/user/` | `user` | List, retrieve, partial update, soft delete |
| `/contact-verification/` | `contact_verification` | `send-the-code/`, `verify-the-code/`, `verify-email/`, `verify-phone/` |
| `/payment/` | `payment` | `verify_receipt/`, `buyable/`, and the `appstore/`, `googleplay/` store webhooks |
| `/common/` | `common` | `translation/`, `translated_file/`, `locale/`, each with `bulk_create/` where it applies |
| `/admin/` | | django-unfold admin, email or username plus password |
| `/health` | | Plain `ok`, served by middleware before Django routing |
| `/swagger/`, `/redoc/`, `/api/schema/` | | drf-spectacular, gated by `SWAGGER_ACCESS_PASSCODE` |

---

## Project layout

```
manage/           Django entrypoints: settings, urls, wsgi, asgi, celery
settings/         base.py plus one module per environment; __init__.py picks by $ENV
authy/            Authentication: JWT, password flows, social providers
user/             The custom User model (AUTH_USER_MODEL, UUID primary key)
common/           Cross-cutting machinery, plus the Locale/Translation/TranslatedFile layer
contact_verification/   Email and phone verification codes
payment/          Buyables, purchases, receipt verification
vendor/           Store-side clients, webhook verifiers, notification handlers
subscription/     UserSubscription state and its change history
communications/   Email and SMS clients and services
cloud_storage/    S3-compatible storage client
logger/           structlog processors and New Relic shipping
utils/            Shared helpers with no Django app of their own
custom_test/      Test base classes, mixins, recipes, and repo-wide meta-tests
locale/           en and tr translation catalogues
bin/              Developer scripts. Start here, not with raw manage.py
```

---

## A note on migrations

Migration files are **not committed** to this repository. Generate them locally
before running anything:

```bash
python manage.py makemigrations
```

CI enforces this with `makemigrations --check --dry-run`. See
[CONTRIBUTING.md](CONTRIBUTING.md) for the reasoning.
