# Celery

[Back to docs index](../README.md)

Celery 5.5 on Redis, with results in PostgreSQL and schedules in PostgreSQL.

---

## Running it locally

```bash
bin/celery
```

One command starts Redis if it is not already up, then a worker, then beat, all
in the foreground. Ctrl-C stops everything and shuts down Redis if the script
started it.

| Variable | Default | Effect |
|---|---|---|
| `REDIS_PORT` | `6379` | Which port to use or start Redis on |
| `CELERY_APP` | `manage` | The app name passed to `-A` |
| `CELERY_LOG_LEVEL` | `info` | Worker and beat log level |
| `DJANGO_SETTINGS_MODULE` | `settings.development` | Settings for both processes |

On macOS the script passes `--pool=solo`, because the default prefork pool hits
fork-safety crashes on Darwin. On Linux it uses `--concurrency=2`. If you run
Celery by hand on a Mac, pass `--pool=solo` yourself.

The script also exports `CELERY_BROKER_URL` to match the Redis it started, so it
overrides whatever is in `.env`.

---

## Wiring

```python
# manage/celery.py
app = Celery("manage")
app.config_from_object("django.conf:settings", namespace="CELERY")
app.autodiscover_tasks()
```

```python
# manage/__init__.py
from .celery import app as celery_app
__all__ = ("celery_app",)
```

Importing `manage` starts the app, which is why `-A manage` works.

The `CELERY_` namespace means every Celery setting in `settings/base.py` is
prefixed. `CELERY_BROKER_URL` becomes Celery's `broker_url`.

| Setting | Value |
|---|---|
| `CELERY_BROKER_URL` | `redis://localhost:6379/0` |
| `CELERY_RESULT_BACKEND` | `django-db`, so results go to `django_celery_results` tables |
| `CELERY_ACCEPT_CONTENT` | `["application/json"]` |
| `CELERY_TASK_SERIALIZER`, `CELERY_RESULT_SERIALIZER` | `json` |
| `CELERY_TIMEZONE` | `UTC` |
| `CELERY_TASK_TRACK_STARTED` | `True` |
| `CELERY_TASK_TIME_LIMIT` | 1800 seconds |
| `CELERY_RESULT_EXPIRES` | 2592000 seconds, 30 days |
| `CELERY_BEAT_SCHEDULER` | `django_celery_beat.schedulers:DatabaseScheduler` |

Because results and schedules live in the database, a worker needs database
access, not only Redis, and `celery_taskmeta` grows until results expire.

---

## The tasks

There is exactly one today:

```python
# communications/services/communication_services.py
@shared_task
def send_email_task(receivers, subject, message, from_email=None, html_message=None):
    ...
```

Used by `EmailService.send_async`. SMS is **not** queued despite the method name.
See [../apps/communications.md](../apps/communications.md).

> **Discovery is indirect, and worth understanding before you add tasks.**
> `autodiscover_tasks()` looks for a `tasks.py` in each **installed** app.
> `communications` is not an installed app, and the task is not in a `tasks.py`.
> It gets registered only because `@shared_task` registers on import, and
> `contact_verification/models.py` imports `communications.services` at module
> level. Break that import chain and the worker silently stops knowing about the
> task, and calls to `.delay()` queue work nothing will ever run.
>
> When adding tasks, put them in `{app}/tasks.py` inside an installed app, where
> autodiscovery finds them deterministically.

---

## Adding a task

```python
# myapp/tasks.py
from celery import shared_task
from structlog import get_logger

log = get_logger(__name__)


@shared_task
def do_the_thing(user_id: str, language_code: str = "en"):
    ...
```

Two rules specific to this codebase:

1. **Pass primitives, not model instances.** Arguments are JSON-serialized.
2. **The global context does not exist inside a task.**
   `GlobalContextMiddleware.get_global_context()` returns `NullGlobalContext`,
   with no user, no permissions, and language `en`. Pass `user_id` and
   `language_code` explicitly. A meta-test enforces this, see
   [../conventions/logging-and-context.md](../conventions/logging-and-context.md).

---

## Scheduled work

`DatabaseScheduler` means schedules are rows, not code. Create them in the admin
under Periodic Tasks, or programmatically:

```python
from django_celery_beat.models import PeriodicTask, IntervalSchedule

schedule, _ = IntervalSchedule.objects.get_or_create(every=1, period=IntervalSchedule.HOURS)
PeriodicTask.objects.get_or_create(
    interval=schedule, name="expire-subscriptions", task="myapp.tasks.expire_subscriptions"
)
```

Changes take effect without a redeploy, and beat picks them up on its next tick.

---

## In production

```
worker: celery -A manage worker -l INFO
beat:   celery -A manage beat -l INFO --scheduler django_celery_beat.schedulers:DatabaseScheduler
```

Run **exactly one beat process**. Two schedulers means every periodic task fires
twice. Workers scale freely.

The `Procfile` comment about `--preload` applies to the `web` process, not these.
See [deployment.md](deployment.md).

---

## In tests

`settings/local_test.py`:

```python
CELERY_TASK_ALWAYS_EAGER = True
CELERY_TASK_EAGER_PROPAGATES = True
```

Tasks run inline, so no worker or broker is needed, and a failing task fails the
test rather than being swallowed. See [../testing.md](../testing.md).

---

## Troubleshooting

| Symptom | Cause |
|---|---|
| `.delay()` returns but nothing happens | No worker running, or the task was never imported. See the discovery note above |
| Worker crashes on macOS | Fork safety. Use `--pool=solo` |
| Connection refused on 6379 | Redis is not running. `bin/celery` starts one |
| Beat schedules do nothing | Beat is not running, or the `PeriodicTask` is disabled |
| Tasks run twice | Two beat processes |
| `celery_taskmeta` growing | Expected. Results live 30 days |

---

## Related

- [../apps/communications.md](../apps/communications.md) for the email task.
- [deployment.md](deployment.md) for the process model.
- [../conventions/logging-and-context.md](../conventions/logging-and-context.md) for why context is absent.
