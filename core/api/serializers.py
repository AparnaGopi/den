from django.utils.text import slugify
from rest_framework import serializers

from core.models import Category, EventRequest, Listing, VendorProfile, VendorTag, ServiceLocation, PortfolioEntry
from core.event_rules import DATE_REQUIRED_MESSAGE, LOCATION_REQUIRED_MESSAGE, event_location_display, normalize_event_location, resolve_event_location, toronto_today


STEP_FIELDS = {
    1: ("event_type", "custom_event_type"),
    2: ("event_date", "city", "postal_code"),
    3: ("guest_count", "budget_min", "budget_max"),
    4: ("help_types", "other_help_text"),
    5: ("required_categories",),
    6: ("theme", "colours", "venue_type", "notes"),
}
REQUIRED_FIELDS = {
    1: ("event_type",),
    2: ("event_date", "city"),
    3: ("guest_count", "budget_min", "budget_max"),
    4: ("help_types",),
    5: ("required_categories",),
    6: (),
}


class EventRequestSerializer(serializers.ModelSerializer):
    help_types = serializers.ListField(child=serializers.ChoiceField(choices=EventRequest.HelpType.choices), required=False, max_length=24)
    colours = serializers.ListField(child=serializers.CharField(max_length=50), required=False, max_length=10)
    required_categories = serializers.PrimaryKeyRelatedField(queryset=Category.objects.filter(is_active=True), many=True, required=False)
    saved_vendor_ids = serializers.SerializerMethodField()
    notes = serializers.CharField(required=False, allow_blank=True, max_length=5000)
    other_help_text = serializers.CharField(required=False, allow_blank=True, max_length=500)

    class Meta:
        model = EventRequest
        fields = (
            "id", "event_type", "custom_event_type", "event_date", "city", "postal_code",
            "guest_count", "budget_min", "budget_max", "help_types", "other_help_text", "required_categories",
            "theme", "colours", "venue_type", "notes", "status", "completed_step",
            "saved_vendor_ids", "created_at", "updated_at",
        )
        read_only_fields = ("id", "status", "completed_step", "saved_vendor_ids", "created_at", "updated_at")

    def get_saved_vendor_ids(self, instance):
        return list(instance.saved_vendors.filter(
            approval_status=VendorProfile.ApprovalStatus.APPROVED, is_active=True,
            user__is_active=True, user__role="vendor", listings__is_active=True,
        ).values_list("pk", flat=True).distinct())

    def to_representation(self, instance):
        representation = super().to_representation(instance)
        representation["city"] = event_location_display(representation["city"])
        return representation

    def validate_event_date(self, value):
        if value is not None and value <= toronto_today() and value != getattr(self.instance, "event_date", None):
            raise serializers.ValidationError(DATE_REQUIRED_MESSAGE)
        return value

    def validate_city(self, value):
        if self.instance is not None and value == self.instance.city and not resolve_event_location(value):
            return value
        if not resolve_event_location(value):
            raise serializers.ValidationError(LOCATION_REQUIRED_MESSAGE)
        return normalize_event_location(value)

    def validate_help_types(self, value):
        return list(dict.fromkeys(value))

    def validate(self, attrs):
        def value(field):
            if field in attrs:
                return attrs[field]
            if self.instance is None:
                return None
            result = getattr(self.instance, field)
            return list(result.all()) if field == "required_categories" else result

        errors = {}
        minimum, maximum = value("budget_min"), value("budget_max")
        if minimum is not None and maximum is not None and minimum > maximum:
            errors["budget_max"] = "Maximum budget must be at least the minimum budget."
        step = self.context.get("step")
        complete = self.context.get("complete") or (self.instance and self.instance.status == EventRequest.Status.READY and step is None)
        required = [field for fields in REQUIRED_FIELDS.values() for field in fields] if complete else REQUIRED_FIELDS.get(step, ())
        for field in required:
            if value(field) is None or value(field) == "" or value(field) == []:
                errors[field] = "This answer is required before continuing."
        if (complete or step == 1) and value("event_type") == EventRequest.EventType.OTHER and not value("custom_event_type"):
            errors["custom_event_type"] = "Tell us what kind of event you are planning."
        if EventRequest.HelpType.OTHER in (value("help_types") or []) and not (value("other_help_text") or "").strip():
            errors["other_help_text"] = "Please describe the other help you need."
        if complete:
            if any(not category.is_active for category in (value("required_categories") or [])):
                errors["required_categories"] = "Choose active categories."
        if errors:
            raise serializers.ValidationError(errors)
        return attrs


class MatchFilterSerializer(serializers.Serializer):
    rating_min = serializers.DecimalField(max_digits=2, decimal_places=1, min_value=0, max_value=5, required=False)
    category = serializers.PrimaryKeyRelatedField(queryset=Category.objects.filter(is_active=True), required=False)
    service = serializers.ChoiceField(choices=EventRequest.HelpType.choices, required=False)
    listing_type = serializers.ChoiceField(choices=Listing.ListingType.choices, required=False)
    location = serializers.CharField(max_length=100, required=False)
    price_min = serializers.DecimalField(max_digits=12, decimal_places=2, min_value=0, required=False)
    price_max = serializers.DecimalField(max_digits=12, decimal_places=2, min_value=0, required=False)
    approval_status = serializers.ChoiceField(choices=VendorProfile.ApprovalStatus.choices, default=VendorProfile.ApprovalStatus.APPROVED)
    sort = serializers.ChoiceField(choices=("relevance", "rating", "price", "newest"), default="relevance")

    def validate(self, attrs):
        if attrs.get("price_min") is not None and attrs.get("price_max") is not None and attrs["price_min"] > attrs["price_max"]:
            raise serializers.ValidationError({"price_max": "Maximum price must be at least the minimum price."})
        return attrs


class PortfolioSerializer(serializers.ModelSerializer):
    class Meta:
        model = PortfolioEntry
        fields = ("id", "image", "caption")
        read_only_fields = ("id",)


class VendorBasicProfileSerializer(serializers.ModelSerializer):
    additional_categories = serializers.PrimaryKeyRelatedField(queryset=Category.objects.filter(is_active=True), many=True, required=False)
    service_tags = serializers.PrimaryKeyRelatedField(queryset=VendorTag.objects.filter(is_active=True, kind="SERVICE"), many=True, required=False)
    service_locations = serializers.PrimaryKeyRelatedField(queryset=ServiceLocation.objects.filter(is_active=True), many=True, required=False)
    remove_logo = serializers.BooleanField(write_only=True, required=False)
    clear_service_tags = serializers.BooleanField(write_only=True, required=False)
    clear_service_locations = serializers.BooleanField(write_only=True, required=False)
    clear_additional_categories = serializers.BooleanField(write_only=True, required=False)

    category = serializers.PrimaryKeyRelatedField(source="primary_category", queryset=Category.objects.filter(is_active=True))
    approval_label = serializers.CharField(source="get_approval_status_display", read_only=True)
    full_profile_url = serializers.SerializerMethodField()
    profile_image_url = serializers.SerializerMethodField()

    class Meta:
        model = VendorProfile
        fields = ("id", "business_name", "category", "additional_categories", "phone", "city", "service_area", "contact_first_name", "contact_last_name", "business_email", "website_url", "instagram_url", "google_business_url", "service_tags", "service_locations", "review_feedback", "remove_logo", "clear_service_tags", "clear_service_locations", "clear_additional_categories", "short_description", "profile_image", "profile_image_url", "approval_status", "approval_label", "full_profile_url")
        read_only_fields = ("id", "review_feedback", "approval_status", "approval_label", "profile_image_url", "full_profile_url")
        extra_kwargs = {"profile_image": {"write_only": True, "required": False}, "city": {"allow_blank": True}, "service_area": {"allow_blank": True}}

    def get_profile_image_url(self, instance):
        if not instance.profile_image:
            return None
        request = self.context.get("request")
        return request.build_absolute_uri(instance.profile_image.url) if request else instance.profile_image.url

    def get_full_profile_url(self, instance):
        from django.urls import reverse
        request = self.context.get("request")
        path = reverse("core:vendor-profile-manage")
        return request.build_absolute_uri(path) if request else path

    def validate(self, attrs):
        additional = list(attrs.get("additional_categories", self.instance.additional_categories.all() if self.instance else []))
        primary = attrs.get("primary_category", self.instance.primary_category if self.instance else None)
        if len(additional) > 3:
            raise serializers.ValidationError({"additional_categories": "Choose no more than three additional categories."})
        if primary and primary in additional:
            raise serializers.ValidationError({"additional_categories": "Additional categories must differ from the primary category."})
        return attrs

    def update(self, instance, validated_data):
        for field in ("service_tags", "service_locations", "additional_categories"):
            if validated_data.pop("clear_" + field, False):
                validated_data[field] = []
        if validated_data.pop("remove_logo", False):
            validated_data["profile_image"] = ""
        instance = super().update(instance, validated_data)
        base = slugify(instance.business_name) or f"vendor-{instance.user_id}"
        slug = base
        if VendorProfile.objects.exclude(pk=instance.pk).filter(slug=slug).exists():
            slug = f"{base}-{instance.user_id}"
        if instance.slug != slug:
            instance.slug = slug
            instance.save(update_fields=("slug", "updated_at"))
        return instance


class ReviewSubmissionSerializer(serializers.Serializer):
    rating = serializers.IntegerField(min_value=1, max_value=5)
    comment = serializers.CharField(max_length=2000)
