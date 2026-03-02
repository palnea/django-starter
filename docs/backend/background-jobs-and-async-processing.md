# Background Jobs and Async Processing

## Celery Configuration

### Timezone Handling

Always enable UTC in Celery to avoid ambiguity with daylight saving time transitions:

```python
CELERY_ENABLE_UTC = True
CELERY_TIMEZONE = TIME_ZONE  # uses the project's TIME_ZONE setting
```

`CELERY_ENABLE_UTC = True` ensures that task timestamps, ETA/countdown calculations, and periodic-task schedules all operate in UTC internally, regardless of `CELERY_TIMEZONE`. The `CELERY_TIMEZONE` setting only affects how times are displayed in monitoring tools like Flower.

### Task Retry Configuration

**Important:** `CELERY_TASK_MAX_RETRIES` and `CELERY_TASK_DEFAULT_RETRY_DELAY` are **not** standard Celery settings. Celery does not provide global retry defaults. Retry behavior must be configured per-task using the built-in task parameters.

Configure retries directly on each task:

```python
@shared_task(
    bind=True,
    max_retries=3,            # maximum number of retry attempts
    default_retry_delay=60,   # seconds between retries
    autoretry_for=(TransientError,),  # auto-retry on these exceptions
    retry_backoff=True,       # exponential backoff (60s, 120s, 240s, ...)
    retry_backoff_max=600,    # cap backoff at 10 minutes
    retry_jitter=True,        # add randomness to avoid thundering herd
)
def send_notification(self, user_id):
    try:
        # task logic
        ...
    except TransientError as exc:
        raise self.retry(exc=exc)
```

Key parameters (all set on the `@shared_task` decorator):

| Parameter | Purpose | Default |
|---|---|---|
| `max_retries` | Max retry attempts per task invocation | `3` |
| `default_retry_delay` | Seconds before the first retry | `180` |
| `autoretry_for` | Tuple of exception classes that trigger automatic retry | `()` |
| `retry_backoff` | Enable exponential backoff | `False` |
| `retry_backoff_max` | Upper bound on backoff delay (seconds) | `600` |
| `retry_jitter` | Randomize delay to spread retries | `True` |

If you need consistent retry behavior across many tasks, define a base task class:

```python
from celery import Task

class RetryableTask(Task):
    max_retries = 3
    default_retry_delay = 60
    autoretry_for = (TransientError,)
    retry_backoff = True

@shared_task(base=RetryableTask)
def my_task():
    ...
```
