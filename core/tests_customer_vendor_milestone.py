from datetime import timedelta
from decimal import Decimal

from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone
from PIL import Image
from io import BytesIO
from rest_framework.test import APITestCase

from accounts.models import User
from core.models import Category, EventRequest, Listing, VendorProfile


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
        Listing.objects.create(profile=self.profile, listing_type=Listing.ListingType.SERVICE, title="Dinner service", category=self.category, image="test.jpg", description="Dinner", pricing_type=Listing.PricingType.FIXED, price=Decimal("2000"))
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
