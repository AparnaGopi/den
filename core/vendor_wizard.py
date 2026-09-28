"""Shared draft, validation and submission logic for the web and mobile wizard."""
from django import forms
from django.core.exceptions import ValidationError
from django.db import transaction
from django.utils import timezone

from .forms import MultipleImageField, WEB_HELP_CHOICES
from .models import (Category, Listing, PortfolioEntry, ServiceLocation, VendorDraftPhoto,
                     VendorOnboardingDraft, VendorProfile, VendorTag, validate_vendor_image)

STEPS = ('Business', 'Services', 'Location', 'Pricing', 'Media', 'Review')
BUSINESS_FIELDS = ('business_name', 'description', 'contact_first_name', 'contact_last_name',
                   'business_email', 'phone', 'website_url', 'instagram_url', 'google_business_url')
LOCATION_FIELDS = ('city', 'service_locations', 'service_area', 'business_address', 'max_travel_distance')
STEP_FIELDS = {
    1: BUSINESS_FIELDS + ('remove_logo',),
    2: ('vendor_type', 'specific_services', 'other_enabled', 'other_services'),
    3: LOCATION_FIELDS,
    4: ('pricing_type', 'price'),
    5: ('remove_cover', 'caption'),
    6: (),
}
LIST_FIELDS = {'specific_services', 'service_locations'}
BOOL_FIELDS = {'other_enabled', 'remove_logo', 'remove_cover'}


def get_draft(profile):
    draft = VendorOnboardingDraft.objects.filter(profile=profile).first()
    if draft:
        return draft
    listing = profile.listings.order_by('pk').first()
    category = profile.primary_category
    vendor_type = profile.vendor_type
    if not vendor_type and category:
        vendor_type = next((value for value, _ in WEB_HELP_CHOICES if value in category.relevant_help_types), 'OTHER')
    answers = {name: getattr(profile, name) for name in BUSINESS_FIELDS + LOCATION_FIELDS if name != 'service_locations'}
    # Reuse a saved short description only when the full description has never been set.
    answers['description'] = profile.description or profile.short_description
    answers.update({
        'vendor_type': vendor_type, 'other_enabled': bool(profile.other_services) or vendor_type == 'OTHER',
        'other_services': profile.other_services,
        'specific_services': [str(pk) for pk in ([profile.primary_category_id] if category else []) + list(profile.additional_categories.values_list('pk', flat=True))],
        'service_locations': [str(pk) for pk in profile.service_locations.values_list('pk', flat=True)],
        'pricing_type': listing.pricing_type if listing else '',
        'price': str(listing.price) if listing and listing.price is not None else '',
        'remove_logo': False, 'remove_cover': False, 'caption': '',
    })
    return VendorOnboardingDraft.objects.get_or_create(profile=profile, defaults={'answers': answers, 'pricing_listing': listing})[0]


def service_choices(draft, vendor_type=None):
    vendor_type = vendor_type if vendor_type is not None else draft.answers.get('vendor_type', '')
    # Existing categories remain explicit choices even if the catalogue was later changed.
    saved_ids = set(draft.profile.additional_categories.values_list('pk', flat=True))
    if draft.profile.primary_category_id:
        saved_ids.add(draft.profile.primary_category_id)
    return [category for category in Category.objects.all()
            if category.is_active and vendor_type in category.relevant_help_types or category.pk in saved_ids]


def step_form(draft, step, data=None):
    answers = draft.answers if data is None else data
    form = forms.Form(data=answers)
    fields = {}
    if step == 1:
        labels = {'business_name': 'Company name', 'description': 'Business description',
                  'contact_first_name': 'Contact first name', 'contact_last_name': 'Contact last name',
                  'business_email': 'Business email', 'phone': 'Phone', 'website_url': 'Website URL',
                  'instagram_url': 'Instagram URL', 'google_business_url': 'Google Business URL'}
        for name in BUSINESS_FIELDS:
            field = VendorProfile._meta.get_field(name).formfield()
            field.label = labels[name]
            field.required = name not in ('website_url', 'instagram_url', 'google_business_url')
            if name == 'description':
                field.max_length = 10000
                field.widget = forms.Textarea(attrs={'rows': 5})
            fields[name] = field
        fields['remove_logo'] = forms.BooleanField(required=False, label='Remove saved logo')
    elif step == 2:
        fields = {
            'vendor_type': forms.ChoiceField(choices=[('', 'Choose vendor type')] + list(WEB_HELP_CHOICES), label='Vendor type'),
            'specific_services': forms.MultipleChoiceField(
                choices=[(str(c.pk), c.name) for c in service_choices(draft, answers.get('vendor_type'))],
                required=False, label='Specific services', help_text='Choose up to four services. Use Other for additional services.', widget=forms.CheckboxSelectMultiple),
            'other_enabled': forms.BooleanField(required=False, label='Other'),
            'other_services': forms.CharField(required=False, max_length=2000, label='Describe other services', widget=forms.Textarea(attrs={'rows': 3})),
        }
    elif step == 3:
        for name in LOCATION_FIELDS:
            field = VendorProfile._meta.get_field(name).formfield()
            field.required = name == 'city'
            fields[name] = field
        selected = draft.profile.service_locations.values_list('pk', flat=True)
        fields['service_locations'] = forms.MultipleChoiceField(
            choices=[(str(c.pk), c.name) for c in ServiceLocation.objects.all() if c.is_active or c.pk in selected],
            required=False, label='Service areas', widget=forms.CheckboxSelectMultiple)
        fields['city'].label = 'Base location'
        fields['service_area'].label = 'Other service areas'
    elif step == 4:
        fields = {
            'pricing_type': forms.ChoiceField(choices=[('', 'Choose pricing type')] + list(Listing.PricingType.choices), label='Pricing type'),
            'price': forms.DecimalField(required=False, min_value=0, max_digits=10, decimal_places=2, label='Price (CAD)'),
        }
        if answers.get('pricing_type') == Listing.PricingType.CONTACT_FOR_QUOTE:
            answers = {**answers, 'price': ''}
            form.data = answers
    elif step == 5:
        fields = {'remove_cover': forms.BooleanField(required=False, label='Remove saved cover photo'),
                  'caption': forms.CharField(required=False, max_length=240, label='Caption for new photos')}
    form.fields = fields
    form.is_valid()
    if step == 2:
        if len(form.cleaned_data.get('specific_services', [])) > 4:
            form.add_error('specific_services', 'Choose up to four services. Use Other for additional services.')
        if not form.cleaned_data.get('specific_services') and not form.cleaned_data.get('other_enabled') and answers.get('vendor_type') != 'OTHER':
            form.add_error('specific_services', 'Choose a service or select Other.')
        if (form.cleaned_data.get('other_enabled') or answers.get('vendor_type') == 'OTHER') and not form.cleaned_data.get('other_services'):
            form.add_error('other_services', 'Describe the other services you provide.')
    if step == 3 and not form.cleaned_data.get('service_locations') and not form.cleaned_data.get('service_area'):
        form.add_error('service_locations', 'Choose a service area or enter another area.')
    if step == 4 and answers.get('pricing_type') != Listing.PricingType.CONTACT_FOR_QUOTE and form.cleaned_data.get('price') is None:
        form.add_error('price', 'Enter a price for this pricing type.')
    return form


def form_errors(form):
    return {name: [str(error) for error in errors] for name, errors in form.errors.items()}


def schema(draft):
    result = []
    for step, title in enumerate(STEPS, 1):
        fields = []
        for name, field in step_form(draft, step).fields.items():
            kind = ('boolean' if isinstance(field, forms.BooleanField) else
                    'tags' if isinstance(field, forms.MultipleChoiceField) else
                    'choice' if isinstance(field, forms.ChoiceField) else
                    'textarea' if isinstance(field.widget, forms.Textarea) else
                    'email' if isinstance(field, forms.EmailField) else
                    'number' if isinstance(field, forms.DecimalField) else 'text')
            fields.append({'name': name, 'label': field.label, 'kind': kind, 'required': field.required,
                           'max_length': getattr(field, 'max_length', None),
                           'choices': [{'value': str(value), 'label': str(label)} for value, label in getattr(field, 'choices', [])]})
        result.append({'number': step, 'title': title, 'fields': fields})
    return result


def image_url(image, request=None):
    if not image:
        return None
    return request.build_absolute_uri(image.url) if request else image.url


def payload(draft, request=None):
    profile = draft.profile
    saved_category_ids = set(profile.additional_categories.values_list('pk', flat=True))
    saved_category_ids.add(profile.primary_category_id)
    sections = schema(draft)
    review = []
    for section in sections[:5]:
        rows = []
        for field in section['fields']:
            key = field['name']
            if key in {'remove_logo', 'remove_cover', 'caption', 'other_enabled'}:
                continue
            if key == 'other_services' and not draft.answers.get('other_enabled') and draft.answers.get('vendor_type') != 'OTHER':
                continue
            if key == 'price' and draft.answers.get('pricing_type') == 'CONTACT_FOR_QUOTE':
                continue
            value = draft.answers.get(key, '')
            choices = {item['value']: item['label'] for item in field['choices']}
            if isinstance(value, list):
                value = ', '.join(choices.get(str(item), str(item)) for item in value)
            else:
                value = choices.get(str(value), value)
            rows.append({'label': field['label'], 'value': value or 'Not provided'})
        review.append({'step': section['number'], 'title': section['title'], 'rows': rows})
    return {
        'answers': draft.answers, 'step': draft.current_step, 'revision': draft.revision, 'sections': sections, 'review': review,
        'approval_status': profile.approval_status, 'approval_label': profile.get_approval_status_display(),
        'review_feedback': profile.review_feedback, 'submitted': bool(draft.submitted_at),
        'logo_url': None if draft.answers.get('remove_logo') else image_url(draft.logo or profile.profile_image, request),
        'cover_url': None if draft.answers.get('remove_cover') else image_url(draft.cover or profile.cover_image, request),
        'photos': [{'id': f'saved-{photo.pk}', 'url': image_url(photo.image, request), 'caption': photo.caption} for photo in profile.portfolio_entries.exclude(pk__in=draft.answers.get('_removed_photos', []))] +
                  [{'id': f'draft-{photo.pk}', 'url': image_url(photo.image, request), 'caption': photo.caption} for photo in draft.photos.all()],
        'pricing_listing_title': draft.pricing_listing.title if draft.pricing_listing else '',
        'service_catalogue': [{'value': str(c.pk), 'label': c.name, 'types': c.relevant_help_types,
                               'saved': c.pk in saved_category_ids}
                              for c in Category.objects.all() if c.is_active or c.pk in saved_category_ids],
    }


def update_draft(draft, *, step, action, answers, files=None, target=None, revision=None, photo_id=None):
    """Caller locks the profile/draft in a transaction. Failed validation still saves answers."""
    if revision != draft.revision:
        return {'__all__': ['This draft changed in another window. Reload before saving.']}, 409
    if step not in STEP_FIELDS or action not in {'save', 'next', 'back', 'goto', 'submit', 'remove_photo'}:
        return {'__all__': ['Choose a valid step and action.']}, 400
    if not isinstance(answers, dict) or set(answers) - set(STEP_FIELDS[step]):
        return {'__all__': ['Send only answers for the current step.']}, 400
    photo_to_remove = None
    if action == 'remove_photo':
        if step != 5 or not isinstance(photo_id, str):
            return {'__all__': ['Choose a photo in the Media step.']}, 400
        kind, _, pk = photo_id.partition('-')
        if kind not in {'saved', 'draft'} or not pk.isdigit():
            return {'__all__': ['Choose a valid photo.']}, 400
        photos = draft.profile.portfolio_entries if kind == 'saved' else draft.photos
        photo_to_remove = photos.filter(pk=int(pk)).first()
        if photo_to_remove is None:
            return {'__all__': ['This photo is not in your portfolio.']}, 400
    normalized = {}
    for name, value in answers.items():
        if name in LIST_FIELDS:
            if not isinstance(value, list) or len(value) > 100 or any(not isinstance(item, (int, str)) or len(str(item)) > 12 for item in value):
                return {name: ['Choose valid options.']}, 400
            normalized[name] = list(dict.fromkeys(map(str, value)))
        elif name in BOOL_FIELDS:
            if not isinstance(value, bool):
                return {name: ['Choose true or false.']}, 400
            normalized[name] = value
        elif not isinstance(value, str) or len(value) > 10000:
            return {name: ['Enter text of at most 10000 characters.']}, 400
        else:
            normalized[name] = value
    files = files or {}
    if set(files) - ({'logo'} if step == 1 else {'cover', 'photos'} if step == 5 else set()):
        return {'__all__': ['Upload images in Business or Media.']}, 400
    cleaned_files = {}
    try:
        for name in ('logo', 'cover'):
            if files.get(name):
                cleaned_files[name] = forms.ImageField(validators=[validate_vendor_image]).clean(files[name])
        if files.get('photos'):
            cleaned_files['photos'] = MultipleImageField().clean(files.getlist('photos'))
    except ValidationError as error:
        return {'__all__': error.messages}, 400
    draft.answers = {**draft.answers, **normalized}
    if draft.answers.get('vendor_type') == 'OTHER':
        draft.answers['other_enabled'] = True
    for name in ('logo', 'cover'):
        if name in cleaned_files:
            setattr(draft, name, cleaned_files[name])
            draft.answers['remove_' + name] = False
    errors, error_step = {}, step
    destination = step
    if action == 'back':
        destination = max(1, step - 1)
    elif action == 'goto':
        if not isinstance(target, int) or target not in STEP_FIELDS:
            return {'__all__': ['Choose a valid destination.']}, 400
        destination = target
    elif action == 'next':
        destination = min(6, step + 1)
    if action == 'submit' or destination > step:
        for number in range(1, 6 if action == 'submit' else destination):
            form = step_form(draft, number)
            if form.errors:
                errors, error_step = form_errors(form), number
                break
    if photo_to_remove is not None:
        if kind == 'saved':
            draft.answers['_removed_photos'] = list(set(draft.answers.get('_removed_photos', []) + [photo_to_remove.pk]))
        else:
            photo_to_remove.delete()
    draft.current_step = error_step if errors else destination
    draft.revision += 1
    if normalized or cleaned_files or photo_to_remove is not None:
        draft.submitted_at = None
    draft.save()
    for photo in cleaned_files.get('photos', []):
        VendorDraftPhoto.objects.create(draft=draft, image=photo, caption=draft.answers.get('caption', '')[:240])
    if errors:
        return errors, 400
    if action == 'submit':
        submit_draft(draft)
    return {}, 200


@transaction.atomic
def submit_draft(draft):
    profile = draft.profile
    cleaned = {}
    for step in range(1, 6):
        form = step_form(draft, step)
        if form.errors:
            raise ValidationError(form_errors(form))
        cleaned.update(form.cleaned_data)
    for name in BUSINESS_FIELDS + LOCATION_FIELDS:
        if name != 'service_locations':
            setattr(profile, name, cleaned[name])
    profile.vendor_type = cleaned['vendor_type']
    profile.other_services = cleaned['other_services'] if cleaned['other_enabled'] else ''
    ids = [int(pk) for pk in cleaned['specific_services']]
    primary_id = profile.primary_category_id if profile.primary_category_id in ids else next(iter(ids), None)
    if not primary_id:
        category, _ = Category.objects.get_or_create(slug='other-vendor-services', defaults={'name': 'Other vendor services'})
        primary_id = category.pk
    profile.primary_category_id = primary_id
    for source, destination in (('logo', 'profile_image'), ('cover', 'cover_image')):
        if cleaned.get('remove_' + source):
            setattr(profile, destination, '')
        elif getattr(draft, source):
            setattr(profile, destination, getattr(draft, source).name)
    profile.approval_status = VendorProfile.ApprovalStatus.PENDING
    profile.save()
    profile.additional_categories.set([pk for pk in ids if pk != primary_id])
    profile.service_locations.set(cleaned['service_locations'])
    # Existing service tags have independent meaning and must not be discarded.
    tags = [VendorTag.objects.get_or_create(name=category.name, kind='SERVICE')[0] for category in Category.objects.filter(pk__in=ids)]
    profile.service_tags.add(*tags)
    listing = draft.pricing_listing
    if listing is None:
        listing = Listing(profile=profile, listing_type=Listing.ListingType.SERVICE,
                          title=f'{profile.business_name} services'[:160], description=profile.description)
    listing.category_id = primary_id
    listing.pricing_type = cleaned['pricing_type']
    listing.price = cleaned['price']
    listing.help_types = list(dict.fromkeys([*listing.help_types, profile.vendor_type]))
    listing.save()
    listing.service_tags.add(*tags)
    profile.portfolio_entries.filter(pk__in=draft.answers.get('_removed_photos', [])).delete()
    draft.answers.pop('_removed_photos', None)
    for photo in draft.photos.all():
        PortfolioEntry.objects.create(profile=profile, image=photo.image.name, caption=photo.caption)
    draft.photos.all().delete()
    draft.pricing_listing = listing
    draft.current_step = 6
    draft.submitted_at = timezone.now()
    draft.save()
