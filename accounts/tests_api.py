from django.urls import reverse
from rest_framework import status
from rest_framework.test import APITestCase

from .models import User


class AuthenticationAPITests(APITestCase):
    def test_customer_registration_returns_tokens_and_customer_role(self):
        response = self.client.post(
            reverse("api-v1:register-customer"),
            {
                "email": "customer@example.com",
                "password": "a-strong-password-123",
                "first_name": "Casey",
                "last_name": "Customer",
                "role": User.Role.CUSTOMER,
            },
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(response.data["user"]["role"], User.Role.CUSTOMER)
        self.assertIn("access", response.data)
        self.assertIn("refresh", response.data)

    def test_vendor_registration_returns_vendor_role(self):
        response = self.client.post(
            reverse("api-v1:register-vendor"),
            {
                "email": "vendor@example.com",
                "password": "a-strong-password-123",
                "role": User.Role.VENDOR,
            },
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(response.data["user"]["role"], User.Role.VENDOR)

    def test_registration_rejects_admin_role(self):
        response = self.client.post(
            reverse("api-v1:register-customer"),
            {
                "email": "admin@example.com",
                "password": "a-strong-password-123",
                "role": "admin",
            },
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("role", response.data)
        self.assertFalse(User.objects.filter(email="admin@example.com").exists())

    def test_registration_rejects_role_mismatch(self):
        response = self.client.post(
            reverse("api-v1:register-customer"),
            {
                "email": "vendor@example.com",
                "password": "a-strong-password-123",
                "role": User.Role.VENDOR,
            },
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("only registers customer", response.data["role"][0])

    def test_duplicate_email_returns_clear_error(self):
        User.objects.create_user(email="duplicate@example.com", password="a-strong-password-123")

        response = self.client.post(
            reverse("api-v1:register-customer"),
            {
                "email": "duplicate@example.com",
                "password": "a-strong-password-123",
                "role": User.Role.CUSTOMER,
            },
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(response.data["email"][0], "A user with this email already exists.")

    def test_login_returns_tokens(self):
        User.objects.create_user(email="login@example.com", password="a-strong-password-123")

        response = self.client.post(
            reverse("api-v1:login"),
            {"email": "login@example.com", "password": "a-strong-password-123"},
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn("access", response.data)
        self.assertIn("refresh", response.data)

    def test_invalid_credentials_return_clear_error(self):
        User.objects.create_user(email="login@example.com", password="a-strong-password-123")

        response = self.client.post(
            reverse("api-v1:login"),
            {"email": "login@example.com", "password": "wrong-password"},
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(response.data["non_field_errors"][0], "Invalid email or password.")

    def test_token_refresh_returns_new_access_token(self):
        user = User.objects.create_user(email="refresh@example.com", password="a-strong-password-123")
        login_response = self.client.post(
            reverse("api-v1:login"),
            {"email": user.email, "password": "a-strong-password-123"},
            format="json",
        )

        response = self.client.post(
            reverse("api-v1:token-refresh"),
            {"refresh": login_response.data["refresh"]},
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn("access", response.data)

    def test_current_user_requires_authentication_and_returns_user(self):
        anonymous_response = self.client.get(reverse("api-v1:current-user"))
        self.assertEqual(anonymous_response.status_code, status.HTTP_401_UNAUTHORIZED)

        user = User.objects.create_user(
            email="me@example.com",
            password="a-strong-password-123",
            first_name="Morgan",
            last_name="Me",
            role=User.Role.VENDOR,
        )
        login_response = self.client.post(
            reverse("api-v1:login"),
            {"email": user.email, "password": "a-strong-password-123"},
            format="json",
        )
        self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {login_response.data['access']}")

        response = self.client.get(reverse("api-v1:current-user"))

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(
            response.data,
            {
                "id": user.id,
                "email": "me@example.com",
                "first_name": "Morgan",
                "last_name": "Me",
                "role": User.Role.VENDOR,
            },
        )