from io import BytesIO

from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase, override_settings
from django.urls import reverse
from PIL import Image
from rest_framework.test import APIClient

from accounts.models import User
from core.forms import VendorProfileForm
from core.models import Category, Listing, ListingImage, ServiceLocation, VendorProfile, VendorTag


def picture(name="photo.png", format="PNG"):
    stream = BytesIO()
    Image.new("RGB", (10, 10), "red").save(stream, format=format)
    return SimpleUploadedFile(name, stream.getvalue(), content_type="image/" + format.lower())


@override_settings(STORAGES={"default": {"BACKEND": "django.core.files.storage.InMemoryStorage"}, "staticfiles": {"BACKEND": "django.contrib.staticfiles.storage.StaticFilesStorage"}})
class VendorOnboardingTests(TestCase):
    def setUp(self):
        self.vendor = User.objects.create_user(email="onboard@example.com", role="vendor")
        self.other = User.objects.create_user(email="other-onboard@example.com", role="vendor")
        self.customer = User.objects.create_user(email="customer-onboard@example.com", role="customer")
        self.category = Category.objects.create(name="Onboarding decor", slug="onboarding-decor")
        self.service = VendorTag.objects.get(name="Balloon arches", kind="SERVICE")
        self.event = VendorTag.objects.get(name="Birthday", kind="EVENT")
        self.area = ServiceLocation.objects.create(name="Test City")
        self.profile = VendorProfile.objects.create(user=self.vendor, business_name="Studio", slug="onboard-studio")
        self.foreign = VendorProfile.objects.create(user=self.other, business_name="Other", slug="onboard-other")
        self.client.force_login(self.vendor)
        self.api = APIClient()
        self.api.force_authenticate(self.vendor)

    def payload(self, **changes):
        data = dict(business_name="Studio", primary_category=self.category.pk, contact_first_name="Ari", contact_last_name="Lee", business_email="hello@example.com", phone="555-1234", city="Test City", description="Thoughtful event design.", years_experience=3, service_tags=[self.service.pk], event_tags=[self.event.pk], service_locations=[self.area.pk], business_address="123 PRIVATE RESIDENTIAL STREET", services_answer="We design celebrations.", style_answer="Modern and warm.", specialties_answer="Custom balloon installations.")
        data.update(changes)
        return data

    def complete_profile(self):
        response = self.client.post(reverse("core:vendor-profile-manage"), self.payload())
        self.assertRedirects(response, reverse("core:vendor-profile-preview"))
        self.profile.refresh_from_db()

    def approve(self):
        VendorProfile.objects.filter(pk=self.profile.pk).update(approval_status="APPROVED")
        self.profile.refresh_from_db()

    def test_draft_preview_submit_approval_and_private_address(self):
        self.complete_profile()
        self.assertEqual(self.profile.approval_status, "DRAFT")
        self.assertEqual(self.profile.service_tags.get(), self.service)
        self.assertEqual(self.profile.service_locations.get(), self.area)
        preview = self.client.get(reverse("core:vendor-profile-preview"))
        self.assertContains(preview, "Submit for admin approval")
        self.assertNotContains(preview, 'aria-label="Approved"')
        self.assertNotContains(preview, "123 PRIVATE RESIDENTIAL STREET")
        self.assertEqual(self.client.get(reverse("core:vendor-profile", args=[self.profile.slug])).status_code, 404)
        self.client.post(reverse("core:vendor-profile-submit"))
        self.profile.refresh_from_db()
        self.assertEqual(self.profile.approval_status, "PENDING")
        self.approve()
        public = self.client.get(reverse("core:vendor-profile", args=[self.profile.slug]))
        self.assertContains(public, "Balloon arches")
        self.assertNotContains(public, "123 PRIVATE RESIDENTIAL STREET")
        self.assertNotIn("business_address", self.api.get(reverse("api-v1:vendor-basic-profile")).data)

    def test_incomplete_draft_can_save_but_cannot_submit(self):
        response = self.client.post(reverse("core:vendor-profile-manage"), {"business_name": "Just starting"})
        self.assertEqual(response.status_code, 302)
        self.client.post(reverse("core:vendor-profile-submit"))
        self.profile.refresh_from_db()
        self.assertEqual(self.profile.approval_status, "DRAFT")
        self.assertEqual(self.profile.years_experience, 0)

    def test_identity_changes_requeue_but_description_changes_do_not(self):
        self.complete_profile()
        self.approve()
        self.client.post(reverse("core:vendor-profile-manage"), self.payload(description="Updated story"))
        self.profile.refresh_from_db()
        self.assertEqual(self.profile.approval_status, "APPROVED")
        self.client.post(reverse("core:vendor-profile-manage"), self.payload(business_name="New identity"))
        self.profile.refresh_from_db()
        self.assertEqual(self.profile.approval_status, "PENDING")
        self.assertEqual(self.client.get(reverse("core:vendor-profile", args=[self.profile.slug])).status_code, 404)

    def test_api_category_and_logo_changes_requeue(self):
        self.complete_profile()
        url = reverse("api-v1:vendor-basic-profile")
        new_category = Category.objects.create(name="New category", slug="new-category")
        for data, format in [({"category": new_category.pk}, "json"), ({"profile_image": picture()}, "multipart"), ({"business_email": "changed@example.com"}, "json")]:
            self.approve()
            response = self.api.patch(url, data, format=format)
            self.assertEqual(response.status_code, 200, response.data)
            self.assertEqual(response.data["approval_status"], "PENDING")

    def test_description_is_deterministic_editable_and_never_saved_by_generation(self):
        url = reverse("core:vendor-description-create")
        first = self.client.post(url, self.payload()).json()["description"]
        self.assertEqual(first, self.client.post(url, self.payload()).json()["description"])
        for value in ("Studio", "balloon arches", "birthday", "Modern and warm", "3 years"):
            self.assertIn(value, first)
        self.profile.refresh_from_db()
        self.assertEqual(self.profile.description, "")
        self.client.post(reverse("core:vendor-profile-manage"), self.payload(description="My edited draft"))
        self.profile.refresh_from_db()
        self.assertEqual(self.profile.description, "My edited draft")

    def test_inactive_or_wrong_kind_tags_rejected_and_rendered_as_chips(self):
        self.service.is_active = False
        self.service.save()
        response = self.api.patch(reverse("api-v1:vendor-basic-profile"), {"service_tags": [self.service.pk]}, format="json")
        self.assertEqual(response.status_code, 400)
        response = self.api.patch(reverse("api-v1:vendor-basic-profile"), {"service_tags": [self.event.pk]}, format="json")
        self.assertEqual(response.status_code, 400)
        self.service.is_active = True
        self.service.save()
        form = VendorProfileForm(instance=self.profile)
        self.assertIn("Balloon arches", str(form["service_tags"]))
        self.assertIn('type="checkbox"', str(form["service_tags"]))
        self.assertIn("<select", str(form["primary_category"]))

    def test_mobile_multiselect_and_explicit_clear(self):
        url = reverse("api-v1:vendor-basic-profile")
        response = self.api.patch(url, {"service_tags": [self.service.pk], "service_locations": [self.area.pk]}, format="multipart")
        self.assertEqual(response.status_code, 200, response.data)
        self.assertEqual(response.data["service_tags"], [self.service.pk])
        response = self.api.patch(url, {"clear_service_tags": "true", "clear_service_locations": "true"}, format="multipart")
        self.assertEqual(response.data["service_tags"], [])
        self.assertEqual(response.data["service_locations"], [])

    def test_customers_cannot_use_vendor_web_or_api_endpoints(self):
        self.client.force_login(self.customer)
        for name in ("vendor-profile-manage", "vendor-profile-preview", "vendor-portfolio-manage", "vendor-listings-manage"):
            self.assertEqual(self.client.get(reverse("core:" + name)).status_code, 403)
        for name in ("vendor-description-create", "vendor-profile-submit"):
            self.assertEqual(self.client.post(reverse("core:" + name), self.payload()).status_code, 403)
        self.api.force_authenticate(self.customer)
        for name in ("vendor-options", "vendor-portfolio", "vendor-basic-profile"):
            self.assertEqual(self.api.get(reverse("api-v1:" + name)).status_code, 403)
        self.assertEqual(self.api.post(reverse("api-v1:vendor-portfolio"), {"image": picture()}, format="multipart").status_code, 403)

    def test_portfolio_batch_validates_every_image_before_writing(self):
        url = reverse("core:vendor-portfolio-manage")
        bad = SimpleUploadedFile("bad.png", b"not an image", content_type="image/png")
        response = self.client.post(url, {"images": [picture(), bad], "caption": "Test"})
        self.assertEqual(response.status_code, 200)
        self.assertFalse(self.profile.portfolio_entries.exists())
        response = self.client.post(url, {"images": [picture(), picture()], "caption": "Celebration"})
        self.assertEqual(response.status_code, 302)
        self.assertEqual(self.profile.portfolio_entries.filter(caption="Celebration").count(), 2)

    def test_portfolio_api_upload_caption_ownership_and_validation(self):
        url = reverse("api-v1:vendor-portfolio")
        response = self.api.post(url, {"image": picture(), "caption": "Party"}, format="multipart")
        self.assertEqual(response.status_code, 201, response.data)
        detail = reverse("api-v1:vendor-portfolio-detail", args=[response.data["id"]])
        self.assertEqual(self.api.patch(detail, {"caption": "Edited"}, format="json").data["caption"], "Edited")
        self.api.force_authenticate(self.other)
        self.assertEqual(self.api.get(detail).status_code, 404)
        self.assertEqual(self.api.delete(detail).status_code, 404)
        self.assertEqual(self.api.patch(detail, {"caption": "Hijacked"}, format="json").status_code, 404)
        self.api.force_authenticate(self.vendor)
        self.assertEqual(self.api.delete(detail).status_code, 204)
        for upload in (picture("unsafe.html"), picture("unsupported.gif", "GIF"), SimpleUploadedFile("oversized.png", b"x" * (5 * 1024 * 1024 + 1)), SimpleUploadedFile("fake.png", b"invalid")):
            self.assertEqual(self.api.post(url, {"image": upload}, format="multipart").status_code, 400)

    def test_listing_gallery_tags_pricing_and_owner_scoped_removal(self):
        data = dict(title="Decor package", listing_type="SERVICE", category=self.category.pk, description="Custom decor", pricing_type="PER_PERSON", price="20", image=picture(), gallery=[picture(), picture()], service_tags=[self.service.pk], is_active="on")
        response = self.client.post(reverse("core:vendor-listings-manage"), data)
        self.assertEqual(response.status_code, 302)
        listing = self.profile.listings.get()
        self.assertEqual(listing.images.count(), 2)
        self.assertEqual(listing.service_tags.get(), self.service)
        foreign_listing = Listing.objects.create(profile=self.foreign, title="Other", listing_type="PRODUCT", category=self.category, description="Other", pricing_type="CONTACT_FOR_QUOTE", image="existing.png")
        foreign_photo = ListingImage.objects.create(listing=foreign_listing, image="foreign.png")
        data.pop("image"); data.pop("gallery")
        data["remove_images"] = [listing.images.first().pk, foreign_photo.pk]
        self.client.post(reverse("core:vendor-listing-edit", args=[listing.pk]), data)
        self.assertEqual(listing.images.count(), 1)
        self.assertTrue(ListingImage.objects.filter(pk=foreign_photo.pk).exists())
        self.assertEqual(self.client.get(reverse("core:vendor-listing-edit", args=[foreign_listing.pk])).status_code, 404)

    def test_changes_requested_feedback_and_resubmission(self):
        self.complete_profile()
        VendorProfile.objects.filter(pk=self.profile.pk).update(approval_status="CHANGES_REQUESTED", review_feedback="Please clarify your services.")
        self.assertContains(self.client.get(reverse("core:vendor-profile-manage")), "Please clarify your services.")
        self.client.post(reverse("core:vendor-profile-submit"))
        self.profile.refresh_from_db()
        self.assertEqual(self.profile.approval_status, "PENDING")

    def test_admin_can_request_changes_reject_and_approve(self):
        self.complete_profile()
        admin = User.objects.create_superuser(email="reviewer@example.com", password="test-password")
        self.client.force_login(admin)
        for action, expected in (("request_changes", "CHANGES_REQUESTED"), ("reject_profiles", "REJECTED"), ("approve_profiles", "APPROVED")):
            response = self.client.post(reverse("admin:core_vendorprofile_changelist"), {"action": action, "_selected_action": [self.profile.pk], "index": "0"})
            self.assertEqual(response.status_code, 302)
            self.profile.refresh_from_db()
            self.assertEqual(self.profile.approval_status, expected)

    def test_anonymous_access_and_forged_ownership_are_rejected(self):
        url = reverse("api-v1:vendor-portfolio")
        self.api.force_authenticate(None)
        self.assertEqual(self.api.get(url).status_code, 401)
        self.api.force_authenticate(self.vendor)
        response = self.api.post(url, {"image": picture(), "profile": self.foreign.pk}, format="multipart")
        self.assertEqual(response.status_code, 201)
        self.assertTrue(self.profile.portfolio_entries.filter(pk=response.data["id"]).exists())
        self.assertFalse(self.foreign.portfolio_entries.exists())
        response = self.api.patch(reverse("api-v1:vendor-basic-profile"), {"approval_status": "APPROVED", "user": self.other.pk, "review_feedback": "Forged feedback"}, format="json")
        self.assertEqual(response.data["approval_status"], "DRAFT")
        self.assertEqual(response.data["review_feedback"], "")

    def test_managed_locations_participate_in_customer_distance_free_search(self):
        from core.matching import serves_location
        self.profile.service_locations.add(self.area)
        self.assertTrue(serves_location(self.profile, "test city"))
        self.assertFalse(serves_location(self.profile, "Elsewhere"))

    def test_mobile_can_save_partial_draft_and_invalid_image_routes_return_405(self):
        response = self.api.patch(reverse("api-v1:vendor-basic-profile"), {"business_name": "Starting studio", "city": "", "service_area": ""}, format="json")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["approval_status"], "DRAFT")
        url = reverse("api-v1:vendor-portfolio")
        self.assertEqual(self.api.patch(url, {}, format="json").status_code, 405)
        self.assertEqual(self.api.delete(url).status_code, 405)
        self.assertEqual(self.api.post(reverse("api-v1:vendor-portfolio-detail", args=[1]), {}, format="json").status_code, 405)
