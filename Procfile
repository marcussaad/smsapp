web: DJANGO_SETTINGS_MODULE=config.settings gunicorn config.wsgi --workers 2 --threads 4 --bind 0.0.0.0:$PORT --log-file - --timeout 30
release: DJANGO_SETTINGS_MODULE=config.settings python manage.py migrate --noinput
