from django import forms
from django.utils.text import slugify
from .models import Category, EventRequest, Listing, PortfolioEntry, VendorProfile, VendorTag, ServiceLocation, validate_vendor_image
from .event_rules import DATE_REQUIRED_MESSAGE, LOCATION_REQUIRED_MESSAGE, normalize_event_location, resolve_event_location, tomorrow_iso_date, toronto_today


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
        widget=forms.CheckboxSelectMultiple,
    )

    class Meta:
        model = VendorProfile
        fields = (
            "business_name", "profile_image", "cover_image", "contact_first_name", "contact_last_name", "phone", "business_email", "primary_category", "additional_categories", "service_tags", "event_tags", "city", "service_locations", "service_area", "price_range", "max_travel_distance", "business_address", "short_description", "services_answer", "style_answer", "experience_answer", "specialties_answer", "description",
            "years_experience", "tags", "languages", "areas_served", "website_url", "instagram_url",
            "google_business_url", "google_place_identifier", "availability",
        )
        widgets = {"short_description": forms.Textarea(attrs={"rows": 3}), "description": forms.Textarea(attrs={"rows": 5}), "availability": forms.Textarea(attrs={"rows": 3})}

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        active_categories = Category.objects.filter(is_active=True)
        self.fields["primary_category"].queryset = active_categories
        self.fields["additional_categories"].queryset = active_categories
        self.fields["business_name"].label = "Company name"
        self.fields["profile_image"].label = "Company logo"
        self.fields["city"].widget = forms.TextInput(attrs={"list": "vendor-cities", "autocomplete": "address-level2"})
        self.fields["years_experience"] = forms.TypedChoiceField(label="Years of experience", coerce=int, empty_value=0, required=False, choices=VendorProfile.EXPERIENCE_CHOICES + ([(self.instance.years_experience, f"{self.instance.years_experience} years")] if self.instance.years_experience > 50 else []))
        for field, kind in (("service_tags", "SERVICE"), ("event_tags", "EVENT")):
            self.fields[field].queryset = VendorTag.objects.filter(is_active=True, kind=kind)
            self.fields[field].widget = forms.CheckboxSelectMultiple(choices=self.fields[field].choices)
        self.fields["service_locations"].queryset = ServiceLocation.objects.filter(is_active=True)
        self.fields["service_locations"].widget = forms.CheckboxSelectMultiple(choices=self.fields["service_locations"].choices)
        self.fields["service_locations"].label = "Service areas"
        self.fields["service_area"].label = "Other service areas (optional)"
        for field, label in (("services_answer", "What services do you offer?"), ("style_answer", "How would you describe your style?"), ("experience_answer", "What experience would you like clients to know about?"), ("specialties_answer", "What are your specialties?")):
            self.fields[field].label = label
            self.fields[field].widget = forms.Textarea(attrs={"rows": 3})
        # Drafts can be saved progressively; submission validates completeness.
        for field in self.fields.values():
            field.required = False
        self.fields["business_name"].required = True


    def clean(self):
        cleaned_data = super().clean()
        cleaned_data["years_experience"] = cleaned_data.get("years_experience") or 0
        additional = cleaned_data.get("additional_categories")
        if additional and len(additional) > 3:
            self.add_error("additional_categories", "Choose no more than three additional categories.")
        primary = cleaned_data.get("primary_category")
        if primary and additional and primary in additional:
            self.add_error("additional_categories", "Additional categories must differ from the primary category.")
        return cleaned_data

    def save(self, commit=True):
        profile = super().save(commit=False)
        profile.slug = slugify(profile.business_name) or f"vendor-{profile.user_id}"
        profile.years_experience = profile.years_experience or 0
        if VendorProfile.objects.exclude(pk=profile.pk).filter(slug=profile.slug).exists():
            profile.slug = f"{profile.slug}-{profile.user_id}"
        if commit:
            profile.save()
            self._save_m2m()
        return profile


class PortfolioEntryForm(forms.ModelForm):
    class Meta:
        model = PortfolioEntry
        fields = ("image", "caption", "display_order")


class MultipleImageInput(forms.ClearableFileInput):
    allow_multiple_selected = True


class MultipleImageField(forms.ImageField):
    def __init__(self, *args, **kwargs):
        kwargs.setdefault("widget", MultipleImageInput(attrs={"accept": "image/jpeg,image/png,image/webp"}))
        kwargs.setdefault("validators", [validate_vendor_image])
        super().__init__(*args, **kwargs)

    def clean(self, data, initial=None):
        if not data:
            if self.required:
                raise forms.ValidationError("Choose at least one image.")
            return []
        files = data if isinstance(data, (list, tuple)) else [data]
        if len(files) > 20:
            raise forms.ValidationError("Upload at most 20 images at a time.")
        return [super(MultipleImageField, self).clean(item, initial) for item in files]


class PortfolioBatchForm(forms.Form):
    images = MultipleImageField()
    caption = forms.CharField(max_length=240, required=False, help_text="Initial caption for these images; each caption can be edited afterward.")


class ListingForm(forms.ModelForm):
    gallery = MultipleImageField(required=False, label="Additional listing images")

    category = forms.ModelChoiceField(queryset=Category.objects.none(), label="Category")
    help_types = forms.MultipleChoiceField(choices=EventRequest.HelpType.choices, required=False, widget=forms.CheckboxSelectMultiple, label="Services / tasks provided")

    class Meta:
        model = Listing
        fields = ("listing_type", "help_types", "title", "category", "image", "description", "pricing_type", "price", "service_tags", "is_active")
        widgets = {"description": forms.Textarea(attrs={"rows": 4})}

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["category"].queryset = Category.objects.filter(is_active=True)
        self.fields["service_tags"].queryset = VendorTag.objects.filter(is_active=True, kind="SERVICE")
        self.fields["service_tags"].widget = forms.CheckboxSelectMultiple(choices=self.fields["service_tags"].choices)

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


CUSTOMER_HELP_TYPES = (
    EventRequest.HelpType.EVENT_PLANNER, EventRequest.HelpType.EVENT_COORDINATOR,
    EventRequest.HelpType.DECORATOR, EventRequest.HelpType.FLORIST,
    EventRequest.HelpType.BALLOON_ARTIST, EventRequest.HelpType.MAKEUP_ARTIST,
    EventRequest.HelpType.HAIRSTYLIST, EventRequest.HelpType.CATERER,
    EventRequest.HelpType.PRIVATE_CHEF, EventRequest.HelpType.PHOTOGRAPHER,
    EventRequest.HelpType.VIDEOGRAPHER, EventRequest.HelpType.ENTERTAINMENT,
    EventRequest.HelpType.KIDS_ENTERTAINMENT, EventRequest.HelpType.CAKE_DESSERTS,
    EventRequest.HelpType.VENUE, EventRequest.HelpType.RENTAL_ITEMS,
    EventRequest.HelpType.DELIVERY_PICKUP, EventRequest.HelpType.SETUP_TEARDOWN,
    EventRequest.HelpType.FULL_PLANNING, EventRequest.HelpType.OTHER,
)
WEB_HELP_CHOICES = tuple(choice for choice in EventRequest.HelpType.choices if choice[0] in CUSTOMER_HELP_TYPES)


class EventDiscoveryForm(forms.ModelForm):
    colours = forms.CharField(required=False, label="Colours", help_text="Separate colours with commas.")
    help_types = forms.MultipleChoiceField(choices=WEB_HELP_CHOICES, widget=forms.CheckboxSelectMultiple, label="What help do you need?")
    required_categories = forms.ModelMultipleChoiceField(queryset=Category.objects.none(), widget=forms.CheckboxSelectMultiple, label="Service categories")

    class Meta:
        model = EventRequest
        fields = ("event_type", "custom_event_type", "event_date", "city", "postal_code", "guest_count", "budget_min", "budget_max", "help_types", "other_help_text", "required_categories", "theme", "colours", "venue_type", "notes")
        widgets = {
            "event_date": forms.DateInput(attrs={"type": "date"}),
            "notes": forms.Textarea(attrs={"rows": 4}),
            "colours": forms.TextInput(attrs={"placeholder": "Terracotta, cream, olive"}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["required_categories"].queryset = Category.objects.filter(is_active=True)
        self.fields["city"].widget.attrs.update({"list": "gta-locations", "autocomplete": "off"})
        self.fields["other_help_text"].required = False
        self.fields["other_help_text"].widget = forms.TextInput(attrs={"maxlength": 500, "placeholder": "Tell us what kind of help you need"})
        self.fields["event_date"].widget.attrs["min"] = tomorrow_iso_date()
        if self.instance.pk and self.instance.event_date and self.instance.event_date <= toronto_today():
            self.fields["event_date"].widget.attrs.pop("min", None)
        submitted_help_types = self.data.getlist("help_types") if hasattr(self.data, "getlist") else self.data.get("help_types", [])
        if isinstance(submitted_help_types, str):
            submitted_help_types = [submitted_help_types]
        legacy_values = set(self.instance.help_types if self.instance.pk else ()) | set(submitted_help_types)
        legacy = [(value, label) for value, label in EventRequest.HelpType.choices if value in legacy_values and value not in dict(WEB_HELP_CHOICES)]
        self.fields["help_types"].choices = WEB_HELP_CHOICES + tuple(legacy)
        if self.instance.pk:
            self.initial["colours"] = ", ".join(self.instance.colours)
        for field in ("event_type", "event_date", "city", "guest_count", "budget_min", "budget_max", "help_types", "required_categories"):
            self.fields[field].required = True

    def clean_event_date(self):
        value = self.cleaned_data.get("event_date")
        if value and value <= toronto_today() and value != self.instance.event_date:
            raise forms.ValidationError(DATE_REQUIRED_MESSAGE)
        return value

    def clean_city(self):
        value = self.cleaned_data.get("city", "").strip()
        if self.instance.pk and value == self.instance.city and not resolve_event_location(value):
            return value
        if not resolve_event_location(value):
            raise forms.ValidationError(LOCATION_REQUIRED_MESSAGE)
        return normalize_event_location(value)

    def clean_colours(self):
        value = self.cleaned_data.get("colours")
        if isinstance(value, list):
            return value
        return [colour.strip() for colour in (value or "").split(",") if colour.strip()]

    def clean(self):
        cleaned = super().clean()
        if EventRequest.HelpType.OTHER in cleaned.get("help_types", []):
            if not (cleaned.get("other_help_text") or "").strip():
                self.add_error("other_help_text", "Please describe the other help you need.")
        else:
            cleaned["other_help_text"] = ""
        if cleaned.get("event_type") == EventRequest.EventType.OTHER and not cleaned.get("custom_event_type"):
            self.add_error("custom_event_type", "Tell us what kind of event you are planning.")
        minimum, maximum = cleaned.get("budget_min"), cleaned.get("budget_max")
        if minimum is not None and maximum is not None and minimum > maximum:
            self.add_error("budget_max", "Maximum budget must be at least the minimum budget.")
        return cleaned


class MatchWebFilterForm(forms.Form):
    rating_min = forms.DecimalField(required=False, min_value=0, max_value=5, decimal_places=1, label="Minimum verified rating")
    category = forms.ModelChoiceField(queryset=Category.objects.none(), required=False)
    location = forms.CharField(required=False, max_length=100)
    service = forms.ChoiceField(choices=(("", "All services"),) + tuple(EventRequest.HelpType.choices), required=False)
    price_min = forms.DecimalField(required=False, min_value=0)
    price_max = forms.DecimalField(required=False, min_value=0)
    sort = forms.ChoiceField(choices=(("relevance", "Relevance"), ("price", "Price"), ("newest", "Newest"), ("rating", "Verified rating")), required=False)

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["category"].queryset = Category.objects.filter(is_active=True)

    def clean(self):
        cleaned = super().clean()
        if cleaned.get("price_min") is not None and cleaned.get("price_max") is not None and cleaned["price_min"] > cleaned["price_max"]:
            self.add_error("price_max", "Maximum price must be at least the minimum price.")
        return cleaned
