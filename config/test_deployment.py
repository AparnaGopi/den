import os
import subprocess
import sys
from unittest.mock import patch

from django.db import OperationalError
from django.test import SimpleTestCase, TestCase, override_settings


class DeploymentDomainTests(SimpleTestCase):
    def test_public_domains_work_with_missing_or_stale_environment_hosts(self):
        script = """
import django
django.setup()
from django.conf import settings
from django.test import Client
from django.middleware.csrf import CsrfViewMiddleware, get_token
from django.test import RequestFactory
for host in ('torontodecorden.com', 'www.torontodecorden.com', 'den-gc2w.onrender.com'):
    response = Client().get('/accounts/login/', secure=True, HTTP_HOST=host)
    assert response.status_code == 200, (host, response.status_code)
    origin = 'https://' + host
    assert origin in settings.CSRF_TRUSTED_ORIGINS
    initial = RequestFactory().get('/', secure=True, HTTP_HOST=host)
    token = get_token(initial)
    request = RequestFactory().post('/accounts/login/', secure=True,
        HTTP_HOST='den-gc2w.onrender.com', HTTP_ORIGIN=origin,
        HTTP_X_CSRFTOKEN=token)
    request.COOKIES[settings.CSRF_COOKIE_NAME] = initial.META['CSRF_COOKIE']
    rejection = CsrfViewMiddleware(lambda r: None).process_view(request, lambda r: None, (), {})
    assert rejection is None, (host, rejection.status_code)
assert Client().get('/accounts/login/', secure=True, HTTP_HOST='untrusted.example').status_code == 400
assert not settings.DEBUG
assert '*' not in settings.ALLOWED_HOSTS
"""
        for stale_value in (None, "test.torontodecorden.com"):
            with self.subTest(environment_hosts=stale_value):
                env = {
                    **os.environ,
                    "DJANGO_SETTINGS_MODULE": "config.settings_deploy",
                    "DJANGO_SECRET_KEY": "test-only-secret-key-" * 4,
                    "DATABASE_URL": "sqlite:///:memory:",
                    "RENDER_EXTERNAL_HOSTNAME": "den-gc2w.onrender.com",
                }
                for key in ("DJANGO_ALLOWED_HOSTS", "DJANGO_CSRF_TRUSTED_ORIGINS", "DEN_STORAGE_BACKEND", "DEN_STORAGE_OPTIONS"):
                    env.pop(key, None)
                if stale_value:
                    env["DJANGO_ALLOWED_HOSTS"] = stale_value
                    env["DJANGO_CSRF_TRUSTED_ORIGINS"] = "https://" + stale_value
                result = subprocess.run([sys.executable, "-c", script], env=env, capture_output=True, text=True, timeout=20)
                self.assertEqual(result.returncode, 0, result.stdout + result.stderr)


@override_settings(ROOT_URLCONF="config.urls_deploy")
class DeploymentHealthTests(TestCase):
    def test_healthy_database_returns_status_without_private_configuration(self):
        response = self.client.get("/health/", secure=True)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), {"status": "ok"})

    def test_database_outage_returns_503_without_exception_details(self):
        with patch("config.urls_deploy.connection.cursor", side_effect=OperationalError("private database details")):
            response = self.client.get("/health/", secure=True)
        self.assertEqual(response.status_code, 503)
        self.assertEqual(response.json(), {"status": "unavailable"})

    def test_health_does_not_accept_mutations(self):
        self.assertEqual(self.client.post("/health/", secure=True).status_code, 405)
