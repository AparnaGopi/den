from django.db import IntegrityError, transaction
from django.test import Client, TestCase
from django.urls import reverse

from accounts.models import User
from .models import VendorProfile


class VendorApprovalSynchronizationTests(TestCase):
    def setUp(self):
        self.vendor = User.objects.create_user(email="approval-vendor@example.com", role=User.Role.VENDOR)
        self.other_vendor = User.objects.create_user(email="approval-other@example.com", role=User.Role.VENDOR)
        self.profile = VendorProfile.objects.create(user=self.vendor, business_name="Approval Studio", slug="approval-studio", approval_status=VendorProfile.ApprovalStatus.PENDING)
        self.other_profile = VendorProfile.objects.create(user=self.other_vendor, business_name="Other Studio", slug="other-studio", approval_status=VendorProfile.ApprovalStatus.APPROVED)
        self.admin = User.objects.create_superuser(email="approval-admin@example.com", password="test-password")
        self.client.force_login(self.vendor)
        self.admin_client = Client()
        self.admin_client.force_login(self.admin)
        self.dashboard_url = reverse("core:vendor-dashboard")
        self.public_url = reverse("core:vendor-profile", args=[self.profile.slug])

    def test_admin_approval_action_is_visible_on_next_request(self):
        before = self.client.get(self.dashboard_url)
        self.assertContains(before, "pending review")
        self.assertNotContains(before, self.public_url)
        response = self.admin_client.post(reverse("admin:core_vendorprofile_changelist"), {
            "action": "approve_profiles", "_selected_action": [self.profile.pk], "index": "0",
        })
        self.assertEqual(response.status_code, 302)
        self.profile.refresh_from_db()
        self.assertEqual(self.profile.approval_status, VendorProfile.ApprovalStatus.APPROVED)
        after = self.client.get(self.dashboard_url)
        self.assertEqual(after.context["vendor_profile"].pk, self.profile.pk)
        self.assertContains(after, '<span class="approval-badge">Approved</span>', html=True)
        self.assertContains(after, self.public_url)
        self.assertNotContains(after, "approval-note")
        self.assertNotContains(after, "pending review")
        self.assertEqual(self.client.get(self.public_url).status_code, 200)
        self.assertFalse(any("approval" in key for key in self.client.session.keys()))

    def test_admin_edit_saves_same_status_field(self):
        self.client.get(self.dashboard_url)
        response = self.admin_client.post(reverse("admin:core_vendorprofile_change", args=[self.profile.pk]), {
            "user": self.vendor.pk, "business_name": self.profile.business_name,
            "slug": self.profile.slug, "city": "Toronto", "service_area": "Toronto",
            "description": "Event services", "years_experience": 0,
            "approval_status": VendorProfile.ApprovalStatus.APPROVED, "_save": "Save",
            "portfolio_entries-TOTAL_FORMS": 0, "portfolio_entries-INITIAL_FORMS": 0,
            "portfolio_entries-MIN_NUM_FORMS": 0, "portfolio_entries-MAX_NUM_FORMS": 1000,
            "listings-TOTAL_FORMS": 0, "listings-INITIAL_FORMS": 0,
            "listings-MIN_NUM_FORMS": 0, "listings-MAX_NUM_FORMS": 1000,
        })
        self.assertEqual(response.status_code, 302)
        self.profile.refresh_from_db()
        self.assertEqual(self.profile.approval_status, VendorProfile.ApprovalStatus.APPROVED)
        self.assertContains(self.client.get(self.dashboard_url), self.public_url)

    def test_every_status_is_read_from_current_vendor_database_record(self):
        messages = {
            VendorProfile.ApprovalStatus.PENDING: "pending review",
            VendorProfile.ApprovalStatus.REJECTED: "was rejected",
            VendorProfile.ApprovalStatus.DRAFT: "is a draft",
        }
        for status, message in messages.items():
            with self.subTest(status=status):
                VendorProfile.objects.filter(pk=self.profile.pk).update(approval_status=status)
                response = self.client.get(self.dashboard_url)
                self.assertEqual(response.context["vendor_profile"].user_id, self.vendor.pk)
                self.assertContains(response, message)
                self.assertContains(response, f'<span class="approval-badge">{status.label}</span>', html=True)
                self.assertNotContains(response, self.public_url)
                self.assertEqual(self.client.get(self.public_url).status_code, 404)

    def test_approving_another_vendor_does_not_approve_current_vendor(self):
        self.admin_client.post(reverse("admin:core_vendorprofile_changelist"), {
            "action": "approve_profiles", "_selected_action": [self.other_profile.pk], "index": "0",
        })
        self.assertContains(self.client.get(self.dashboard_url), "pending review")

    def test_duplicate_vendor_profiles_are_rejected_by_database(self):
        with self.assertRaises(IntegrityError), transaction.atomic():
            VendorProfile.objects.create(user=self.vendor, business_name="Duplicate", slug="duplicate")
