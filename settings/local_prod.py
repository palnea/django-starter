"""
Production-like settings for local use.

Local development and production do not serve static files the same way, and the
difference is invisible until something is deployed:

    DEBUG=True   Django's staticfiles finders serve unhashed files straight out
                 of each app's static/ directory. STATIC_ROOT is never read, so
                 a missing or stale staticfiles.json goes unnoticed.

    DEBUG=False  whitenoise serves content-hashed filenames out of STATIC_ROOT
                 and resolves every {% static %} through staticfiles.json. A
                 missing entry raises ValueError.

This module reproduces the second case locally, so a broken asset reference is
caught before it reaches production rather than after.

Run it with:

    bin/server --prod

which collects static first, then serves with these settings.
"""

from settings.development import *  # noqa: F401,F403

# The whole point of this module. Everything below follows from it.
DEBUG = False

# development.py already allows localhost, 127.0.0.1 and [::1]. Repeated here so
# this module keeps working if that list is ever narrowed.
ALLOWED_HOSTS = list({*ALLOWED_HOSTS, "localhost", "127.0.0.1", "[::1]"})  # noqa: F405

# base.py derives this from its own DEBUG, which is False, so it is already 3600
# by the time development.py flips DEBUG on. Set it explicitly so the schema
# cache behaves like production rather than depending on import order.
API_SCHEMA_CACHE_TIMEOUT = 3600
