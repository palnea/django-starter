from settings.development import *

VERIFICATION_ACTIVE_INTERVAL = 300

INSTALLED_APPS = [app for app in INSTALLED_APPS if app not in ["logger"]]

TEST_MODE = True

CELERY_TASK_ALWAYS_EAGER = True
CELERY_TASK_EAGER_PROPAGATES = True

# Disable throttling during tests to avoid rate-limit failures
REST_FRAMEWORK["DEFAULT_THROTTLE_CLASSES"] = []
REST_FRAMEWORK["DEFAULT_THROTTLE_RATES"] = {
    "anon": "100000/second",
    "user": "100000/second",
    "auth": "100000/second",
}
