from io import BytesIO

from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase, override_settings
from django.urls import reverse
from PIL import Image
from rest_framework.test import APIClient

from accounts.models import User
from core.models import Category, Listing, PortfolioEntry, ServiceLocation, VendorProfile
from core.vendor_wizard import get_draft


def photo(name='wizard.png'):
    stream = BytesIO()
    Image.new('RGB', (12, 12), 'blue').save(stream, format='PNG')
    return SimpleUploadedFile(name, stream.getvalue(), content_type='image/png')


@override_settings(STORAGES={'default': {'BACKEND': 'django.core.files.storage.InMemoryStorage'}, 'staticfiles': {'BACKEND': 'django.contrib.staticfiles.storage.StaticFilesStorage'}})
class GuidedVendorTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(email='guided@example.test', role='vendor')
        self.client.force_login(self.user)
        self.api = APIClient()
        self.api.force_authenticate(self.user)
        self.api_url = reverse('api-v1:vendor-onboarding')
        self.web_url = reverse('core:vendor-profile-manage')
        self.category = Category.objects.get(slug='table-styling')
        self.area = ServiceLocation.objects.create(name='Guided Toronto')
        self.state = self.api.get(self.api_url).data

    def send(self, step, action='next', answers=None, **extra):
        response = self.api.post(self.api_url, {'step': step, 'action': action, 'revision': self.state['revision'], 'answers': answers or {}, **extra}, format='json')
        if 'revision' in response.data:
            self.state = response.data
        return response

    def business(self):
        return dict(business_name='Guided Studio', description='Decor for celebrations.', contact_first_name='Ari', contact_last_name='Lee', business_email='studio@example.test', phone='416-555-0123', website_url='', instagram_url='', google_business_url='', remove_logo=False)

    def finish_answers(self):
        for step, answers in [
            (1, self.business()),
            (2, {'vendor_type': 'DECORATOR', 'specific_services': [str(self.category.pk)], 'other_enabled': False, 'other_services': ''}),
            (3, {'city': 'Toronto', 'service_locations': [str(self.area.pk)], 'service_area': '', 'business_address': 'Private street', 'max_travel_distance': '50'}),
            (4, {'pricing_type': 'FIXED', 'price': '225.50'}),
            (5, {}),
        ]:
            response = self.send(step, answers=answers)
            self.assertEqual(response.status_code, 200, response.data)
        self.assertEqual(self.state['step'], 6)

    def test_full_mobile_api_flow_resume_review_edit_submit(self):
        self.finish_answers()
        profile = VendorProfile.objects.get(user=self.user)
        self.assertEqual(profile.approval_status, 'DRAFT')
        self.assertEqual(profile.description, '')
        self.assertFalse(profile.listings.exists())
        self.assertEqual(self.client.get(self.web_url).context['step'], 6)
        response = self.send(6, 'goto', target=1)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(self.state['answers']['business_name'], 'Guided Studio')
        self.send(1, 'save', {'business_name': 'Updated Studio'})
        self.assertEqual(self.api.get(self.api_url).data['answers']['business_name'], 'Updated Studio')
        self.send(1, 'goto', target=6)
        review = str(self.state['review'])
        self.assertIn('Updated Studio', review)
        self.assertIn('225.50', review)
        self.assertEqual(self.send(6, 'submit').status_code, 200)
        profile.refresh_from_db()
        self.assertEqual(profile.business_name, 'Updated Studio')
        self.assertEqual(profile.approval_status, 'PENDING')
        self.assertEqual(profile.primary_category, self.category)
        self.assertEqual(str(profile.listings.get().price), '225.50')
        self.assertEqual(profile.service_locations.get(), self.area)
        self.assertEqual(profile.service_tags.get().name, self.category.name)
        self.assertEqual(self.send(6, 'submit').status_code, 200)
        self.assertEqual(profile.listings.count(), 1)
        self.assertEqual(self.client.get(reverse('core:vendor-profile', args=[profile.slug])).status_code, 404)

    def test_incomplete_and_invalid_answers_saved_but_cannot_advance_or_submit(self):
        result = self.send(1, 'next', {'business_name': 'Half complete', 'business_email': 'not-an-email'})
        self.assertEqual(result.status_code, 400)
        self.assertIn('business_email', result.data['errors'])
        self.assertEqual(self.state['step'], 1)
        self.assertEqual(self.api.get(self.api_url).data['answers']['business_name'], 'Half complete')
        self.assertEqual(self.send(1, 'goto', target=6).status_code, 400)
        self.assertEqual(self.send(6, 'submit').status_code, 400)
        self.assertEqual(VendorProfile.objects.get(user=self.user).approval_status, 'DRAFT')

    def test_service_dependency_other_and_quote_validation(self):
        self.send(1, answers=self.business())
        floral = Category.objects.get(slug='bouquets')
        result = self.send(2, answers={'vendor_type': 'DECORATOR', 'specific_services': [str(floral.pk)]})
        self.assertEqual(result.status_code, 400)
        self.assertIn('specific_services', result.data['errors'])
        self.assertEqual(self.send(2, answers={'vendor_type': 'OTHER', 'specific_services': [], 'other_enabled': True, 'other_services': ''}).status_code, 400)
        self.assertEqual(self.send(2, answers={'other_services': 'Custom installations'}).status_code, 200)
        self.assertEqual(self.send(3, answers={'city': 'Toronto', 'service_area': 'GTA'}).status_code, 200)
        for price in ('', '-1', 'abc', '1.001', 'NaN', 'Infinity'):
            result = self.send(4, answers={'pricing_type': 'HOURLY', 'price': price})
            self.assertEqual(result.status_code, 400, price)
        self.assertEqual(self.send(4, answers={'pricing_type': 'CONTACT_FOR_QUOTE', 'price': '180'}).status_code, 200)
        self.send(5)
        self.assertEqual(self.send(6, 'submit').status_code, 200)
        profile = VendorProfile.objects.get(user=self.user)
        self.assertEqual(profile.other_services, 'Custom installations')
        self.assertIsNone(profile.listings.get().price)
        self.assertEqual(profile.primary_category.slug, 'other-vendor-services')

    def test_uploads_persist_in_draft_and_submit_once(self):
        import json
        response = self.api.post(self.api_url, {'step': '1', 'action': 'next', 'revision': self.state['revision'], 'answers': json.dumps(self.business()), 'logo': photo()}, format='multipart')
        self.assertEqual(response.status_code, 200, response.data)
        self.state = response.data
        self.assertTrue(self.state['logo_url'])
        self.finish_answers()
        self.send(6, 'goto', target=5)
        response = self.api.post(self.api_url, {'step': '5', 'action': 'next', 'revision': self.state['revision'], 'answers': json.dumps({'caption': 'Celebration'}), 'cover': photo('cover.png'), 'photos': [photo('a.png'), photo('b.png')]}, format='multipart')
        self.assertEqual(response.status_code, 200, response.data)
        self.state = response.data
        profile = VendorProfile.objects.get(user=self.user)
        self.assertFalse(profile.profile_image)
        self.assertEqual(profile.portfolio_entries.count(), 0)
        self.assertEqual(len(self.api.get(self.api_url).data['photos']), 2)
        self.assertEqual(self.send(6, 'submit').status_code, 200)
        profile.refresh_from_db()
        self.assertTrue(profile.profile_image)
        self.assertTrue(profile.cover_image)
        self.assertEqual(profile.portfolio_entries.count(), 2)
        self.send(6, 'submit')
        self.assertEqual(profile.portfolio_entries.count(), 2)

    def test_bad_upload_and_stale_revision_do_not_overwrite_saved_answers(self):
        bad = SimpleUploadedFile('bad.png', b'not an image', content_type='image/png')
        response = self.api.post(self.api_url, {'step': '1', 'action': 'save', 'revision': self.state['revision'], 'answers': '{}', 'logo': bad}, format='multipart')
        self.assertEqual(response.status_code, 400)
        old_revision = self.state['revision']
        self.send(1, 'save', {'business_name': 'Newest'})
        response = self.api.post(self.api_url, {'step': 1, 'action': 'save', 'revision': old_revision, 'answers': {'business_name': 'Stale'}}, format='json')
        self.assertEqual(response.status_code, 409)
        self.assertEqual(self.api.get(self.api_url).data['answers']['business_name'], 'Newest')
        self.assertEqual(self.send(1, 'save', {'approval_status': 'APPROVED'}).status_code, 400)
        self.assertEqual(self.send(1, 'save', {'business_name': {'nested': 'invalid'}}).status_code, 400)

    def test_django_form_complete_flow_back_preserves_values_and_server_validation(self):
        self.assertContains(self.client.get(self.web_url), 'Step 1 of 6')
        self.assertContains(self.client.get(self.web_url), 'Company logo')
        def post(step, action, answers=None, **extra):
            data = {'wizard': '1', 'step': step, 'action': action, 'revision': self.api.get(self.api_url).data['revision'], **(answers or {}), **extra}
            return self.client.post(self.web_url, data, follow=True)
        invalid = post(1, 'next', {'business_name': 'Started'})
        self.assertEqual(invalid.status_code, 400)
        self.assertContains(invalid, 'Started', status_code=400)
        business = self.business()
        business.pop('remove_logo')
        self.assertContains(post(1, 'next', business), 'Step 2 of 6')
        self.assertContains(post(2, 'next', {'vendor_type': 'DECORATOR', 'specific_services': [self.category.pk]}), 'Step 3 of 6')
        self.assertContains(post(3, 'back', {'city': 'Toronto', 'service_area': 'GTA'}), 'Step 2 of 6')
        self.assertContains(post(2, 'next', {'vendor_type': 'DECORATOR', 'specific_services': [self.category.pk]}), 'GTA')
        self.assertContains(post(3, 'next', {'city': 'Toronto', 'service_area': 'GTA'}), 'Step 4 of 6')
        self.assertContains(post(4, 'next', {'pricing_type': 'PER_PERSON', 'price': '75'}), 'Step 5 of 6')
        self.assertContains(post(5, 'next', {'photos': photo(), 'caption': 'Web portfolio'}), 'Edit Business')
        review = self.client.get(self.web_url)
        self.assertContains(review, 'Web portfolio')
        self.assertContains(review, 'Guided Studio')
        self.assertContains(post(6, 'submit'), 'Submitted for admin approval')
        profile = VendorProfile.objects.get(user=self.user)
        self.assertEqual(profile.approval_status, 'PENDING')
        self.assertEqual(profile.portfolio_entries.count(), 1)

    def test_existing_toronto_profile_hidden_fields_media_and_other_listings_survive(self):
        profile = VendorProfile.objects.get(user=self.user)
        profile.onboarding_draft.delete()
        profile.business_name = 'Toronto Decor Den'
        profile.slug = 'toronto-decor-den'
        profile.primary_category = self.category
        profile.description = 'Original description'
        profile.short_description = 'Original summary'
        profile.tags = 'existing-data'
        profile.services_answer = 'Original services story'
        profile.style_answer = 'Warm and modern'
        profile.languages = 'English, French'
        profile.years_experience = 12
        profile.availability = 'Weekends'
        profile.approval_status = 'APPROVED'
        profile.save()
        extra = Category.objects.get(slug='backdrops')
        profile.additional_categories.add(extra)
        first = Listing.objects.create(profile=profile, category=self.category, listing_type='SERVICE', title='Existing decor package', description='Saved listing description', pricing_type='FIXED', price=500)
        second = Listing.objects.create(profile=profile, category=extra, listing_type='RENTAL', title='Backdrop rental', description='Keep me', pricing_type='PER_ITEM', price=200)
        portfolio = PortfolioEntry.objects.create(profile=profile, image=photo(), caption='Original photo')
        before = {field.name: str(getattr(profile, field.name)) for field in profile._meta.fields}
        self.state = self.api.get(self.api_url).data
        self.assertEqual(self.state['answers']['description'], 'Original description')
        self.assertEqual(self.state['answers']['price'], '500.00')
        self.send(1, 'save', {'business_name': 'Unsubmitted name'})
        profile.refresh_from_db()
        self.assertEqual({field.name: str(getattr(profile, field.name)) for field in profile._meta.fields}, before)
        self.finish_answers()
        self.send(6, 'submit')
        profile.refresh_from_db(); first.refresh_from_db(); second.refresh_from_db()
        for field in ('short_description', 'tags', 'services_answer', 'style_answer', 'languages', 'years_experience', 'availability', 'slug'):
            self.assertEqual(str(getattr(profile, field)), before[field], field)
        self.assertEqual(second.title, 'Backdrop rental')
        self.assertEqual(second.price, 200)
        self.assertEqual(first.title, 'Existing decor package')
        self.assertEqual(first.description, 'Saved listing description')
        self.assertTrue(profile.portfolio_entries.filter(pk=portfolio.pk).exists())

    def test_portfolio_removal_is_owned_and_deferred_until_submission(self):
        self.finish_answers()
        profile = VendorProfile.objects.get(user=self.user)
        saved = PortfolioEntry.objects.create(profile=profile, image=photo(), caption='Keep until submitted')
        self.send(6, 'goto', target=5)
        self.assertEqual(self.send(5, 'remove_photo', photo_id=f'saved-{saved.pk}').status_code, 200)
        self.assertTrue(PortfolioEntry.objects.filter(pk=saved.pk).exists())
        self.assertFalse(self.state['photos'])
        self.assertEqual(self.send(5, 'remove_photo', photo_id='saved-999999').status_code, 400)
        self.send(5)
        self.assertEqual(self.send(6, 'submit').status_code, 200)
        self.assertFalse(PortfolioEntry.objects.filter(pk=saved.pk).exists())

    def test_ownership_and_customer_denial(self):
        other = User.objects.create_user(email='other-guided@example.test', role='vendor')
        self.send(1, 'save', {'business_name': 'Private draft'})
        self.api.force_authenticate(other)
        self.assertNotEqual(self.api.get(self.api_url).data['answers']['business_name'], 'Private draft')
        customer = User.objects.create_user(email='customer-guided@example.test', role='customer')
        self.api.force_authenticate(customer)
        self.assertEqual(self.api.get(self.api_url).status_code, 403)
        self.assertEqual(self.api.post(self.api_url, {}, format='json').status_code, 403)
        self.api.force_authenticate(None)
        self.assertEqual(self.api.get(self.api_url).status_code, 401)
