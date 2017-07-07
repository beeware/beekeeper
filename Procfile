web: gunicorn config.wsgi
worker: celery worker -c 2 -A config --loglevel=INFO