from io import StringIO
from unittest.mock import patch

from django.core.management import call_command, CommandError
from django.test import TestCase, override_settings
from django.urls import reverse

from accounts.models import User
from core.models import Category, EventRequest, Listing, VendorProfile, VendorTag


class DemoVendorSeedCommandTests(TestCase):
    def setUp(self):
        self.customer = User.objects.create_user(email="demo-seed-customer@example.com", role=User.Role.CUSTOMER)
        self.existing_user = User.objects.create_user(email="existing-toronto-decor@example.com", role=User.Role.VENDOR)
        self.existing_category = Category.objects.get(slug="table-styling")
        self.existing_profile = VendorProfile.objects.create(
            user=self.existing_user,
            business_name="Toronto Decor Den",
            slug="toronto-decor-den",
            primary_category=self.existing_category,
            city="Toronto",
            service_area="Toronto",
            description="Existing account that must remain untouched.",
            tags="existing-data",
            approval_status=VendorProfile.ApprovalStatus.APPROVED,
        )
        Listing.objects.create(
            profile=self.existing_profile,
            listing_type=Listing.ListingType.SERVICE,
            title="Existing decor service",
            category=self.existing_category,
            description="Existing listing.",
            pricing_type=Listing.PricingType.STARTING_FROM,
            price=100,
            help_types=[EventRequest.HelpType.DECORATOR],
        )

    def run_import(self):
        output = StringIO()
        with patch("core.management.commands.seed_demo_vendors.Command.check_local_database"):
            call_command("seed_demo_vendors", confirm_local=True, stdout=output)
        return output.getvalue()

    def test_import_is_gated_and_repeatable_without_changing_existing_vendor(self):
        with override_settings(DEN_ALLOW_LOCAL_DEMO_VENDOR_SEED=False):
            with self.assertRaises(CommandError):
                call_command("seed_demo_vendors", confirm_local=True, stdout=StringIO())

        original_password = self.existing_user.password
        original_profile_values = (
            self.existing_profile.business_name,
            self.existing_profile.slug,
            self.existing_profile.primary_category_id,
            self.existing_profile.city,
            self.existing_profile.service_area,
            self.existing_profile.description,
            self.existing_profile.tags,
            self.existing_profile.approval_status,
            self.existing_profile.is_active,
        )
        original_listing_count = self.existing_profile.listings.count()
        first = self.run_import()
        second = self.run_import()

        self.assertIn("Demo vendors created: 18; already seeded: 0; rows: 18.", first)
        self.assertIn("Demo vendors created: 0; already seeded: 18; rows: 18.", second)
        demo_profiles = VendorProfile.objects.filter(slug__startswith="den-demo-")
        self.assertEqual(demo_profiles.count(), 18)
        self.assertEqual(Listing.objects.filter(profile__in=demo_profiles).count(), 18)
        self.assertTrue(all(profile.is_active and profile.approval_status == VendorProfile.ApprovalStatus.APPROVED for profile in demo_profiles))
        self.assertTrue(all(not profile.user.has_usable_password() for profile in demo_profiles))

        self.existing_user.refresh_from_db()
        self.existing_profile.refresh_from_db()
        self.assertEqual(self.existing_user.password, original_password)
        self.assertEqual((
            self.existing_profile.business_name,
            self.existing_profile.slug,
            self.existing_profile.primary_category_id,
            self.existing_profile.city,
            self.existing_profile.service_area,
            self.existing_profile.description,
            self.existing_profile.tags,
            self.existing_profile.approval_status,
            self.existing_profile.is_active,
        ), original_profile_values)
        self.assertEqual(self.existing_profile.listings.count(), original_listing_count)

    def test_seed_data_maps_to_existing_categories_and_service_models(self):
        self.run_import()
        florist = VendorProfile.objects.get(slug="den-demo-001")
        listing = florist.listings.get()
        self.assertEqual(florist.primary_category, Category.objects.get(name="Bouquets"))
        self.assertEqual(set(listing.help_types), {EventRequest.HelpType.FLORIST})
        self.assertEqual(listing.price, 250)
        self.assertEqual(
            set(listing.service_tags.values_list("name", flat=True)),
            {"Bouquets", "Table decoration", "Floral decoration"},
        )
        self.assertEqual(
            set(florist.service_locations.values_list("name", flat=True)),
            {"Toronto", "North York", "Scarborough"},
        )

    def test_each_customer_filter_narrows_seed_and_clear_restores_approved_catalogue(self):
        self.client.force_login(self.customer)
        self.run_import()
        url = reverse("core:vendor-discovery")
        baseline = self.client.get(url)
        all_approved_ids = {item["id"] for item in baseline.context["matches"]}
        demo_ids = {
            item["id"] for item in baseline.context["matches"]
            if item["slug"].startswith("den-demo-")
        }
        self.assertEqual(len(demo_ids), 18)
        self.assertIn(self.existing_profile.pk, all_approved_ids)

        floral_category = Category.objects.get(name="Bouquets")
        floral_tag = VendorTag.objects.get(name="Floral decoration", kind=VendorTag.Kind.SERVICE)
        filters = [
            {"category": floral_category.pk},
            {"service_tag": floral_tag.pk},
            {"location": "North York"},
            {"price_min": "1000"},
            {"help_types": [EventRequest.HelpType.OTHER], "other_help_text": "Floral arches"},
        ]
        for query in filters:
            filtered = self.client.get(url, query)
            filtered_demo_ids = {
                item["id"] for item in filtered.context["matches"]
                if item["slug"].startswith("den-demo-")
            }
            self.assertLess(len(filtered_demo_ids), len(demo_ids), query)
            self.assertTrue(filtered_demo_ids.issubset(demo_ids), query)

        cleared = self.client.get(url)
        self.assertEqual({item["id"] for item in cleared.context["matches"]}, all_approved_ids)
        self.assertEqual(
            self.existing_profile.listings.get().title,
            "Existing decor service",
        )