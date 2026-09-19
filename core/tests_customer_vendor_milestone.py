from datetime import timedelta
from decimal import Decimal

from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase, override_settings
from django.urls import reverse
from django.utils import timezone
from PIL import Image
from io import BytesIO
from rest_framework.test import APITestCase

from accounts.models import User
from core.models import Category, EventRequest, Listing, Review, VendorProfile


def picture():
    stream = BytesIO(); Image.new("RGB", (20, 20), "#bd6046").save(stream, "JPEG")
    return SimpleUploadedFile("profile.jpg", stream.getvalue(), content_type="image/jpeg")


class CustomerWebDiscoveryTests(TestCase):
    def setUp(self):
        self.customer = User.objects.create_user(email="web-customer@example.com", role=User.Role.CUSTOMER)
        self.other = User.objects.create_user(email="other-web@example.com", role=User.Role.CUSTOMER)
        self.vendor_user = User.objects.create_user(email="web-vendor@example.com", role=User.Role.VENDOR)
        self.category = Category.objects.create(name="Catering", slug="catering")
        self.profile = VendorProfile.objects.create(user=self.vendor_user, business_name="Table Studio", slug="table-studio", primary_category=self.category, city="Toronto", service_area="Toronto", description="Full catering", approval_status=VendorProfile.ApprovalStatus.APPROVED)
        Listing.objects.create(profile=self.profile, listing_type=Listing.ListingType.SERVICE, title="Dinner service", category=self.category, help_types=[EventRequest.HelpType.CATERING], image="test.jpg", description="Dinner", pricing_type=Listing.PricingType.FIXED, price=Decimal("2000"))
        self.client.force_login(self.customer)

    def payload(self):
        return {"event_type": EventRequest.EventType.WEDDING, "custom_event_type": "", "event_date": str(timezone.localdate() + timedelta(days=30)), "city": "Toronto", "postal_code": "M5V", "guest_count": 50, "budget_min": "1000", "budget_max": "3000", "help_types": [EventRequest.HelpType.CATERING], "required_categories": [self.category.pk], "theme": "Warm", "colours": "cream, olive", "venue_type": EventRequest.VenueType.INDOOR, "notes": "No address"}

    def test_customer_questionnaire_creates_shared_ready_event_and_displays_match(self):
        response = self.client.post(reverse("core:event-discovery"), self.payload())
        event = EventRequest.objects.get(customer=self.customer)
        self.assertRedirects(response, reverse("core:event-matches", args=[event.pk]))
        self.assertContains(self.client.get(reverse("core:event-matches", args=[event.pk])), "Table Studio")
        self.assertEqual(event.status, EventRequest.Status.READY)
        self.assertEqual(event.help_types, [EventRequest.HelpType.CATERING])
        self.assertEqual(event.colours, ["cream", "olive"])
        results = self.client.get(reverse("core:event-matches", args=[event.pk]), {"service": EventRequest.HelpType.CATERING, "location": "Toronto", "price_max": "2500"})
        self.assertContains(results, "Table Studio")
        self.assertContains(results, "Approved")

    def test_pending_vendor_is_not_rendered_and_other_customer_event_is_hidden(self):
        event = EventRequest.objects.create(customer=self.customer, status=EventRequest.Status.READY)
        self.profile.approval_status = VendorProfile.ApprovalStatus.PENDING; self.profile.save(update_fields=["approval_status"])
        self.assertNotContains(self.client.get(reverse("core:event-matches", args=[event.pk])), "Table Studio")
        foreign = EventRequest.objects.create(customer=self.other, status=EventRequest.Status.READY)
        self.assertEqual(self.client.get(reverse("core:event-matches", args=[foreign.pk])).status_code, 404)

    def test_dashboard_lists_events_and_can_resume_mobile_draft(self):
        draft = EventRequest.objects.create(customer=self.customer, event_type=EventRequest.EventType.BIRTHDAY, status=EventRequest.Status.DRAFT, completed_step=2)
        dashboard = self.client.get(reverse("core:customer-dashboard"))
        self.assertContains(dashboard, "Birthday")
        self.assertContains(dashboard, f"?event_id={draft.pk}")
        edit = self.client.get(reverse("core:event-discovery"), {"event_id": draft.pk})
        self.assertEqual(edit.context["form"].instance.pk, draft.pk)


class VendorBasicProfileAPITests(APITestCase):
    def setUp(self):
        self.vendor = User.objects.create_user(email="mobile-vendor@example.com", role=User.Role.VENDOR)
        self.other_vendor = User.objects.create_user(email="mobile-other@example.com", role=User.Role.VENDOR)
        self.customer = User.objects.create_user(email="mobile-customer@example.com", role=User.Role.CUSTOMER)
        self.category = Category.objects.create(name="Decor", slug="decor")
        self.profile = VendorProfile.objects.create(user=self.vendor, business_name="Old Name", slug="old-name", city="Old City", service_area="Old Area", description="Full web description", tags="private-to-mobile", availability="Weekends", approval_status=VendorProfile.ApprovalStatus.APPROVED)
        self.other_profile = VendorProfile.objects.create(user=self.other_vendor, business_name="Other", slug="other-basic", city="", service_area="", description="")
        self.url = reverse("api-v1:vendor-basic-profile")

    def test_vendor_reads_and_updates_only_allowed_own_fields_without_approval_control(self):
        self.client.force_authenticate(self.vendor)
        response = self.client.patch(self.url, {"business_name": "New Name", "category": self.category.pk, "phone": "555-0100", "city": "Toronto", "service_area": "GTA", "short_description": "Small celebrations", "approval_status": VendorProfile.ApprovalStatus.REJECTED, "tags": "changed", "availability": "Never"}, format="json")
        self.assertEqual(response.status_code, 200, response.data)
        self.profile.refresh_from_db(); self.other_profile.refresh_from_db()
        self.assertEqual(self.profile.business_name, "New Name")
        self.assertEqual(self.profile.slug, "new-name")
        self.assertEqual(self.profile.primary_category, self.category)
        self.assertEqual(self.profile.approval_status, VendorProfile.ApprovalStatus.APPROVED)
        self.assertEqual(self.profile.tags, "private-to-mobile")
        self.assertEqual(self.profile.availability, "Weekends")
        self.assertEqual(self.other_profile.business_name, "Other")
        self.assertNotIn("tags", response.data); self.assertNotIn("availability", response.data)
        self.assertIn("full_profile_url", response.data)

    def test_customer_cannot_read_or_edit_vendor_profile(self):
        self.client.force_authenticate(self.customer)
        self.assertEqual(self.client.get(self.url).status_code, 403)
        self.assertEqual(self.client.patch(self.url, {"business_name": "Hijacked"}, format="json").status_code, 403)
        self.profile.refresh_from_db(); self.assertEqual(self.profile.business_name, "Old Name")

    @override_settings(STORAGES={"default": {"BACKEND": "django.core.files.storage.InMemoryStorage"}})
    def test_vendor_can_upload_valid_profile_image_and_use_category_api(self):
        self.client.force_authenticate(self.vendor)
        categories = self.client.get(reverse("api-v1:categories"))
        self.assertEqual(categories.status_code, 200)
        response = self.client.patch(self.url, {"profile_image": picture()}, format="multipart")
        self.assertEqual(response.status_code, 200, response.data)
        self.assertTrue(response.data["profile_image_url"].endswith(".jpg"))

    def test_vendor_web_form_keeps_full_profile_fields(self):
        self.client.force_authenticate(None); self.client.force_login(self.vendor)
        response = self.client.get(reverse("core:vendor-profile-manage"))
        for field in ("tags", "availability", "google_business_url", "description", "cover_image"):
            self.assertIn(field, response.context["form"].fields)
        self.assertNotIn("approval_status", response.context["form"].fields)


class MatchingConsistencyTests(TestCase):
    payload = CustomerWebDiscoveryTests.payload

    def setUp(self):
        CustomerWebDiscoveryTests.setUp(self)
        self.client.post(reverse("core:event-discovery"), self.payload())
        self.event = EventRequest.objects.get(customer=self.customer)
        from rest_framework.test import APIClient
        self.api = APIClient()
        self.api.force_authenticate(self.customer)
        self.api_url = reverse("api-v1:event-matches", args=[self.event.pk])
        self.web_url = reverse("core:event-matches", args=[self.event.pk])

    def test_specific_services_do_not_match_unrelated_service_listings(self):
        self.profile.listings.update(help_types=[EventRequest.HelpType.DECORATOR])
        self.assertEqual(self.api.get(self.api_url).data["results"], [])
        self.profile.listings.update(help_types=[EventRequest.HelpType.CATERING])
        self.assertEqual(self.api.get(self.api_url).data["count"], 1)
        self.assertEqual(self.api.get(self.api_url, {"service": "PLANNER"}).data["count"], 0)

    def test_verified_rating_filters_have_identical_web_and_api_results(self):
        Review.objects.create(event=self.event, vendor=self.profile, rating=1, comment="Unverified")
        self.assertEqual(self.api.get(self.api_url, {"rating_min": 4}).data["count"], 0)
        Review.objects.filter(event=self.event).update(rating=5, is_verified=True, verification_note="Confirmed service")
        params = {"rating_min": 4, "sort": "rating", "service": "CATERING", "location": "Toronto", "category": self.category.pk, "price_max": "2500"}
        api = self.api.get(self.api_url, params)
        web = self.client.get(self.web_url, params)
        self.assertEqual(api.data["results"], web.context["matches"])
        self.assertEqual(api.data["results"][0]["rating"], 5)
        self.assertEqual(api.data["results"][0]["review_count"], 1)
        self.assertTrue(api.data["rating_available"])
        self.assertEqual(self.api.get(self.api_url, {"rating_min": 6}).status_code, 400)
        self.assertContains(self.client.get(reverse("core:vendor-profile", args=[self.profile.slug])), "Unverified")

    def test_unverified_reviews_are_not_public(self):
        Review.objects.create(event=self.event, vendor=self.profile, rating=5, comment="Private pending review")
        self.assertNotContains(self.client.get(reverse("core:vendor-profile", args=[self.profile.slug])), "Private pending review")

    def test_review_submission_requires_owner_and_past_event_and_cannot_self_verify(self):
        url = reverse("api-v1:event-review", args=[self.event.pk, self.profile.pk])
        payload = {"rating": 5, "comment": "Great catering", "is_verified": True, "verification_note": "Spoofed"}
        self.assertEqual(self.api.post(url, payload, format="json").status_code, 400)
        self.event.event_date = timezone.localdate() - timedelta(days=1)
        self.event.save()
        self.assertEqual(self.api.post(url, payload, format="json").status_code, 400)
        self.event.saved_vendors.add(self.profile)
        self.api.force_authenticate(self.other)
        self.assertEqual(self.api.post(url, payload, format="json").status_code, 404)
        self.api.force_authenticate(self.vendor_user)
        self.assertEqual(self.api.post(url, payload, format="json").status_code, 403)
        self.api.force_authenticate(self.customer)
        self.assertEqual(self.api.post(url, payload, format="json").status_code, 201)
        review = Review.objects.get(event=self.event)
        self.assertFalse(review.is_verified)
        self.assertEqual(review.verification_note, "")
        self.assertEqual(self.api.post(url, payload, format="json").status_code, 400)

    def test_verification_requires_staff_evidence(self):
        from django.core.exceptions import ValidationError
        review = Review(event=self.event, vendor=self.profile, rating=5, comment="Great", is_verified=True)
        with self.assertRaises(ValidationError):
            review.full_clean()

    def test_web_profile_saves_additional_categories(self):
        from core.forms import VendorProfileForm
        extra = Category.objects.create(name="Decor", slug="decor")
        form = VendorProfileForm({"business_name": "Table Studio", "primary_category": self.category.pk,
                                  "additional_categories": [extra.pk], "city": "Toronto", "service_area": "Toronto",
                                  "description": "Dinner", "years_experience": 1}, instance=self.profile)
        self.assertTrue(form.is_valid(), form.errors)
        form.save()
        self.assertEqual(list(self.profile.additional_categories.all()), [extra])


    def test_service_choices_and_multi_service_requests(self):
        listing = self.profile.listings.get()
        for service in ("PLANNER", "DECORATOR", "COMPLETE_SERVICE", "CATERING", "OTHER_SERVICES", "RENTAL_ITEMS"):
            with self.subTest(service=service):
                listing.help_types = [service]
                listing.listing_type = "RENTAL" if service == "RENTAL_ITEMS" else "SERVICE"
                listing.save()
                self.event.help_types = [service]
                self.event.save()
                self.assertEqual(self.api.get(self.api_url).data["count"], 1)
        self.event.help_types = ["PLANNER", "RENTAL_ITEMS"]
        self.event.save()
        self.assertEqual(self.api.get(self.api_url).data["count"], 1)

    def test_rating_average_ignores_pending_reviews_and_sorts_unrated_last(self):
        another_event = EventRequest.objects.create(customer=self.other)
        Review.objects.create(event=self.event, vendor=self.profile, rating=5, comment="Excellent", is_verified=True, verification_note="Confirmed")
        Review.objects.create(event=another_event, vendor=self.profile, rating=3, comment="Good", is_verified=True, verification_note="Confirmed")
        third_event = EventRequest.objects.create(customer=self.customer)
        Review.objects.create(event=third_event, vendor=self.profile, rating=1, comment="Pending")
        user = User.objects.create_user(email="unrated@example.com", role=User.Role.VENDOR)
        unrated = VendorProfile.objects.create(user=user, business_name="A Unrated", slug="unrated", primary_category=self.category, city="Toronto", service_area="Toronto", description="Dinner", approval_status="APPROVED")
        Listing.objects.create(profile=unrated, title="Dinner", listing_type="SERVICE", help_types=["CATERING"], category=self.category, image="test.jpg", description="Dinner", pricing_type="FIXED", price=2000)
        response = self.api.get(self.api_url, {"sort": "rating"})
        self.assertEqual([item["id"] for item in response.data["results"]], [self.profile.pk, unrated.pk])
        self.assertEqual(response.data["results"][0]["rating"], 4)
        self.assertEqual(response.data["results"][0]["review_count"], 2)
        self.assertEqual(self.api.get(self.api_url, {"rating_min": "4.1"}).data["count"], 0)
