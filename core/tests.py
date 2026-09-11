from django.test import TestCase
from django.urls import reverse


class HomePageTests(TestCase):
	def test_homepage_contains_den_actions(self):
		response = self.client.get(reverse("core:home"))

		self.assertEqual(response.status_code, 200)
		self.assertContains(response, "Plan your event in one place")
		self.assertContains(response, "Find Vendors")
		self.assertContains(response, "Become a Vendor")
from django.test import TestCase

# Create your tests here.
