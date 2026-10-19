from django.test import Client, TestCase
from django.urls import reverse

from accounts.models import User
from core.models import EventRequest, Review, VendorProfile


class SavedSearchDeleteTests(TestCase):
    def setUp(self):
        self.customer = User.objects.create_user(email="search-owner@example.com", role=User.Role.CUSTOMER)
        self.other = User.objects.create_user(email="search-other@example.com", role=User.Role.CUSTOMER)
        self.vendor = User.objects.create_user(email="search-vendor@example.com", role=User.Role.VENDOR)
        self.event = EventRequest.objects.create(customer=self.customer, event_type="BIRTHDAY", status="READY", completed_step=6)
        self.url = reverse("core:event-search-delete", args=[self.event.pk])
        self.client.force_login(self.customer)

    def test_confirmation_and_cancel_do_not_remove_search(self):
        self.assertContains(self.client.get(reverse("core:customer-dashboard")), self.url)
        response = self.client.get(self.url)
        self.assertContains(response, "Keep search")
        self.assertContains(response, 'name="csrfmiddlewaretoken"')
        self.event.refresh_from_db()
        self.assertEqual(self.event.status, "READY")

    def test_confirm_removes_only_this_search_and_keeps_reviews(self):
        other_event = EventRequest.objects.create(customer=self.customer)
        profile, _ = VendorProfile.objects.get_or_create(user=self.vendor, defaults={"business_name": "Review vendor", "slug": "review-vendor"})
        review = Review.objects.create(event=self.event, vendor=profile, rating=5, comment="Great service")
        response = self.client.post(self.url)
        self.assertRedirects(response, reverse("core:customer-dashboard"))
        self.event.refresh_from_db()
        self.assertEqual(self.event.status, "ARCHIVED")
        self.assertTrue(Review.objects.filter(pk=review.pk).exists())
        self.assertNotContains(self.client.get(reverse("core:customer-dashboard")), self.url)
        other_event.refresh_from_db()
        self.assertEqual(other_event.status, "DRAFT")
        self.assertEqual(self.client.get(reverse("core:event-matches", args=[self.event.pk])).status_code, 404)

    def test_draft_search_can_be_removed(self):
        self.event.status = "DRAFT"
        self.event.save()
        self.assertEqual(self.client.post(self.url).status_code, 302)
        self.event.refresh_from_db()
        self.assertEqual(self.event.status, "ARCHIVED")

    def test_another_customer_cannot_read_or_remove_search(self):
        self.client.force_login(self.other)
        self.assertEqual(self.client.get(self.url).status_code, 404)
        self.assertEqual(self.client.post(self.url).status_code, 404)
        self.event.refresh_from_db()
        self.assertEqual(self.event.status, "READY")

    def test_vendor_and_anonymous_access_are_blocked(self):
        self.client.force_login(self.vendor)
        self.assertEqual(self.client.post(self.url).status_code, 403)
        self.client.logout()
        self.assertEqual(self.client.post(self.url).status_code, 302)
        self.event.refresh_from_db()
        self.assertEqual(self.event.status, "READY")

    def test_post_requires_csrf(self):
        client = Client(enforce_csrf_checks=True)
        client.force_login(self.customer)
        self.assertEqual(client.post(self.url).status_code, 403)
        self.event.refresh_from_db()
        self.assertEqual(self.event.status, "READY")
