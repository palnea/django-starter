import threading

from django.conf import settings


def call_async(func):
    def wrapper(*args, **kwargs):
        if getattr(settings, "TEST_MODE", False):
            return func(*args, **kwargs)

        thread = threading.Thread(target=func, args=args, kwargs=kwargs)
        thread.start()
        return None

    return wrapper
