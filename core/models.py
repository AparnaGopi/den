from django.db import models
from decimal import Decimal

from django.core.exceptions import ValidationError
from django.core.validators import MinValueValidator
from PIL import Image

from accounts.models import User


MAX_IMAGE_SIZE = 5 * 1024 * 1024


def validate_vendor_image(upload):
	if upload.size > MAX_IMAGE_SIZE:
		raise ValidationError("Images must be 5 MB or smaller.")
	try:
		with Image.open(upload) as image:
			image.verify()
	except (OSError, ValueError):
		raise ValidationError("Upload a valid image file.")


def vendor_upload_path(instance, filename):
	owner_id = getattr(instance, "profile_id", None) or getattr(instance, "user_id", "unassigned")
	return f"vendors/{owner_id}/{filename}"


class Category(models.Model):
	name = models.CharField(max_length=100, unique=True)
	slug = models.SlugField(max_length=120, unique=True)
	is_active = models.BooleanField(default=True)

	class Meta:
		ordering = ("name",)

	def __str__(self):
		return self.name


class VendorProfile(models.Model):
	class ApprovalStatus(models.TextChoices):
		DRAFT = "DRAFT", "Draft"
		PENDING = "PENDING", "Pending"
		APPROVED = "APPROVED", "Approved"
		REJECTED = "REJECTED", "Rejected"

	user = models.OneToOneField(User, on_delete=models.CASCADE, related_name="vendor_profile")
	business_name = models.CharField(max_length=160)
	phone = models.CharField(max_length=30, blank=True)
	slug = models.SlugField(max_length=180, unique=True)
	primary_category = models.ForeignKey(Category, on_delete=models.PROTECT, related_name="primary_profiles", null=True, blank=True)
	additional_categories = models.ManyToManyField(Category, related_name="additional_profiles", blank=True)
	tags = models.CharField(max_length=300, blank=True, help_text="Comma-separated searchable tags.")
	city = models.CharField(max_length=100)
	service_area = models.CharField(max_length=200)
	short_description = models.CharField(max_length=500, blank=True)
	description = models.TextField()
	years_experience = models.PositiveIntegerField(default=0)
	languages = models.CharField(max_length=200, blank=True)
	areas_served = models.CharField(max_length=300, blank=True)
	website_url = models.URLField(blank=True)
	instagram_url = models.URLField(blank=True)
	google_business_url = models.URLField(blank=True)
	google_place_identifier = models.CharField(max_length=255, blank=True)
	availability = models.TextField(blank=True, help_text="Describe current availability, lead times, or seasonal limits.")
	cover_image = models.ImageField(upload_to=vendor_upload_path, validators=[validate_vendor_image], blank=True)
	profile_image = models.ImageField(upload_to=vendor_upload_path, validators=[validate_vendor_image], blank=True)
	is_active = models.BooleanField(default=True)
	approval_status = models.CharField(max_length=20, choices=ApprovalStatus.choices, default=ApprovalStatus.DRAFT)
	created_at = models.DateTimeField(auto_now_add=True)
	updated_at = models.DateTimeField(auto_now=True)

	class Meta:
		ordering = ("business_name",)

	def clean(self):
		if self.user_id and self.user.role != User.Role.VENDOR:
			raise ValidationError({"user": "Only vendor accounts can own vendor profiles."})

	@property
	def is_approved(self):
		return self.approval_status == self.ApprovalStatus.APPROVED

	def __str__(self):
		return self.business_name


class PortfolioEntry(models.Model):
	profile = models.ForeignKey(VendorProfile, on_delete=models.CASCADE, related_name="portfolio_entries")
	image = models.ImageField(upload_to=vendor_upload_path, validators=[validate_vendor_image])
	caption = models.CharField(max_length=240, blank=True)
	display_order = models.PositiveIntegerField(default=0)
	created_at = models.DateTimeField(auto_now_add=True)

	class Meta:
		ordering = ("display_order", "-created_at")

	def __str__(self):
		return self.caption or f"Portfolio image {self.pk}"


class Listing(models.Model):
	class ListingType(models.TextChoices):
		SERVICE = "SERVICE", "Service"
		PACKAGE = "PACKAGE", "Package"
		RENTAL = "RENTAL", "Rental"
		PRODUCT = "PRODUCT", "Product"

	class PricingType(models.TextChoices):
		FIXED = "FIXED", "Fixed"
		STARTING_FROM = "STARTING_FROM", "Starting from"
		HOURLY = "HOURLY", "Hourly"
		CONTACT_FOR_QUOTE = "CONTACT_FOR_QUOTE", "Contact for quote"

	profile = models.ForeignKey(VendorProfile, on_delete=models.CASCADE, related_name="listings")
	listing_type = models.CharField(max_length=20, choices=ListingType.choices)
	title = models.CharField(max_length=160)
	category = models.ForeignKey(Category, on_delete=models.PROTECT, related_name="listings", null=True, blank=True)
	image = models.ImageField(upload_to=vendor_upload_path, validators=[validate_vendor_image])
	description = models.TextField()
	pricing_type = models.CharField(max_length=20, choices=PricingType.choices)
	price = models.DecimalField(max_digits=10, decimal_places=2, blank=True, null=True, validators=[MinValueValidator(Decimal("0"))])
	is_active = models.BooleanField(default=True)
	created_at = models.DateTimeField(auto_now_add=True)
	updated_at = models.DateTimeField(auto_now=True)

	class Meta:
		ordering = ("-is_active", "title")

	def clean(self):
		if self.category_id and not self.category.is_active:
			raise ValidationError({"category": "Choose an active category."})
		if self.pricing_type == self.PricingType.CONTACT_FOR_QUOTE and self.price is not None:
			raise ValidationError({"price": "Contact-for-quote listings should not include a price."})
		if self.pricing_type != self.PricingType.CONTACT_FOR_QUOTE and self.price is None:
			raise ValidationError({"price": "Enter a price for this pricing type."})

	def __str__(self):
		return self.title

# Create your models here.


class EventRequest(models.Model):
    class EventType(models.TextChoices):
        WEDDING = "WEDDING", "Wedding"
        BIRTHDAY = "BIRTHDAY", "Birthday"
        CORPORATE = "CORPORATE", "Corporate event"
        BABY_SHOWER = "BABY_SHOWER", "Baby shower"
        ANNIVERSARY = "ANNIVERSARY", "Anniversary"
        OTHER = "OTHER", "Something else"

    class HelpType(models.TextChoices):
        FULL_PLANNING = "FULL_PLANNING", "Full planning"
        PARTIAL_PLANNING = "PARTIAL_PLANNING", "Some planning help"
        VENDORS_ONLY = "VENDORS_ONLY", "Find vendors"
        RENTALS = "RENTALS", "Rentals"
        PRODUCTS = "PRODUCTS", "Products"
        PLANNER = "PLANNER", "Planner"
        DECORATOR = "DECORATOR", "Decorator"
        COMPLETE_SERVICE = "COMPLETE_SERVICE", "Complete service"
        RENTAL_ITEMS = "RENTAL_ITEMS", "Rental items only"
        CATERING = "CATERING", "Catering"
        OTHER_SERVICES = "OTHER_SERVICES", "Other event services"

    class VenueType(models.TextChoices):
        INDOOR = "INDOOR", "Indoor"
        OUTDOOR = "OUTDOOR", "Outdoor"
        UNDECIDED = "UNDECIDED", "Undecided"

    class Status(models.TextChoices):
        DRAFT = "DRAFT", "Draft"
        READY = "READY", "Ready"
        ARCHIVED = "ARCHIVED", "Archived"

    customer = models.ForeignKey(User, on_delete=models.CASCADE, related_name="event_requests", limit_choices_to={"role": User.Role.CUSTOMER})
    event_type = models.CharField(max_length=30, choices=EventType.choices, blank=True)
    custom_event_type = models.CharField(max_length=100, blank=True)
    event_date = models.DateField(null=True, blank=True)
    city = models.CharField(max_length=100, blank=True)
    postal_code = models.CharField(max_length=20, blank=True)
    guest_count = models.PositiveIntegerField(null=True, blank=True, validators=[MinValueValidator(1)])
    budget_min = models.DecimalField(max_digits=12, decimal_places=2, null=True, blank=True, validators=[MinValueValidator(Decimal("0"))])
    budget_max = models.DecimalField(max_digits=12, decimal_places=2, null=True, blank=True, validators=[MinValueValidator(Decimal("0"))])
    help_types = models.JSONField(default=list, blank=True)
    required_categories = models.ManyToManyField(Category, related_name="event_requests", blank=True)
    theme = models.CharField(max_length=200, blank=True)
    colours = models.JSONField(default=list, blank=True)
    venue_type = models.CharField(max_length=20, choices=VenueType.choices, default=VenueType.UNDECIDED)
    notes = models.TextField(blank=True)
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.DRAFT)
    completed_step = models.PositiveSmallIntegerField(default=0)
    saved_vendors = models.ManyToManyField(VendorProfile, related_name="saved_for_events", blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ("-updated_at", "-pk")
        constraints = [
            models.CheckConstraint(condition=models.Q(budget_min__isnull=True) | models.Q(budget_max__isnull=True) | models.Q(budget_max__gte=models.F("budget_min")), name="event_budget_order"),
            models.CheckConstraint(condition=models.Q(completed_step__lte=6), name="event_progress_range"),
            models.CheckConstraint(condition=models.Q(guest_count__isnull=True) | models.Q(guest_count__gte=1), name="event_positive_guests"),
        ]

    def clean(self):
        super().clean()
        if self.customer_id and self.customer.role != User.Role.CUSTOMER:
            raise ValidationError({"customer": "Only customers can own event requests."})
        if self.budget_min is not None and self.budget_max is not None and self.budget_min > self.budget_max:
            raise ValidationError({"budget_max": "Maximum budget must be at least the minimum budget."})
        if not isinstance(self.help_types, list) or any(value not in self.HelpType.values for value in self.help_types):
            raise ValidationError({"help_types": "Choose supported help types."})

    def __str__(self):
        return f"{self.get_event_type_display() or 'Draft event'} ({self.pk})"
