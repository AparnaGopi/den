from datetime import timedelta
from decimal import Decimal

from django.test import TestCase
from django.urls import reverse
from django.utils import timezone
from rest_framework import status
from rest_framework.test import APITestCase

from accounts.models import User
from core.event_rules import tomorrow_iso_date
from core.forms import EventDiscoveryForm
from core.models import Category, EventRequest, Listing, VendorProfile


class EventServiceWebTests(TestCase):
    def setUp(self):
        self.customer = User.objects.create_user(email="services-web@example.com", role=User.Role.CUSTOMER)
        self.client.force_login(self.customer)
        self.categories = {
            name: Category.objects.get(name=name)
            for name in ("Bouquets", "Guest makeup", "Buffet")
        }
        self.payload = {
            "event_type": EventRequest.EventType.BIRTHDAY,
            "custom_event_type": "",
            "event_date": tomorrow_iso_date(),
            "city": "Toronto",
            "postal_code": "M5V",
            "guest_count": "50",
            "budget_min": "500",
            "budget_max": "700",
            "help_types": ["EVENT_PLANNER", "FLORIST", "MAKEUP_ARTIST", "CATERER", "OTHER"],
            "other_help_text": "A pet-friendly setup",
            "required_categories": [category.pk for category in self.categories.values()],
            "theme": "",
            "colours": "",
            "venue_type": EventRequest.VenueType.UNDECIDED,
            "notes": "",
        }

    def test_other_help_requires_description_and_web_saves_multiple_services_and_categories(self):
        category_count = Category.objects.count()
        invalid = EventDiscoveryForm(data={**self.payload, "other_help_text": "   "})
        self.assertFalse(invalid.is_valid())
        self.assertIn("other_help_text", invalid.errors)

        response = self.client.post(reverse("core:event-discovery"), self.payload)
        self.assertEqual(response.status_code, 302)
        event = EventRequest.objects.get(customer=self.customer)
        self.assertEqual(set(event.help_types), set(self.payload["help_types"]))
        self.assertEqual(event.other_help_text, "A pet-friendly setup")
        self.assertSetEqual(set(event.required_categories.values_list("pk", flat=True)), {category.pk for category in self.categories.values()})
        self.assertEqual(Category.objects.count(), category_count)
        deselected = EventDiscoveryForm(data={**self.payload, "help_types": ["FLORIST"], "other_help_text": "stale text"})
        self.assertTrue(deselected.is_valid(), deselected.errors)
        self.assertEqual(deselected.cleaned_data["other_help_text"], "")

    def test_web_catalogue_shows_featured_services_and_browse_all_options(self):
        response = self.client.get(reverse("core:event-discovery"))
        self.assertContains(response, "Browse all services")
        self.assertContains(response, "Backdrops")
        self.assertContains(response, "Full planning")
        self.assertContains(response, 'value="OTHER"')


class EventServiceAPITests(APITestCase):
    def setUp(self):
        self.customer = User.objects.create_user(email="services-api@example.com", role=User.Role.CUSTOMER)
        self.client.force_authenticate(self.customer)
        self.event = EventRequest.objects.create(
            customer=self.customer,
            event_type=EventRequest.EventType.BIRTHDAY,
            event_date=timezone.localdate() + timedelta(days=30),
            city="Toronto",
            guest_count=50,
            budget_min=Decimal("500"),
            budget_max=Decimal("700"),
            completed_step=3,
        )
        self.url = reverse("api-v1:event-step", args=[self.event.pk, 4])

    def test_other_help_validation_and_step_progress_restore_text_and_categories(self):
        missing = self.client.patch(self.url, {"help_types": ["EVENT_PLANNER", "OTHER"]}, format="json")
        self.assertEqual(missing.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("other_help_text", missing.data)

        saved = self.client.patch(self.url, {
            "help_types": ["EVENT_PLANNER", "FLORIST", "MAKEUP_ARTIST", "CATERER", "OTHER"],
            "other_help_text": "A pet-friendly setup",
        }, format="json")
        self.assertEqual(saved.status_code, status.HTTP_200_OK, saved.data)
        self.assertEqual(saved.data["other_help_text"], "A pet-friendly setup")
        self.assertEqual(saved.data["completed_step"], 4)

        categories = [Category.objects.get(name=name) for name in ("Bouquets", "Guest makeup", "Buffet")]
        category_response = self.client.patch(
            reverse("api-v1:event-step", args=[self.event.pk, 5]),
            {"required_categories": [category.pk for category in categories]},
            format="json",
        )
        self.assertEqual(category_response.status_code, status.HTTP_200_OK, category_response.data)
        finish_later = self.client.patch(reverse("api-v1:event-detail", args=[self.event.pk]), {
            "help_types": ["EVENT_PLANNER", "FLORIST", "MAKEUP_ARTIST", "CATERER", "OTHER"],
            "other_help_text": "A pet-friendly setup",
            "required_categories": [category.pk for category in categories],
            "theme": "Saved for later",
        }, format="json")
        self.assertEqual(finish_later.status_code, status.HTTP_200_OK, finish_later.data)
        restored = self.client.get(reverse("api-v1:event-detail", args=[self.event.pk]))
        self.assertEqual(restored.data["theme"], "Saved for later")
        self.assertEqual(restored.data["other_help_text"], "A pet-friendly setup")
        self.assertEqual(set(restored.data["help_types"]), {"EVENT_PLANNER", "FLORIST", "MAKEUP_ARTIST", "CATERER", "OTHER"})
        self.assertEqual(set(restored.data["required_categories"]), {category.pk for category in categories})

    def test_category_api_is_the_seeded_grouped_catalogue(self):
        response = self.client.get(reverse("api-v1:categories"))
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        by_name = {category["name"]: category for category in response.data}
        for name in ("Full planning", "Day-of coordination", "Signage", "Floral arches", "Balloon bouquets", "Bridal makeup", "Private dining", "Photo booths", "Face painting", "Tableware", "Delivery", "Teardown"):
            self.assertIn(name, by_name)
        self.assertEqual(by_name["Bouquets"]["service_group"], Category.ServiceGroup.FLORALS)
        self.assertIn("FLORIST", by_name["Bouquets"]["relevant_help_types"])
        self.assertEqual(by_name["Event Planning"]["id"], Category.objects.get(name="Event Planning").pk)


class EventServiceMatchingTests(TestCase):
    def setUp(self):
        self.customer = User.objects.create_user(email="service-match-host@example.com", role=User.Role.CUSTOMER)
        self.vendor_user = User.objects.create_user(email="service-match-vendor@example.com", role=User.Role.VENDOR)
        self.bouquets = Category.objects.get(name="Bouquets")
        self.event = EventRequest.objects.create(
            customer=self.customer,
            event_type=EventRequest.EventType.BIRTHDAY,
            event_date=timezone.localdate() + timedelta(days=20),
            city="North York",
            guest_count=50,
            budget_min=Decimal("500"),
            budget_max=Decimal("700"),
            help_types=[EventRequest.HelpType.EVENT_PLANNER, EventRequest.HelpType.FLORIST],
            status=EventRequest.Status.READY,
            completed_step=6,
        )
        self.event.required_categories.add(self.bouquets)
        self.vendor = VendorProfile.objects.create(
            user=self.vendor_user,
            business_name="GTA Floral Studio",
            slug="gta-floral-studio",
            primary_category=self.bouquets,
            city="Toronto",
            service_area="GTA",
            description="Bouquets for celebrations.",
            approval_status=VendorProfile.ApprovalStatus.APPROVED,
            is_active=True,
        )
        Listing.objects.create(
            profile=self.vendor,
            listing_type=Listing.ListingType.SERVICE,
            title="Birthday bouquets",
            category=self.bouquets,
            help_types=[EventRequest.HelpType.FLORIST],
            image="test.jpg",
            description="Seasonal bouquets.",
            pricing_type=Listing.PricingType.CONTACT_FOR_QUOTE,
            is_active=True,
        )

    def test_planner_does_not_hide_florist_matches_and_web_matches_api(self):
        from rest_framework.test import APIClient

        api = APIClient()
        api.force_authenticate(self.customer)
        api_response = api.get(reverse("api-v1:event-matches", args=[self.event.pk]))
        web = self.client
        web.force_login(self.customer)
        web_response = web.get(reverse("core:event-matches", args=[self.event.pk]))
        self.assertEqual(api_response.status_code, status.HTTP_200_OK)
        api_ids = [item["id"] for item in api_response.data["results"]]
        web_ids = [item["id"] for item in web_response.context["matches"]]
        self.assertIn(self.vendor.pk, api_ids)
        self.assertIn(self.vendor.pk, web_ids)
        self.assertEqual(api_ids, web_ids)
