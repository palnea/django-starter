# Deployment

[Back to docs index](../README.md)

The project ships with a `Procfile`, so it deploys to Heroku or anything that
reads one. Nothing here is Heroku-specific beyond that file.

---

## Processes

```
web:     gunicorn -c gunicorn.conf.py -w 3 manage.wsgi:application --timeout 15 --preload
worker:  celery -A manage worker -l INFO
beat:    celery -A manage beat -l INFO --scheduler django_celery_beat.schedulers:DatabaseScheduler
release: ./bin/release
```

| Process | Scale to |
|---|---|
| `web` | as many as you need |
| `worker` | as many as you need |
| `beat` | **exactly one** |
| `release` | runs once per deploy, before the new release goes live |

Two beat processes fire every periodic task twice. See [celery.md](celery.md).

### About `--preload`

The `Procfile` comment explains it: application code is loaded before workers
fork, which speeds up start and avoids scheduled jobs being initialised once per
worker. If you remove it, you must handle repeated scheduler initialisation
yourself.

It also means **code is imported once, before forking**. Anything evaluated at
import time is shared by every worker. `common/models.py` builds a cloud storage
client at import to compute a field default, so a broken storage configuration
fails the whole boot rather than one request. See
[../apps/common.md](../apps/common.md).

### The 15 second timeout

`--timeout 15` kills a worker whose request takes longer. Two known paths can
approach it: an SMS send, which is synchronous, and a store receipt verification,
which calls Apple or Google. If you see worker timeouts, look there first.

---

## The release phase

```bash
#!/bin/bash
python manage.py collectstatic --noinput
python manage.py migrate
```

Runs before the new release receives traffic. Note it does **not** run
`makemigrations`, by design: migrations are generated in development and applied
here.

It also does not run `compilemessages`. `bin/post_compile` exists for build-time
hooks. If your platform does not compile messages during the build, translations
will fall back to the untranslated strings, so make sure `compilemessages` runs
somewhere in your build.

---

## Static files

`staticfiles/` is **not committed**. It is build output, and every environment
builds it: CI does, the release phase does, and `bin/setup` does locally.

```python
STATIC_ROOT = os.path.join(BASE_DIR, "staticfiles")
STORAGES = {
    "staticfiles": {"BACKEND": "whitenoise.storage.CompressedManifestStaticFilesStorage"},
}
```

`WhiteNoiseMiddleware` sits high in the stack and serves the collected files, so
no separate web server or CDN is required.

`CompressedManifestStaticFilesStorage` means every `{% static %}` is resolved
through `staticfiles.json`, and a missing entry raises `ValueError` rather than
silently serving a 404. That is stricter than development, where the finders
serve files straight from disk.

Catch it before deploying:

```bash
bin/server --prod
```

which collects static and then serves with `DEBUG=False` under
`settings/local_prod.py`. See [../getting-started.md](../getting-started.md).

---

## Environment selection

`settings/__init__.py` picks a module from `$ENV`. For production, set:

```
ENV=production
DJANGO_SETTINGS_MODULE=manage.settings
```

`manage.settings` is the indirection that honours `$ENV`. Setting
`DJANGO_SETTINGS_MODULE=settings.prod` directly also works and ignores `$ENV`.

Then fill in the rest from `.env.example`. At minimum, production needs
`SECRET_KEY`, `DATABASE_URL`, `CELERY_BROKER_URL`, and
`SWAGGER_ACCESS_PASSCODE`. See [settings-and-env.md](settings-and-env.md).

### Before you ship, edit `settings/prod.py`

It is a template, and two values are placeholders:

```python
ALLOWED_HOSTS += []                          # empty. Add your domain
CORS_ALLOWED_ORIGINS = [
    "https://www.myapp.com",                 # placeholder
    "https://myapp-admin.vercel.app",        # placeholder
]
```

An empty `ALLOWED_HOSTS` with `DEBUG=False` rejects every request with a 400.

---

## Monitoring

New Relic, initialised per gunicorn worker:

```python
# gunicorn.conf.py
def post_fork(server, worker):
    environment = get_environment()
    newrelic.agent.initialize("settings/logger/" + environment + ".ini")
    newrelic.agent.register_application(timeout=10.0)
```

Two things to do before deploying:

- **Replace the license keys.** `settings/logger/development.ini`,
  `production.ini`, and `test.ini` each contain a `license_key` in plain text.
  Treat those files as credentials and put your own account's key in.
- **There is no `staging.ini`.** `get_environment()` can return `staging`, and
  `post_fork` would then try to open `settings/logger/staging.ini` and fail. Add
  the file before using `ENV=staging`.

Application logs ship separately, through the structlog processor in the
`logger` app, posting to `https://log-api.eu.newrelic.com/log/v1`. Note the
**EU** endpoint, which will not accept a US-region key. See
[../conventions/logging-and-context.md](../conventions/logging-and-context.md).

---

## Health checks

`/health` returns the plain text `ok`, served by `HealthCheckMiddleware` before
routing, authentication, or any database access. So it answers even when the
database is down, which makes it a liveness check and **not** a readiness check.
If your platform needs readiness, add an endpoint that actually touches the
database.

---

## Deploy checklist

- [ ] `ENV` and `DJANGO_SETTINGS_MODULE` set
- [ ] `SECRET_KEY` set to a real secret, not the `base.py` default
- [ ] `DATABASE_URL` set
- [ ] `ALLOWED_HOSTS` in `settings/prod.py` includes your domain
- [ ] `CORS_ALLOWED_ORIGINS` updated from the placeholders
- [ ] `SWAGGER_ACCESS_PASSCODE` set to a real value
- [ ] `SOCIAL_SECRET` set to a real secret, if you use social login
- [ ] New Relic `.ini` files carry your own license key
- [ ] `compilemessages` runs somewhere in the build
- [ ] `beat` scaled to exactly one process
- [ ] Store webhooks pointed at `/payment/{appstore,googleplay}/webhook/`, if you kept those apps

---

## Related

- [settings-and-env.md](settings-and-env.md) for every variable.
- [celery.md](celery.md) for the worker and beat.
- [ci.md](ci.md) for what runs before a merge.
