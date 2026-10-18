#!/bin/sh
set -eu
python -m pip install -r deploy/requirements.txt
python manage.py collectstatic --noinput --settings=config.settings_deploy
