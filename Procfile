# --preload is used to load the application code before forking the workers.
# This is useful for applications that are slow to start up.
# It also helps to avoid double initiation of scheduled jobs.
# You need to take care of multiple initialization of scheduled jobs if you plan to remove --preload
# https://sepgh.medium.com/common-mistakes-with-using-apscheduler-in-your-python-and-django-applications-100b289b812c
# If you plan to use multiple VM instances, it will already cause multiple schedulers.
# We suggest to use celery for scheduled jobs at that moment

web: gunicorn -c gunicorn.conf.py -w 3 manage.wsgi:application --timeout 15 --preload
release: ./release.sh