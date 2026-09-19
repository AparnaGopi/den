from django import forms
from django.utils.text import slugify
from django.utils import timezone

from .models import Category, EventRequest, Listing, PortfolioEntry, VendorProfile


class VendorProfileForm(forms.ModelForm):
    primary_category = forms.ModelChoiceField(
        queryset=Category.objects.none(),
        label="Primary category",
        help_text="Choose the category that best describes your business.",
    )
    additional_categories = forms.ModelMultipleChoiceField(
        queryset=Category.objects.none(),
        required=False,
        label="Additional categories",
        help_text="Choose up to three other services you provide.",
        widget=forms.SelectMultiple(attrs={"size": 5}),
    )

    class Meta:
        model = VendorProfile
        fields = (
            "business_name", "primary_category", "additional_categories", "phone", "tags", "city", "service_area", "short_description", "description",
            "years_experience", "languages", "areas_served", "website_url", "instagram_url",
            "google_business_url", "google_place_identifier", "availability", "cover_image", "profile_image",
        )
        widgets = {"short_description": forms.Textarea(attrs={"rows": 3}), "description": forms.Textarea(attrs={"rows": 5}), "availability": forms.Textarea(attrs={"rows": 3})}

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        active_categories = Category.objects.filter(is_active=True)
        self.fields["primary_category"].queryset = active_categories
        self.fields["additional_categories"].queryset = active_categories

    def clean(self):
        cleaned_data = super().clean()
        additional = cleaned_data.get("additional_categories")
        if additional and len(additional) > 3:
            self.add_error("additional_categories", "Choose no more than three additional categories.")
        primary = cleaned_data.get("primary_category")
        if primary and additional and primary in additional:
            self.add_error("additional_categories", "Additional categories must differ from the primary category.")
        return cleaned_data

    def save(self, commit=True):
        profile = super().save(commit=False)
        profile.slug = slugify(profile.business_name)
        if not profile.is_approved:
            profile.approval_status = VendorProfile.ApprovalStatus.PENDING
        if VendorProfile.objects.exclude(pk=profile.pk).filter(slug=profile.slug).exists():
            profile.slug = f"{profile.slug}-{profile.user_id}"
        if commit:
            profile.save()
        return profile


class PortfolioEntryForm(forms.ModelForm):
    class Meta:
        model = PortfolioEntry
        fields = ("image", "caption", "display_order")


class ListingForm(forms.ModelForm):
    category = forms.ModelChoiceField(queryset=Category.objects.none(), label="Category")

    class Meta:
        model = Listing
        fields = ("listing_type", "title", "category", "image", "description", "pricing_type", "price", "is_active")
        widgets = {"description": forms.Textarea(attrs={"rows": 4})}

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["category"].queryset = Category.objects.filter(is_active=True)

    def clean(self):
        cleaned_data = super().clean()
        pricing_type = cleaned_data.get("pricing_type")
        price = cleaned_data.get("price")
        if pricing_type == Listing.PricingType.CONTACT_FOR_QUOTE:
            if price is not None:
                self.add_error("price", "Leave price blank when customers should contact you.")
        elif pricing_type and price is None:
            self.add_error("price", "Enter a price for this pricing type.")
        return cleaned_data


WEB_HELP_CHOICES = (
    (EventRequest.HelpType.PLANNER, "Planner"),
    (EventRequest.HelpType.DECORATOR, "Decorator"),
    (EventRequest.HelpType.COMPLETE_SERVICE, "Complete service"),
    (EventRequest.HelpType.RENTAL_ITEMS, "Rental items only"),
    (EventRequest.HelpType.CATERING, "Catering"),
    (EventRequest.HelpType.OTHER_SERVICES, "Other event services"),
)


class EventDiscoveryForm(forms.ModelForm):
    colours = forms.CharField(required=False, label="Colours", help_text="Separate colours with commas.")
    help_types = forms.MultipleChoiceField(choices=WEB_HELP_CHOICES, widget=forms.CheckboxSelectMultiple, label="What help do you need?")
    required_categories = forms.ModelMultipleChoiceField(queryset=Category.objects.none(), widget=forms.CheckboxSelectMultiple, label="Service categories")

    class Meta:
        model = EventRequest
        fields = ("event_type", "custom_event_type", "event_date", "city", "postal_code", "guest_count", "budget_min", "budget_max", "help_types", "required_categories", "theme", "colours", "venue_type", "notes")
        widgets = {
            "event_date": forms.DateInput(attrs={"type": "date"}),
            "notes": forms.Textarea(attrs={"rows": 4}),
            "colours": forms.TextInput(attrs={"placeholder": "Terracotta, cream, olive"}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["required_categories"].queryset = Category.objects.filter(is_active=True)
        for field in ("event_type", "event_date", "city", "guest_count", "budget_min", "budget_max", "help_types", "required_categories"):
            self.fields[field].required = True

    def clean_event_date(self):
        value = self.cleaned_data.get("event_date")
        if value and value < timezone.localdate():
            raise forms.ValidationError("Choose today or a future date.")
        return value

    def clean_colours(self):
        value = self.cleaned_data.get("colours")
        if isinstance(value, list):
            return value
        return [colour.strip() for colour in (value or "").split(",") if colour.strip()]

    def clean(self):
        cleaned = super().clean()
        if cleaned.get("event_type") == EventRequest.EventType.OTHER and not cleaned.get("custom_event_type"):
            self.add_error("custom_event_type", "Tell us what kind of event you are planning.")
        minimum, maximum = cleaned.get("budget_min"), cleaned.get("budget_max")
        if minimum is not None and maximum is not None and minimum > maximum:
            self.add_error("budget_max", "Maximum budget must be at least the minimum budget.")
        return cleaned


class MatchWebFilterForm(forms.Form):
    category = forms.ModelChoiceField(queryset=Category.objects.none(), required=False)
    location = forms.CharField(required=False, max_length=100)
    service = forms.ChoiceField(choices=(("", "All services"),) + WEB_HELP_CHOICES, required=False)
    price_min = forms.DecimalField(required=False, min_value=0)
    price_max = forms.DecimalField(required=False, min_value=0)
    sort = forms.ChoiceField(choices=(("relevance", "Relevance"), ("price", "Price"), ("newest", "Newest"), ("rating", "Rating ? coming later")), required=False)

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["category"].queryset = Category.objects.filter(is_active=True)

    def clean(self):
        cleaned = super().clean()
        if cleaned.get("price_min") is not None and cleaned.get("price_max") is not None and cleaned["price_min"] > cleaned["price_max"]:
            self.add_error("price_max", "Maximum price must be at least the minimum price.")
        return cleaned
