from django.test import TestCase
from django.urls import reverse

from .models import User


class AuthenticationFlowTests(TestCase):
	def test_customer_registration_redirects_to_customer_dashboard(self):
		response = self.client.post(
			reverse("accounts:register"),
			{
				"email": "customer@example.com",
				"role": User.Role.CUSTOMER,
				"password1": "a-strong-password-123",
				"password2": "a-strong-password-123",
			},
		)

		self.assertRedirects(response, reverse("core:customer-dashboard"))
		self.assertTrue(self.client.session.get("_auth_user_id"))

	def test_vendor_registration_redirects_to_vendor_dashboard(self):
		response = self.client.post(
			reverse("accounts:register"),
			{
				"email": "vendor@example.com",
				"role": User.Role.VENDOR,
				"password1": "a-strong-password-123",
				"password2": "a-strong-password-123",
			},
		)

		self.assertRedirects(response, reverse("core:vendor-dashboard"))

	def test_email_login_and_post_logout(self):
		User.objects.create_user(email="login@example.com", password="a-strong-password-123")

		response = self.client.post(
			reverse("accounts:login"),
			{"username": "login@example.com", "password": "a-strong-password-123"},
		)
		self.assertRedirects(response, reverse("core:customer-dashboard"))

		response = self.client.post(reverse("accounts:logout"))
		self.assertRedirects(response, reverse("core:home"))
from django.test import TestCase

# Create your tests here.
