from datetime import timedelta
from decimal import Decimal

from django.urls import reverse
from django.utils import timezone
from rest_framework import status
from rest_framework.test import APITestCase

from accounts.models import User
from core.models import Category, EventRequest, Listing, VendorProfile


class EventDiscoveryAPITests(APITestCase):
    def setUp(self):
        self.customer = User.objects.create_user(email="host@example.com", role=User.Role.CUSTOMER)
        self.other_customer = User.objects.create_user(email="other-host@example.com", role=User.Role.CUSTOMER)
        self.vendor_user = User.objects.create_user(email="planner@example.com", role=User.Role.VENDOR)
        self.category = Category.objects.create(name="Planning", slug="planning")
        self.other_category = Category.objects.create(name="Florals", slug="florals")
        self.event = EventRequest.objects.create(
            customer=self.customer, event_type=EventRequest.EventType.WEDDING,
            event_date=timezone.localdate() + timedelta(days=30), city="Toronto", postal_code="M5V",
            guest_count=80, budget_min=Decimal("1000"), budget_max=Decimal("5000"),
            help_types=[EventRequest.HelpType.FULL_PLANNING], venue_type=EventRequest.VenueType.INDOOR,
            status=EventRequest.Status.READY, completed_step=6,
        )
        self.event.required_categories.add(self.category)
        self.profile = self.make_vendor("Good Gatherings", "good-gatherings", self.vendor_user, self.category)
        self.client.force_authenticate(self.customer)

    def make_vendor(self, name, slug, user, category, **profile_overrides):
        values = {
            "user": user, "business_name": name, "slug": slug, "primary_category": category,
            "city": "Toronto", "service_area": "Toronto, Mississauga", "description": "Careful event work.",
            "approval_status": VendorProfile.ApprovalStatus.APPROVED, "is_active": True,
        }
        values.update(profile_overrides)
        profile = VendorProfile.objects.create(**values)
        Listing.objects.create(profile=profile, listing_type=Listing.ListingType.SERVICE, title=f"{name} planning",
                               category=category, image="listings/test.jpg", description="Planning help",
                               pricing_type=Listing.PricingType.STARTING_FROM, price=Decimal("2500"), is_active=True)
        return profile

    def matches_url(self, event=None):
        return reverse("api-v1:event-matches", args=[(event or self.event).pk])

    def test_customer_can_create_list_retrieve_and_patch_only_own_drafts(self):
        created = self.client.post(reverse("api-v1:event-list"), {}, format="json")
        self.assertEqual(created.status_code, status.HTTP_201_CREATED)
        draft_id = created.data["id"]
        self.assertEqual(created.data["status"], EventRequest.Status.DRAFT)
        self.assertNotIn("address", created.data)
        updated = self.client.patch(reverse("api-v1:event-detail", args=[draft_id]), {"theme": "Garden"}, format="json")
        self.assertEqual(updated.status_code, status.HTTP_200_OK)
        self.assertEqual(updated.data["theme"], "Garden")
        own_list = self.client.get(reverse("api-v1:event-list"))
        self.assertEqual({item["id"] for item in own_list.data["results"]}, {self.event.pk, draft_id})
        other_event = EventRequest.objects.create(customer=self.other_customer)
        self.assertEqual(self.client.get(reverse("api-v1:event-detail", args=[other_event.pk])).status_code, status.HTTP_404_NOT_FOUND)
        self.assertEqual(self.client.patch(reverse("api-v1:event-detail", args=[other_event.pk]), {"city": "Ottawa"}, format="json").status_code, status.HTTP_404_NOT_FOUND)
        self.assertEqual(self.client.post(reverse("api-v1:event-complete", args=[other_event.pk])).status_code, status.HTTP_404_NOT_FOUND)
        self.assertEqual(self.client.get(self.matches_url(other_event)).status_code, status.HTTP_404_NOT_FOUND)

    def test_event_endpoints_require_an_authenticated_customer(self):
        self.client.force_authenticate(None)
        self.assertEqual(self.client.get(reverse("api-v1:event-list")).status_code, status.HTTP_401_UNAUTHORIZED)
        self.client.force_authenticate(self.vendor_user)
        self.assertEqual(self.client.get(reverse("api-v1:event-list")).status_code, status.HTTP_403_FORBIDDEN)

    def test_steps_save_progress_and_completion_validates_required_answers(self):
        draft = EventRequest.objects.create(customer=self.customer)
        one = self.client.patch(reverse("api-v1:event-step", args=[draft.pk, 1]), {"event_type": "OTHER", "custom_event_type": "Dinner"}, format="json")
        self.assertEqual(one.status_code, status.HTTP_200_OK)
        self.assertEqual(one.data["completed_step"], 1)
        skipped = self.client.patch(reverse("api-v1:event-step", args=[draft.pk, 3]), {"guest_count": 10}, format="json")
        self.assertEqual(skipped.status_code, status.HTTP_400_BAD_REQUEST)
        incomplete = self.client.post(reverse("api-v1:event-complete", args=[draft.pk]))
        self.assertEqual(incomplete.status_code, status.HTTP_400_BAD_REQUEST)
        payloads = [
            {"event_date": str(timezone.localdate() + timedelta(days=1)), "city": "Toronto", "postal_code": "M5V"},
            {"guest_count": 20, "budget_min": "500", "budget_max": "1500"},
            {"help_types": [EventRequest.HelpType.VENDORS_ONLY]},
            {"required_categories": [self.category.pk]},
            {"theme": "Warm", "colours": ["gold"], "venue_type": EventRequest.VenueType.UNDECIDED, "notes": "No exact address."},
        ]
        for step, payload in enumerate(payloads, 2):
            response = self.client.patch(reverse("api-v1:event-step", args=[draft.pk, step]), payload, format="json")
            self.assertEqual(response.status_code, status.HTTP_200_OK, response.data)
        completed = self.client.post(reverse("api-v1:event-complete", args=[draft.pk]))
        self.assertEqual(completed.status_code, status.HTTP_200_OK)
        self.assertEqual(completed.data["status"], EventRequest.Status.READY)
        self.assertEqual(completed.data["completed_step"], 6)

    def test_matching_returns_public_rule_explanations_without_private_information(self):
        response = self.client.get(self.matches_url())
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        match = response.data["results"][0]
        self.assertEqual(match["id"], self.profile.pk)
        self.assertEqual(match["match_score"], 100)
        self.assertEqual({reason["code"] for reason in match["matching_reasons"]}, {"CATEGORY_COVERAGE", "SERVICE_LOCATION", "HELP_TYPE", "INDICATIVE_BUDGET"})
        self.assertNotIn("email", match)
        self.assertNotIn("user", match)
        self.assertNotIn("google_place_identifier", match)
        self.assertTrue(all(listing["id"] for listing in match["listings"]))

    def test_only_approved_active_vendors_and_listings_can_match(self):
        scenarios = [
            {"approval_status": VendorProfile.ApprovalStatus.PENDING},
            {"is_active": False},
        ]
        for index, overrides in enumerate(scenarios):
            user = User.objects.create_user(email=f"hidden{index}@example.com", role=User.Role.VENDOR)
            self.make_vendor(f"Hidden {index}", f"hidden-{index}", user, self.category, **overrides)
        disabled_user = User.objects.create_user(email="disabled@example.com", role=User.Role.VENDOR, is_active=False)
        self.make_vendor("Disabled user", "disabled-user", disabled_user, self.category)
        inactive_listing_user = User.objects.create_user(email="inactive-listing@example.com", role=User.Role.VENDOR)
        inactive_profile = self.make_vendor("Inactive listing", "inactive-listing", inactive_listing_user, self.category)
        inactive_profile.listings.update(is_active=False)
        response = self.client.get(self.matches_url())
        self.assertEqual([item["id"] for item in response.data["results"]], [self.profile.pk])

    def test_category_location_help_type_and_budget_are_eligibility_rules(self):
        florist_user = User.objects.create_user(email="florist@example.com", role=User.Role.VENDOR)
        self.make_vendor("Florist", "florist", florist_user, self.other_category)
        far_user = User.objects.create_user(email="far@example.com", role=User.Role.VENDOR)
        self.make_vendor("Far Planner", "far-planner", far_user, self.category, city="Ottawa", service_area="Ottawa")
        rental_user = User.objects.create_user(email="rental@example.com", role=User.Role.VENDOR)
        rental = self.make_vendor("Rental", "rental", rental_user, self.category)
        rental.listings.update(listing_type=Listing.ListingType.RENTAL)
        pricey_user = User.objects.create_user(email="pricey@example.com", role=User.Role.VENDOR)
        pricey = self.make_vendor("Pricey", "pricey", pricey_user, self.category)
        pricey.listings.update(price=Decimal("6000"))
        ids = {item["id"] for item in self.client.get(self.matches_url()).data["results"]}
        self.assertEqual(ids, {self.profile.pk})

    def test_quote_only_listing_remains_eligible_without_false_budget_points(self):
        self.profile.listings.update(pricing_type=Listing.PricingType.CONTACT_FOR_QUOTE, price=None)
        match = self.client.get(self.matches_url()).data["results"][0]
        budget = next(reason for reason in match["matching_reasons"] if reason["code"] == "INDICATIVE_BUDGET")
        self.assertEqual(budget["points"], 0)
        self.assertEqual(match["match_score"], 80)

    def test_filters_and_sorting_are_validated_and_rating_falls_back(self):
        response = self.client.get(self.matches_url(), {"category": self.category.pk, "service": EventRequest.HelpType.PLANNER, "listing_type": "SERVICE", "location": "Mississauga", "price_min": "2000", "price_max": "3000", "sort": "newest"})
        self.assertEqual([item["id"] for item in response.data["results"]], [self.profile.pk])
        self.assertEqual(response.data["applied_sort"], "newest")
        rating = self.client.get(self.matches_url(), {"sort": "rating"})
        self.assertFalse(rating.data["rating_available"])
        self.assertEqual(rating.data["applied_sort"], "relevance")
        private = self.client.get(self.matches_url(), {"approval_status": "PENDING"})
        self.assertEqual(private.data["results"], [])
        invalid = self.client.get(self.matches_url(), {"price_min": "3000", "price_max": "1000"})
        self.assertEqual(invalid.status_code, status.HTTP_400_BAD_REQUEST)

    def test_save_vendor_is_persistent_and_cannot_save_private_vendor_or_another_event(self):
        url = reverse("api-v1:event-save-vendor", args=[self.event.pk, self.profile.pk])
        saved = self.client.put(url)
        self.assertEqual(saved.status_code, status.HTTP_200_OK)
        self.assertEqual(saved.data["saved_vendor_ids"], [self.profile.pk])
        removed = self.client.delete(url)
        self.assertEqual(removed.data["saved_vendor_ids"], [])
        hidden_user = User.objects.create_user(email="private@example.com", role=User.Role.VENDOR)
        hidden = self.make_vendor("Private", "private", hidden_user, self.category, approval_status=VendorProfile.ApprovalStatus.PENDING)
        self.assertEqual(self.client.put(reverse("api-v1:event-save-vendor", args=[self.event.pk, hidden.pk])).status_code, status.HTTP_404_NOT_FOUND)
        other = EventRequest.objects.create(customer=self.other_customer)
        self.assertEqual(self.client.put(reverse("api-v1:event-save-vendor", args=[other.pk, self.profile.pk])).status_code, status.HTTP_404_NOT_FOUND)

    def test_archived_events_cannot_be_edited_or_saved(self):
        archived = self.client.post(reverse("api-v1:event-archive", args=[self.event.pk]))
        self.assertEqual(archived.data["status"], EventRequest.Status.ARCHIVED)
        self.assertEqual(self.client.patch(reverse("api-v1:event-detail", args=[self.event.pk]), {"theme": "Changed"}, format="json").status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(self.client.put(reverse("api-v1:event-save-vendor", args=[self.event.pk, self.profile.pk])).status_code, status.HTTP_400_BAD_REQUEST)
