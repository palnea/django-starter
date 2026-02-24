import os

from celery import Celery

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "manage.settings")

app = Celery("manage")

# All celery-related config keys must have the `CELERY_` prefix in settings.
app.config_from_object("django.conf:settings", namespace="CELERY")

# Auto-discover tasks.py in every installed Django app.
app.autodiscover_tasks()
