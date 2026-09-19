from django.test import TestCase
from django.urls import reverse

from .models import User


class AuthenticationFlowTests(TestCase):
	def test_homepage_become_vendor_opens_dedicated_registration(self):
		response = self.client.get(reverse("core:home"))

		self.assertContains(response, reverse("accounts:vendor-register"))
		vendor_page = self.client.get(reverse("accounts:vendor-register"))
		self.assertEqual(vendor_page.status_code, 200)
		self.assertContains(vendor_page, "Become a vendor")
		self.assertNotContains(vendor_page, 'name="role"')

	def test_vendor_registration_assigns_vendor_role_server_side(self):
		response = self.client.post(
			reverse("accounts:vendor-register"),
			{
				"email": "vendor@example.com",
				"password1": "a-strong-password-123",
				"password2": "a-strong-password-123",
				"role": User.Role.CUSTOMER,
			},
		)

		self.assertEqual(response.status_code, 302)
		self.assertEqual(User.objects.get(email="vendor@example.com").role, User.Role.VENDOR)

	def test_vendor_registration_redirects_to_vendor_onboarding(self):
		response = self.client.post(
			reverse("accounts:vendor-register"),
			{
				"email": "onboarding@example.com",
				"password1": "a-strong-password-123",
				"password2": "a-strong-password-123",
			},
		)

		self.assertRedirects(response, reverse("core:vendor-profile-manage"))

	def test_logged_in_customer_sees_vendor_account_choice(self):
		customer = User.objects.create_user(email="customer-vendor@example.com", password="a-strong-password-123")
		self.client.force_login(customer)

		response = self.client.get(reverse("accounts:vendor-register"))

		self.assertEqual(response.status_code, 200)
		self.assertContains(response, "You are currently signed in with a customer account.")
		self.assertContains(response, "Continue as customer")
		self.assertContains(response, "Log out and register as a vendor")

	def test_logged_in_vendor_opens_vendor_dashboard(self):
		vendor = User.objects.create_user(email="existing-vendor@example.com", password="a-strong-password-123", role=User.Role.VENDOR)
		self.client.force_login(vendor)

		response = self.client.get(reverse("accounts:vendor-register"))

		self.assertRedirects(response, reverse("core:vendor-dashboard"))

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
