# Starting a new project from this template

[Back to docs index](README.md)

Get it running unchanged first, following
[getting-started.md](getting-started.md). Then work through this page.

---

## 1. Rename the project

The name `myapp` appears in scripts, settings, and docstrings. The Django project
package is `manage/`, which is generic and does not need renaming.

Pick a name, then change these. The `bin/` scripts matter most, because they all
derive the virtualenv path from `PROJECT_NAME`.

| File | What to change |
|---|---|
| `bin/setup` | `PROJECT_NAME="myapp"` and `DB_NAME="myapp"` |
| `bin/activate`, `bin/server`, `bin/celery` | `PROJECT_NAME="myapp"` |
| `pyproject.toml` | `name = "my_app"`, plus `authors` and `description` |
| `settings/base.py` | `SPECTACULAR_SETTINGS` `TITLE` and `DESCRIPTION`, `UNFOLD` `SITE_TITLE` and `SITE_HEADER` |
| `settings/development.py` | The `DATABASE_URL` fallback, `postgresql://localhost:5432/myapp` |
| `settings/prod.py` | `CORS_ALLOWED_ORIGINS`, currently `myapp.com` placeholders |
| `settings/test.py` | `ALLOWED_HOSTS`, currently a Heroku placeholder |
| `manage/urls.py`, `wsgi.py`, `asgi.py`, `settings/base.py` | Docstrings saying "myapp project" |

A quick audit of what is left:

```bash
grep -rn "myapp\|MyApp\|my_app" --include="*.py" --include="*.toml" . \
  | grep -v __pycache__ | grep -v staticfiles
```

Test files also contain `myapp` in fixture data. Harmless, rename at leisure.

After renaming, re-run `bin/setup` so the virtualenv and database are created
under the new name.

---

## 2. Replace the secrets

`settings/base.py` ships a working but insecure `SECRET_KEY`, and
`development.py` supplies placeholder credentials for every external service.
None of it is safe outside your machine.

| Replace | Why |
|---|---|
| `SECRET_KEY` | Signs sessions **and** every JWT |
| `SOCIAL_SECRET` | The password given to every socially created user. Effectively a master password |
| `SWAGGER_ACCESS_PASSCODE` | Otherwise the docs gate is `swagger` |
| `settings/logger/*.ini` `license_key` | Real New Relic keys are checked in. Replace them and treat the files as credentials |
| `LOGO_URL` | Points at a third-party CDN image, used in verification emails |

Copy `.env.example` to `.env` and work through it. Everything is marked required
or optional.

---

## 3. Decide which apps to keep

### Keep these

| App | Why |
|---|---|
| `user` | `AUTH_USER_MODEL`. Not removable |
| `authy` | Login, registration, tokens |
| `common` | The response envelope, exception handling, permissions, mixins, middleware. Everything depends on it |
| `logger` | structlog configuration |
| `utils`, `custom_test` | Helpers and test infrastructure |

### Keep if you need them

| App | Drop it if |
|---|---|
| `contact_verification` | You do not verify email or phone. Note registration calls it |
| `communications` | You send no email or SMS. `contact_verification` and password reset both depend on it |
| `cloud_storage` | You store no files. `common.TranslatedFile` depends on it |

### Drop unless you sell in-app purchases

`payment`, `vendor`, and `subscription` are one feature across three apps. They
are the largest part of the codebase and the most specific. If your product does
not sell App Store or Google Play subscriptions, remove all three together.

### The translation models are optional too

`common` bundles `Locale`, `Translation`, and `TranslatedFile` with the core
machinery. If you do not need database-backed content translation, delete those
models, their serializers, views, and URLs, and keep the rest of `common`. Note
`User.locale` is a foreign key to `Locale`, so removing `Locale` means editing
the `User` model.

---

## 4. Removing the payment apps

In order, because of the dependencies:

1. Delete `payment/`, `vendor/`, and `subscription/`.
2. Remove `payment`, `subscription`, and `vendor` from `INSTALLED_APPS` in
   `settings/base.py`.
3. Remove `path("payment/", include("payment.urls"))` from `manage/urls.py`.
4. In `user/models.py`, remove the `subscription` imports and the
   `active_subscription`, `last_or_active_subscription`, and
   `has_active_subscription` members.
5. In `authy/helpers/token_helper.py`, remove `get_token_subscription_for_user`
   and the `subscription` claim from `authenticate_response`.
6. In `custom_test/base_test.py`, remove the `Buyable` import and
   `create_product`, and the `Buyable` line in `create_common_models`.
7. Delete `custom_test/baker_recipes.py`, which is entirely payment recipes.
8. Drop the payment variables from `.env.example`: the `APPLE_*` and
   `GOOGLE_PLAY_*` blocks.
9. Delete `docs/apps/payments-and-subscriptions.md` and its links in
   `docs/README.md` and `CONTRIBUTING.md`.

Then:

```bash
python manage.py makemigrations
bin/run-tests
```

The meta-tests in `custom_test/` will tell you if you missed a reference.

---

## 5. Add your own app

```bash
python manage.py startapp widget
```

Then follow the shape of an existing app rather than Django's default:

```
widget/
  models.py       your models
  serializers.py  one per action where they differ
  services.py     business logic, static methods
  views.py        thin, using LoggingMixin or OwnershipMixin
  urls.py         with app_name = "widget"
  test/
    test_integration.py
```

**Register it.** Add `"widget"` to `INSTALLED_APPS` and
`path("widget/", include("widget.urls"))` to `manage/urls.py`.

**Set `app_name`.** Every app in this project namespaces its URLs, so tests
reverse `widget:widget-viewset`. Omitting it breaks that convention.

**Follow the four conventions**, or the meta-tests will fail your build:

| Convention | Document |
|---|---|
| Return `view_response.rest_response`, mix in `LoggingMixin` | [conventions/views.md](conventions/views.md) |
| Static-method services raising `CustomException` | [conventions/services.md](conventions/services.md) |
| `ShortCircuitOr(ActionAwareModelPermissions, IsOwner)` plus `OwnershipMixin` | [conventions/permissions.md](conventions/permissions.md) |
| `gettext_lazy` on every user-facing string | [conventions/i18n.md](conventions/i18n.md) |

**Add `docs/apps/widget.md`** and link it from
[docs/README.md](README.md). See the table in
[CONTRIBUTING.md](../CONTRIBUTING.md).

A model that belongs to a user should have a `user_id` field, which is what
`OwnershipMixin` and `IsOwner` look for. `User` itself is special-cased precisely
because it does not have one.

---

## 6. Things to fix before production

Known gaps in the template, documented where they live:

| Gap | Where |
|---|---|
| `GOOGLE_CLIENT_ID` is used but never defined, so Google sign-in 500s | [apps/authy.md](apps/authy.md) |
| Password reset mails a six digit password in plain text, with no token or expiry, and reveals whether an account exists | [apps/authy.md](apps/authy.md) |
| `settings/logger/*.ini` contain real-looking New Relic license keys | [operations/deployment.md](operations/deployment.md) |
| No `settings/logger/staging.ini`, so `ENV=staging` breaks gunicorn | [operations/deployment.md](operations/deployment.md) |
| `settings/prod.py` has an empty `ALLOWED_HOSTS` and placeholder CORS origins | [operations/deployment.md](operations/deployment.md) |
| SMS sending is synchronous despite being called `send_async` | [apps/communications.md](apps/communications.md) |
| `common/models.py` builds a storage client at import time, so bad storage config breaks boot | [apps/common.md](apps/common.md) |
| The default `Locale` is Turkish while `LANGUAGE_CODE` is `en-us` | [apps/common.md](apps/common.md) |
| `CustomUserManager.create_user_with_default_password` references an undefined setting | [apps/user.md](apps/user.md) |
| Request bodies are logged in full, including credentials | [conventions/logging-and-context.md](conventions/logging-and-context.md) |

None of these block development. All of them matter before you take payments or
real users.

---

## 7. Housekeeping

- Point `.github/workflows/ci.yml` at your own branch names if you do not use
  `develop` and `master`.
- Rewrite this repository's `README.md` to describe your product.
- Keep `CLAUDE.md` pointing at `docs/`, and update the docs rather than that
  file. See [CONTRIBUTING.md](../CONTRIBUTING.md).
- Decide whether to keep Turkish. If not, drop `tr` from `LANGUAGES` and delete
  `locale/tr/`. See [conventions/i18n.md](conventions/i18n.md).

---

## Related

- [architecture.md](architecture.md) for the patterns your apps should follow.
- [operations/settings-and-env.md](operations/settings-and-env.md) for every variable.
- [operations/deployment.md](operations/deployment.md) for the deploy checklist.
