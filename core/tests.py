from io import BytesIO
from pathlib import Path
from tempfile import TemporaryDirectory

from django.core.exceptions import ValidationError
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase
from django.urls import reverse
from PIL import Image

from accounts.models import User

from .forms import ListingForm
from .models import Category, Listing, PortfolioEntry, VendorProfile, validate_vendor_image


def image_upload(name="portfolio.jpg", size=(20, 20)):
	stream = BytesIO()
	Image.new("RGB", size, "#bd6046").save(stream, format="JPEG")
	return SimpleUploadedFile(name, stream.getvalue(), content_type="image/jpeg")


class VendorStorefrontTests(TestCase):
	def setUp(self):
		self.category = Category.objects.create(name="Event design", slug="event-design")
		self.other_category = Category.objects.create(name="Florals", slug="florals")
		self.vendor = User.objects.create_user(email="vendor@example.com", password="a-strong-password-123", role=User.Role.VENDOR)
		self.other_vendor = User.objects.create_user(email="other@example.com", password="a-strong-password-123", role=User.Role.VENDOR)
		self.customer = User.objects.create_user(email="customer@example.com", password="a-strong-password-123", role=User.Role.CUSTOMER)
		self.profile = VendorProfile.objects.create(
			user=self.vendor,
			business_name="Gather Studio",
			slug="gather-studio",
			primary_category=self.category,
			city="Austin",
			service_area="Central Texas",
			description="Thoughtful gatherings.",
			approval_status=VendorProfile.ApprovalStatus.APPROVED,
		)

	def test_approved_profile_is_public(self):
		response = self.client.get(reverse("core:vendor-profile", args=[self.profile.slug]))

		self.assertEqual(response.status_code, 200)
		self.assertContains(response, "Gather Studio")
		self.assertContains(response, "Reviews will follow real bookings.")

	def test_unapproved_profile_is_hidden(self):
		self.profile.approval_status = VendorProfile.ApprovalStatus.PENDING
		self.profile.save(update_fields=["approval_status"])

		response = self.client.get(reverse("core:vendor-profile", args=[self.profile.slug]))

		self.assertEqual(response.status_code, 404)

	def test_customer_cannot_open_vendor_management(self):
		self.client.force_login(self.customer)

		response = self.client.get(reverse("core:vendor-profile-manage"))

		self.assertEqual(response.status_code, 403)

	def test_vendor_can_create_edit_and_delete_own_portfolio_entry(self):
		self.client.force_login(self.vendor)
		create_response = self.client.post(
			reverse("core:vendor-portfolio-manage"),
			{"image": image_upload(), "caption": "A summer table", "display_order": 2},
		)

		self.assertRedirects(create_response, reverse("core:vendor-portfolio-manage"))
		entry = PortfolioEntry.objects.get(profile=self.profile)
		edit_response = self.client.post(
			reverse("core:vendor-portfolio-edit", args=[entry.pk]),
			{"caption": "An edited summer table", "display_order": 1},
		)
		self.assertRedirects(edit_response, reverse("core:vendor-portfolio-manage"))
		entry.refresh_from_db()
		self.assertEqual(entry.caption, "An edited summer table")

		delete_response = self.client.post(reverse("core:vendor-portfolio-delete", args=[entry.pk]))
		self.assertRedirects(delete_response, reverse("core:vendor-portfolio-manage"))
		self.assertFalse(PortfolioEntry.objects.filter(pk=entry.pk).exists())

	def test_vendor_cannot_delete_another_vendor_portfolio_entry(self):
		entry = PortfolioEntry.objects.create(profile=self.profile, image="portfolio/existing.jpg")
		self.client.force_login(self.other_vendor)

		response = self.client.post(reverse("core:vendor-portfolio-delete", args=[entry.pk]))

		self.assertEqual(response.status_code, 404)
		self.assertTrue(PortfolioEntry.objects.filter(pk=entry.pk).exists())

	def test_profile_image_is_created_under_media_directory(self):
		with TemporaryDirectory() as media_root:
			with self.settings(MEDIA_ROOT=media_root):
				self.profile.profile_image = image_upload("profile.jpg")
				self.profile.save(update_fields=["profile_image"])

				self.assertTrue(Path(media_root, self.profile.profile_image.name).is_file())


class VendorValidationTests(TestCase):
	def setUp(self):
		self.active_category = Category.objects.create(name="Planning", slug="planning")
		self.inactive_category = Category.objects.create(name="Inactive", slug="inactive", is_active=False)

	def test_vendor_profile_rejects_inactive_and_more_than_three_additional_categories(self):
		additional = Category.objects.bulk_create([
			Category(name=f"Service {number}", slug=f"service-{number}") for number in range(1, 5)
		])
		from .forms import VendorProfileForm

		form = VendorProfileForm(data={
			"business_name": "Test Studio",
			"primary_category": self.inactive_category.pk,
			"additional_categories": [category.pk for category in additional],
			"city": "Austin",
			"service_area": "Central Texas",
			"description": "A studio.",
		})

		self.assertFalse(form.is_valid())
		self.assertIn("Select a valid choice", form.errors["primary_category"][0])
		self.assertIn("no more than three", form.errors["additional_categories"][0])

	def test_listing_rejects_inactive_category(self):
		form = ListingForm(
			data={
				"listing_type": Listing.ListingType.SERVICE,
				"title": "Full planning",
				"category": self.inactive_category.pk,
				"description": "Complete event planning.",
				"pricing_type": Listing.PricingType.CONTACT_FOR_QUOTE,
				"is_active": "on",
			},
			files={"image": image_upload("listing.jpg")},
		)

		self.assertFalse(form.is_valid())
		self.assertIn("Select a valid choice", form.errors["category"][0])

	def test_portfolio_image_size_is_limited(self):
		large_file = SimpleUploadedFile("large.jpg", b"0" * (5 * 1024 * 1024 + 1), content_type="image/jpeg")

		with self.assertRaisesMessage(ValidationError, "Images must be 5 MB or smaller."):
			validate_vendor_image(large_file)

	def test_contact_for_quote_cannot_have_a_price(self):
		form = ListingForm(
			data={
				"listing_type": Listing.ListingType.SERVICE,
				"title": "Full planning",
				"category": self.active_category.pk,
				"description": "Complete event planning.",
				"pricing_type": Listing.PricingType.CONTACT_FOR_QUOTE,
				"price": "2500.00",
				"is_active": "on",
			},
			files={"image": image_upload("listing.jpg")},
		)

		self.assertFalse(form.is_valid())
		self.assertIn("Leave price blank", form.errors["price"][0])
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
