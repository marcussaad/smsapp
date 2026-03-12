web: gunicorn config.wsgi --workers 2 --threads 4 --bind 0.0.0.0:$PORT --log-file -
release: python manage.py migrate --noinput
