from datetime import date, datetime
from unittest.mock import patch

from django.test import TestCase
from django.urls import reverse
from rest_framework.test import APITestCase

from accounts.models import User
from core.event_rules import EVENT_LOCATIONS, TORONTO_TIME_ZONE, toronto_today
from core.forms import EventDiscoveryForm
from core.models import Category, EventRequest


class EventLocationRuleTests(TestCase):
    def setUp(self):
        self.customer = User.objects.create_user(email="rules-web@example.com", role=User.Role.CUSTOMER)
        self.category = Category.objects.create(name="Planning", slug="planning")
        self.client.force_login(self.customer)
        self.payload = {
            "event_type": "WEDDING", "custom_event_type": "", "event_date": "2026-11-14",
            "city": "Toronto", "postal_code": "", "guest_count": "40", "budget_min": "100",
            "budget_max": "1000", "help_types": ["PLANNER"],
            "required_categories": [self.category.pk], "theme": "", "colours": "",
            "venue_type": "UNDECIDED", "notes": "",
        }

    @patch("core.event_rules.datetime")
    def test_server_today_uses_the_toronto_timezone(self, datetime_mock):
        datetime_mock.now.return_value = datetime(2026, 9, 25, 0, 30)
        self.assertEqual(toronto_today(), date(2026, 9, 25))
        datetime_mock.now.assert_called_once_with(TORONTO_TIME_ZONE)

    @patch("core.forms.toronto_today", return_value=date(2026, 9, 25))
    def test_web_form_rejects_yesterday_and_today_but_accepts_tomorrow(self, _today):
        for candidate, valid in (("2026-09-24", False), ("2026-09-25", False), ("2026-09-26", True)):
            form = EventDiscoveryForm(data={**self.payload, "event_date": candidate})
            self.assertEqual(form.is_valid(), valid, form.errors)
            if not valid:
                self.assertEqual(form.errors["event_date"], ["Please choose a date after today."])

    def test_web_form_suggests_supported_locations_and_normalizes_known_alias(self):
        response = self.client.get(reverse("core:event-discovery"))
        self.assertContains(response, '<datalist id="gta-locations">')
        self.assertContains(response, 'value="North York"')
        form = EventDiscoveryForm(data={**self.payload, "city": " north   york "})
        self.assertTrue(form.is_valid(), form.errors)
        self.assertEqual(form.cleaned_data["city"], "North York")
        unsupported = EventDiscoveryForm(data={**self.payload, "city": "Ottawa"})
        self.assertFalse(unsupported.is_valid())
        self.assertEqual(unsupported.errors["city"], ["Den currently supports events within the Greater Toronto Area."])

    def test_unchanged_legacy_location_and_expired_date_do_not_block_other_edits(self):
        event = EventRequest.objects.create(
            customer=self.customer, event_type="WEDDING", event_date=date(2026, 9, 24),
            city="Smallville", status=EventRequest.Status.DRAFT,
        )
        data = {**self.payload, "event_date": "2026-09-24", "city": "Smallville", "notes": "Updated"}
        with patch("core.forms.toronto_today", return_value=date(2026, 9, 25)):
            form = EventDiscoveryForm(data=data, instance=event)
            self.assertTrue(form.is_valid(), form.errors)

    def test_dashboard_formats_iso_date_and_normalizes_known_city_spelling(self):
        EventRequest.objects.create(
            customer=self.customer, event_type="WEDDING", event_date=date(2026, 11, 14),
            city="north york", status=EventRequest.Status.DRAFT, completed_step=2,
        )
        response = self.client.get(reverse("core:customer-dashboard"))
        self.assertContains(response, "Nov 14, 2026 | North York")
        self.assertContains(response, "Draft | 2/6 steps")

    @patch("core.event_rules.toronto_today", return_value=date(2026, 9, 25))
    def test_web_date_picker_uses_tomorrow_as_its_minimum(self, _today):
        form = EventDiscoveryForm()
        self.assertEqual(form.fields["event_date"].widget.input_type, "date")
        self.assertEqual(form.fields["event_date"].widget.attrs["min"], "2026-09-26")


class EventLocationAPIRuleTests(APITestCase):
    def setUp(self):
        self.customer = User.objects.create_user(email="rules-api@example.com", role=User.Role.CUSTOMER)
        self.client.force_authenticate(self.customer)
        self.event = EventRequest.objects.create(
            customer=self.customer, event_date=date(2026, 10, 1), city="North York",
        )
        self.url = reverse("api-v1:event-detail", args=[self.event.pk])

    @patch("core.api.serializers.toronto_today", return_value=date(2026, 9, 25))
    def test_api_rejects_yesterday_and_today_but_accepts_tomorrow(self, _today):
        for candidate, expected_status in (("2026-09-24", 400), ("2026-09-25", 400), ("2026-09-26", 200)):
            response = self.client.patch(self.url, {"event_date": candidate}, format="json")
            self.assertEqual(response.status_code, expected_status, response.data)
            if expected_status == 400:
                self.assertEqual(response.data["event_date"][0], "Please choose a date after today.")
            self.event.refresh_from_db()
            self.event.event_date = date(2026, 9, 24)
            self.event.save(update_fields=["event_date"])

    @patch("core.api.serializers.toronto_today", return_value=date(2026, 9, 25))
    def test_expired_event_accepts_unrelated_patch_and_unchanged_legacy_city(self, _today):
        self.event.event_date = date(2026, 9, 24)
        self.event.save(update_fields=["event_date"])
        response = self.client.patch(self.url, {"theme": "Garden"}, format="json")
        self.assertEqual(response.status_code, 200, response.data)
        response = self.client.patch(self.url, {"event_date": "2026-09-24", "city": "North York"}, format="json")
        self.assertEqual(response.status_code, 200, response.data)

    def test_location_catalog_is_shared_and_city_ids_are_validated(self):
        response = self.client.get(reverse("api-v1:event-locations"))
        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.data), len(EVENT_LOCATIONS))
        north_york = next(location for location in response.data if location["id"] == "north-york")
        self.assertEqual(north_york["canonical_id"], "toronto")
        self.assertEqual(north_york["label"], "North York")

        response = self.client.patch(self.url, {"city": "north-york"}, format="json")
        self.assertEqual(response.status_code, 200, response.data)
        self.event.refresh_from_db()
        self.assertEqual(self.event.city, "North York")
        response = self.client.patch(self.url, {"city": "mississauga"}, format="json")
        self.assertEqual(response.status_code, 200, response.data)
        self.event.refresh_from_db()
        self.assertEqual(self.event.city, "Mississauga")
        response = self.client.patch(self.url, {"city": "ottawa"}, format="json")
        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.data["city"][0], "Den currently supports events within the Greater Toronto Area.")

    def test_known_city_names_are_normalized_and_unknown_existing_values_are_preserved(self):
        response = self.client.patch(self.url, {"city": "north york"}, format="json")
        self.assertEqual(response.status_code, 200)
        self.event.refresh_from_db()
        self.assertEqual(self.event.city, "North York")
        self.event.city = "Smallville"
        self.event.save(update_fields=["city"])
        response = self.client.patch(self.url, {"theme": "Updated"}, format="json")
        self.assertEqual(response.status_code, 200)
        self.event.refresh_from_db()
        self.assertEqual(self.event.city, "Smallville")