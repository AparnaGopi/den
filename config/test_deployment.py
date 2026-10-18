from unittest.mock import patch

from django.db import OperationalError
from django.test import TestCase, override_settings


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
