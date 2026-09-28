"""Isolated backend for scripts/vendor-wizard-smoke.cjs; never uses db.sqlite3."""
import os
import sys
from pathlib import Path
from tempfile import TemporaryDirectory

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')
from django.conf import settings

with TemporaryDirectory(prefix='den-wizard-smoke-') as directory:
    settings.DATABASES['default']['NAME'] = str(Path(directory) / 'smoke.sqlite3')
    settings.MEDIA_ROOT = Path(directory) / 'media'
    settings.DEBUG = True
    settings.CORS_ALLOW_ALL_ORIGINS = True
    import django
    django.setup()
    from django.core.management import call_command
    from core.models import ServiceLocation
    call_command('migrate', verbosity=0)
    ServiceLocation.objects.get_or_create(name='Toronto')
    call_command('runserver', '127.0.0.1:8765', use_reloader=False)
