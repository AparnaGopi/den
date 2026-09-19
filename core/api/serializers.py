from django.utils import timezone
from django.utils.text import slugify
from rest_framework import serializers

from core.models import Category, EventRequest, Listing, VendorProfile


STEP_FIELDS = {
    1: ("event_type", "custom_event_type"),
    2: ("event_date", "city", "postal_code"),
    3: ("guest_count", "budget_min", "budget_max"),
    4: ("help_types",),
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
    help_types = serializers.ListField(child=serializers.ChoiceField(choices=EventRequest.HelpType.choices), required=False, max_length=12)
    colours = serializers.ListField(child=serializers.CharField(max_length=50), required=False, max_length=10)
    required_categories = serializers.PrimaryKeyRelatedField(queryset=Category.objects.filter(is_active=True), many=True, required=False)
    saved_vendor_ids = serializers.SerializerMethodField()
    notes = serializers.CharField(required=False, allow_blank=True, max_length=5000)

    class Meta:
        model = EventRequest
        fields = (
            "id", "event_type", "custom_event_type", "event_date", "city", "postal_code",
            "guest_count", "budget_min", "budget_max", "help_types", "required_categories",
            "theme", "colours", "venue_type", "notes", "status", "completed_step",
            "saved_vendor_ids", "created_at", "updated_at",
        )
        read_only_fields = ("id", "status", "completed_step", "saved_vendor_ids", "created_at", "updated_at")

    def get_saved_vendor_ids(self, instance):
        return list(instance.saved_vendors.filter(
            approval_status=VendorProfile.ApprovalStatus.APPROVED, is_active=True,
            user__is_active=True, user__role="vendor", listings__is_active=True,
        ).values_list("pk", flat=True).distinct())

    def validate_event_date(self, value):
        if value is not None and value < timezone.localdate():
            raise serializers.ValidationError("Choose today or a future date.")
        return value

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
        if complete:
            if value("event_date") and value("event_date") < timezone.localdate():
                errors["event_date"] = "Choose today or a future date."
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


class VendorBasicProfileSerializer(serializers.ModelSerializer):
    category = serializers.PrimaryKeyRelatedField(source="primary_category", queryset=Category.objects.filter(is_active=True))
    approval_label = serializers.CharField(source="get_approval_status_display", read_only=True)
    full_profile_url = serializers.SerializerMethodField()
    profile_image_url = serializers.SerializerMethodField()

    class Meta:
        model = VendorProfile
        fields = ("id", "business_name", "category", "phone", "city", "service_area", "short_description", "profile_image", "profile_image_url", "approval_status", "approval_label", "full_profile_url")
        read_only_fields = ("id", "approval_status", "approval_label", "profile_image_url", "full_profile_url")
        extra_kwargs = {"profile_image": {"write_only": True, "required": False}}

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

    def update(self, instance, validated_data):
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
