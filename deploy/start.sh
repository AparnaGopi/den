#!/bin/sh
set -eu
export DJANGO_SETTINGS_MODULE=config.settings_deploy
python manage.py migrate --noinput
exec gunicorn config.wsgi:application --bind "0.0.0.0:${PORT:-8000}" --workers "${WEB_CONCURRENCY:-2}" --access-logfile - --error-logfile -
