from datetime import timedelta
from io import BytesIO

from django.core.exceptions import ValidationError
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase, override_settings
from django.urls import reverse
from django.utils import timezone
from PIL import Image
from rest_framework.test import APIClient

from accounts.models import User
from core.forms import WEB_HELP_CHOICES
from core.messaging import SubscriptionRequired, chat_plan, open_customer_chat, send_message, visit_stats
from core.models import ChatMessage, Conversation, EventRequest, Listing, PortfolioEntry, VendorChatSubscription, VendorProfile


@override_settings(STORAGES={"default": {"BACKEND": "django.core.files.storage.InMemoryStorage"}, "staticfiles": {"BACKEND": "django.contrib.staticfiles.storage.StaticFilesStorage"}})
class VendorQuickAndChatTests(TestCase):
    def setUp(self):
        self.owner = User.objects.create_user(email="quick-vendor@example.test", role="vendor")
        self.vendor = VendorProfile.objects.create(user=self.owner, business_name="Quick Studio", slug="quick-studio", city="Toronto", service_area="GTA", short_description="Event decor", description="Event decor", help_types=["DECORATOR"], approval_status="APPROVED")
        self.customers = [User.objects.create_user(email=f"client-{number}@example.test", role="customer") for number in range(5)]
        self.api = APIClient()

    def chat(self, index):
        conversation = open_customer_chat(self.customers[index], self.vendor.pk)
        send_message(self.customers[index], conversation.pk, "Please help with our event.")
        return conversation

    def test_contact_editor_updates_only_contact_details(self):
        self.client.force_login(self.owner)
        url = reverse("core:vendor-profile-manage") + "?contact=1"
        response = self.client.get(url)
        self.assertContains(response, "Save contact details")
        self.assertNotContains(response, 'name="primary_category"')
        response = self.client.post(url, {"contact_details": "1", "business_email": "hello@example.com", "phone": "4165550100", "business_name": "Unwanted change"})
        self.assertEqual(response.status_code, 302)
        self.vendor.refresh_from_db()
        self.assertEqual(self.vendor.business_email, "hello@example.com")
        self.assertEqual(self.vendor.business_name, "Quick Studio")
        self.assertEqual(self.vendor.approval_status, "PENDING")
        self.assertEqual(self.vendor.help_types, ["DECORATOR"])

    def test_contact_editor_validation_and_access(self):
        url = reverse("core:vendor-profile-manage") + "?contact=1"
        self.client.force_login(self.customers[0])
        self.assertEqual(self.client.get(url).status_code, 403)
        self.client.force_login(self.owner)
        response = self.client.post(url, {"contact_details": "1", "business_email": "invalid", "instagram_url": "invalid"})
        self.assertEqual(response.status_code, 200)
        self.assertIn("business_email", response.context["form"].errors)
        self.assertContains(response, 'class="quick-areas" open')

    def image(self, name="work.png"):
        stream = BytesIO()
        Image.new("RGB", (10, 10), "blue").save(stream, format="PNG")
        return SimpleUploadedFile(name, stream.getvalue(), content_type="image/png")

    def test_simple_profile_and_gallery_use_customer_service_tags(self):
        self.client.force_login(self.owner)
        response = self.client.get(reverse("core:vendor-profile-manage"))
        self.assertFalse(response.context["form"].is_bound)
        self.assertContains(response, "Things you do")
        self.assertNotContains(response, 'name="contact_first_name"')
        for value, _ in WEB_HELP_CHOICES:
            self.assertContains(response, f'value="{value}"')
        payload = {"quick_profile": "1", "business_name": "New Simple Studio", "short_description": "Decor and rental items", "city": "Toronto", "help_types": ["DECORATOR", "RENTAL_ITEMS"], "pictures": [self.image(), self.image("second.png")], "profile_image": self.image("logo.png")}
        self.assertEqual(self.client.post(reverse("core:vendor-profile-manage"), payload).status_code, 302)
        self.vendor.refresh_from_db()
        self.assertEqual(self.vendor.help_types, ["DECORATOR", "RENTAL_ITEMS"])
        self.assertEqual(self.vendor.approval_status, "PENDING")
        self.assertEqual(self.vendor.portfolio_entries.count(), 2)
        self.assertEqual(set(self.vendor.listings.values_list("listing_type", flat=True)), {"SERVICE", "RENTAL"})
        self.assertEqual(self.vendor.submission_errors(), {})

    def test_profile_upload_errors_do_not_save_partial_profile(self):
        self.api.force_authenticate(self.owner)
        response = self.api.post(reverse("api-v1:vendor-quick-profile"), {"business_name": "Bad photo", "short_description": "Decor", "city": "Toronto", "help_types": ["DECORATOR"], "pictures": SimpleUploadedFile("fake.png", b"not a photo")}, format="multipart")
        self.assertEqual(response.status_code, 400)
        self.vendor.refresh_from_db()
        self.assertEqual(self.vendor.business_name, "Quick Studio")
        self.assertFalse(PortfolioEntry.objects.filter(profile=self.vendor).exists())

    def test_simple_profile_matches_rental_search_and_preserves_manual_listing(self):
        manual = Listing.objects.create(profile=self.vendor, listing_type="SERVICE", title="Existing package", description="Custom package", pricing_type="FIXED", price=500, help_types=["DECORATOR"])
        self.api.force_authenticate(self.owner)
        payload = {"business_name": "Quick Studio", "short_description": "Rent beautiful props", "city": "Toronto", "help_types": ["RENTAL_ITEMS"]}
        url = reverse("api-v1:vendor-quick-profile")
        self.assertEqual(self.api.post(url, payload, format="json").status_code, 200)
        self.assertEqual(self.api.post(url, payload, format="json").status_code, 200)
        manual.refresh_from_db()
        self.assertEqual(manual.price, 500)
        self.assertEqual(self.vendor.listings.filter(is_profile_listing=True).count(), 1)
        VendorProfile.objects.filter(pk=self.vendor.pk).update(approval_status="APPROVED")
        self.client.force_login(self.customers[0])
        response = self.client.get(reverse("core:vendor-discovery"), {"help_types": "RENTAL_ITEMS"})
        self.assertContains(response, "Quick Studio")

    def test_vendor_has_three_free_clients_not_three_messages(self):
        chats = [self.chat(index) for index in range(4)]
        for chat in chats[:3]:
            send_message(self.owner, chat.pk, "Happy to help!")
        send_message(self.owner, chats[0].pk, "Another message in the same chat")
        self.assertEqual(chat_plan(self.vendor)["free_clients_used"], 3)
        with self.assertRaises(SubscriptionRequired):
            send_message(self.owner, chats[3].pk, "Fourth client")
        self.assertEqual(chats[3].messages.count(), 1)
        send_message(self.customers[3], chats[3].pk, "A customer can still send an enquiry")

    def test_invalid_messages_do_not_consume_trial(self):
        chat = self.chat(0)
        for text in ("  ", "x" * 4001):
            with self.assertRaises(ValidationError):
                send_message(self.owner, chat.pk, text)
        self.assertEqual(chat_plan(self.vendor)["free_clients_remaining"], 3)

    def test_subscription_expiry_and_client_cannot_activate_own_subscription(self):
        chats = [self.chat(index) for index in range(4)]
        for chat in chats[:3]:
            send_message(self.owner, chat.pk, "Hello")
        subscription = VendorChatSubscription.objects.create(vendor=self.vendor, active_until=timezone.now() + timedelta(days=30))
        send_message(self.owner, chats[3].pk, "Subscribed reply")
        subscription.active_until = timezone.now() - timedelta(seconds=1)
        subscription.save()
        with self.assertRaises(SubscriptionRequired):
            send_message(self.owner, chats[3].pk, "Expired")
        send_message(self.owner, chats[0].pk, "Trial conversation remains free")
        self.api.force_authenticate(self.owner)
        self.assertEqual(self.api.post(reverse("api-v1:vendor-chat-plan"), {"active_until": "2099-01-01T00:00:00Z"}).status_code, 200)
        subscription.refresh_from_db()
        self.assertFalse(subscription.is_active)

    def test_inbox_unread_and_message_access(self):
        chat = self.chat(0)
        send_message(self.owner, chat.pk, "A vendor reply")
        self.api.force_authenticate(self.customers[0])
        response = self.api.get(reverse("api-v1:message-list"))
        self.assertEqual(response.data["results"][0]["unread_count"], 1)
        thread_url = reverse("api-v1:message-thread", args=[chat.pk])
        self.assertEqual(len(self.api.get(thread_url).data["messages"]), 2)
        self.assertEqual(self.api.get(reverse("api-v1:message-list")).data["results"][0]["unread_count"], 0)
        self.api.force_authenticate(self.customers[1])
        self.assertEqual(self.api.get(thread_url).status_code, 404)
        self.assertEqual(self.api.post(thread_url, {"body": "Intruder"}).status_code, 404)
        self.api.force_authenticate(None)
        self.assertEqual(self.api.get(thread_url).status_code, 401)

    def test_private_event_details_require_explicit_customer_share(self):
        event = EventRequest.objects.create(customer=self.customers[1], status="READY", notes="Private event")
        self.api.force_authenticate(self.customers[0])
        contact = reverse("api-v1:contact-vendor", args=[self.vendor.pk])
        self.assertEqual(self.api.post(contact, {"event_id": event.pk}).status_code, 404)
        event.customer = self.customers[0]
        event.save()
        response = self.api.post(contact, {"event_id": event.pk})
        self.assertEqual(response.data["event"]["notes"], "Private event")
        chat = Conversation.objects.get(pk=response.data["id"])
        event.status = "ARCHIVED"
        event.save()
        self.assertIsNone(self.api.get(reverse("api-v1:message-thread", args=[chat.pk])).data["conversation"]["event"])

    def test_visits_are_aggregated_and_preview_does_not_count(self):
        url = reverse("core:vendor-profile", args=[self.vendor.slug])
        self.client.force_login(self.customers[0])
        self.assertEqual(self.client.get(url).status_code, 200)
        self.client.get(url)
        self.client.force_login(self.customers[1])
        self.client.get(url)
        self.client.force_login(self.owner)
        self.client.get(url)
        self.client.get(reverse("core:vendor-profile-preview"))
        self.assertEqual(visit_stats(self.vendor)["total_views"], 3)
        self.assertEqual(visit_stats(self.vendor)["unique_customers"], 2)
        self.api.force_authenticate(self.customers[0])
        self.assertEqual(self.api.get(reverse("api-v1:vendor-visit-stats")).status_code, 403)

    def test_unapproved_profiles_cannot_be_contacted(self):
        self.vendor.approval_status = "PENDING"
        self.vendor.save()
        self.api.force_authenticate(self.customers[0])
        self.assertEqual(self.api.post(reverse("api-v1:contact-vendor", args=[self.vendor.pk])).status_code, 404)

    def test_web_chat_reply_is_visible_to_customer_and_escaped(self):
        chat = self.chat(0)
        self.client.force_login(self.owner)
        url = reverse("core:message-thread", args=[chat.pk])
        self.assertRedirects(self.client.post(url, {"body": "<script>alert('hello')</script>"}), url)
        self.client.force_login(self.customers[0])
        inbox = self.client.get(reverse("core:message-inbox"))
        self.assertContains(inbox, "1 unread")
        response = self.client.get(url)
        self.assertContains(response, "&lt;script&gt;")
        self.assertNotContains(response, "<script>alert")
        self.client.force_login(self.customers[1])
        self.assertEqual(self.client.get(url).status_code, 404)
        self.assertEqual(self.client.post(url, {"body": "Intruder"}).status_code, 404)

    def test_fourth_client_reply_returns_payment_required_without_sending(self):
        chats = [self.chat(index) for index in range(4)]
        for chat in chats[:3]:
            send_message(self.owner, chat.pk, "Hello")
        self.api.force_authenticate(self.owner)
        response = self.api.post(reverse("api-v1:message-thread", args=[chats[3].pk]), {"body": "Fourth reply"})
        self.assertEqual(response.status_code, 402)
        self.assertTrue(response.data["subscription_required"])
        self.assertEqual(chats[3].messages.count(), 1)

    def test_invalid_event_reference_and_service_values_return_validation_errors(self):
        self.api.force_authenticate(self.customers[0])
        self.assertEqual(self.api.post(reverse("api-v1:contact-vendor", args=[self.vendor.pk]), {"event_id": "not-an-id"}).status_code, 400)
        self.api.force_authenticate(self.owner)
        url = reverse("api-v1:vendor-quick-profile")
        payload = {"business_name": "Quick Studio", "short_description": "Decor", "city": "Toronto", "help_types": ["NOT_REAL"]}
        self.assertEqual(self.api.post(url, payload, format="json").status_code, 400)

    def test_api_can_save_multiple_photos_and_submit_minimal_profile(self):
        self.api.force_authenticate(self.owner)
        self.vendor.approval_status = "DRAFT"
        self.vendor.save()
        response = self.api.post(reverse("api-v1:vendor-quick-profile"), {"business_name": "Quick Studio", "short_description": "Beautiful decor", "city": "Toronto", "help_types": ["DECORATOR"], "pictures": [self.image(), self.image("extra.png")], "submit": "1"}, format="multipart")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["approval_status"], "PENDING")
        self.assertEqual(len(response.data["photos"]), 2)

    def test_quick_service_entry_matches_customer_category_filter(self):
        from core.models import Category
        from core.vendor_quick import sync_profile_listings
        category = Category.objects.get(slug="table-styling")
        self.vendor.help_types = ["DECORATOR"]
        self.vendor.save()
        sync_profile_listings(self.vendor)
        self.client.force_login(self.customers[0])
        response = self.client.get(reverse("core:vendor-discovery"), {"category": category.pk, "help_types": "DECORATOR"})
        self.assertContains(response, "Quick Studio")
