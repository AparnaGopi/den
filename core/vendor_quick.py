"""Small vendor profiles use the same service vocabulary as customer discovery."""
from django import forms
from django.db import transaction
from django.utils.text import slugify

from .event_rules import normalize_event_location, resolve_event_location
from .forms import MultipleImageField, WEB_HELP_CHOICES
from .models import EventRequest, Listing, PortfolioEntry, ServiceLocation, VendorProfile


class QuickVendorForm(forms.ModelForm):
    help_types = forms.MultipleChoiceField(choices=WEB_HELP_CHOICES, widget=forms.CheckboxSelectMultiple, label="Things you do")
    pictures = MultipleImageField(required=False, label="Pictures of your work")

    class Meta:
        model = VendorProfile
        fields = ("business_name", "profile_image", "short_description", "help_types", "other_services", "city", "service_locations")
        labels = {"business_name": "Company name", "profile_image": "Logo (optional)", "short_description": "Short description", "service_locations": "Other areas you serve (optional)", "other_services": "Other services — please specify"}
        widgets = {"short_description": forms.Textarea(attrs={"rows": 3, "maxlength": 500}), "other_services": forms.Textarea(attrs={"rows": 2}), "city": forms.TextInput(attrs={"list": "vendor-cities"}), "service_locations": forms.CheckboxSelectMultiple}

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["short_description"].required = True
        self.fields["city"].required = True
        self.fields["service_locations"].queryset = ServiceLocation.objects.filter(is_active=True)
        if not self.is_bound and not self.instance.help_types:
            self.initial["help_types"] = list(dict.fromkeys(value for listing in self.instance.listings.all() for value in listing.help_types if value in dict(WEB_HELP_CHOICES)))

    def clean_city(self):
        city = self.cleaned_data["city"].strip()
        if city == self.instance.city and not resolve_event_location(city):
            return city
        if not resolve_event_location(city):
            raise forms.ValidationError("Choose a city in the Greater Toronto Area.")
        return normalize_event_location(city)

    def clean(self):
        data = super().clean()
        data["help_types"] = list(dict.fromkeys(data.get("help_types", [])))
        if EventRequest.HelpType.OTHER in data["help_types"] and not (data.get("other_services") or "").strip():
            self.add_error("other_services", "Tell customers what other services you provide.")
        return data

    @transaction.atomic
    def save(self, commit=True):
        profile = super().save(commit=False)
        base = slugify(profile.business_name)[:155] or f"vendor-{profile.user_id}"
        profile.slug = base if not VendorProfile.objects.exclude(pk=profile.pk).filter(slug=base).exists() else f"{base}-{profile.user_id}"
        if not profile.description:
            profile.description = profile.short_description
        if commit:
            profile.save()
            self.save_m2m()
            for image in self.cleaned_data["pictures"]:
                PortfolioEntry.objects.create(profile=profile, image=image)
            sync_profile_listings(profile)
        return profile


def sync_profile_listings(profile):
    # Existing hand-written packages and prices are never overwritten.
    groups = {
        Listing.ListingType.SERVICE: [value for value in profile.help_types if value != EventRequest.HelpType.RENTAL_ITEMS],
        Listing.ListingType.RENTAL: [value for value in profile.help_types if value == EventRequest.HelpType.RENTAL_ITEMS],
    }
    labels = dict(WEB_HELP_CHOICES)
    for kind, values in groups.items():
        if not values:
            profile.listings.filter(is_profile_listing=True, listing_type=kind).update(is_active=False)
            continue
        Listing.objects.update_or_create(profile=profile, is_profile_listing=True, listing_type=kind, defaults={
            "title": ", ".join(str(labels[value]) for value in values)[:160], "help_types": values,
            "description": profile.short_description + ("\n" + profile.other_services if EventRequest.HelpType.OTHER in values else ""),
            "category": profile.primary_category, "pricing_type": Listing.PricingType.CONTACT_FOR_QUOTE, "price": None, "is_active": True,
        })


def vendor_quick_manage(request):
    from django.contrib import messages
    from django.shortcuts import redirect, render
    from .views import get_vendor_profile, vendor_only
    vendor_only(request)
    profile = get_vendor_profile(request.user)
    if request.method == "POST":
        profile = VendorProfile.objects.select_for_update().get(pk=profile.pk)
    form = QuickVendorForm(request.POST if request.method == "POST" else None, request.FILES if request.method == "POST" else None, instance=profile)
    if request.method == "POST" and form.is_valid():
        form.save()
        messages.success(request, "Your company details and photos are saved.")
        return redirect("core:vendor-profile-preview")
    return render(request, "core/vendor_quick_profile.html", {"profile": profile, "form": form, "cities": ServiceLocation.objects.filter(is_active=True)})
