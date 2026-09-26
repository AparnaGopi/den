from django.contrib import admin

from .models import Category, Listing, PortfolioEntry, Review, VendorProfile, VendorTag, ServiceLocation, ListingImage


@admin.register(Category)
class CategoryAdmin(admin.ModelAdmin):
	list_display = ("name", "is_active")
	list_filter = ("is_active",)
	search_fields = ("name",)


class PortfolioEntryInline(admin.TabularInline):
	model = PortfolioEntry
	extra = 0


class ListingInline(admin.TabularInline):
	model = Listing
	extra = 0


@admin.register(VendorProfile)
class VendorProfileAdmin(admin.ModelAdmin):
	list_display = ("business_name", "user", "primary_category", "city", "phone", "approval_status", "is_active")
	list_filter = ("approval_status", "is_active", "primary_category", "city")
	search_fields = ("business_name", "user__email", "tags")
	inlines = (PortfolioEntryInline, ListingInline)
	actions = ("approve_profiles", "reject_profiles", "request_changes")

	@admin.action(description="Approve selected vendor profiles")
	def approve_profiles(self, request, queryset):
		updated = 0
		for profile in queryset:
			if not profile.submission_errors():
				profile.approval_status = VendorProfile.ApprovalStatus.APPROVED
				profile.save(update_fields=["approval_status"])
				updated += 1
		self.message_user(request, f"Approved {updated} complete profile(s); incomplete profiles were skipped.")

	@admin.action(description="Reject selected profiles")
	def reject_profiles(self, request, queryset):
		queryset.update(approval_status=VendorProfile.ApprovalStatus.REJECTED)

	@admin.action(description="Request changes (enter review feedback on each profile)")
	def request_changes(self, request, queryset):
		queryset.update(approval_status=VendorProfile.ApprovalStatus.CHANGES_REQUESTED)


@admin.register(PortfolioEntry)
class PortfolioEntryAdmin(admin.ModelAdmin):
	list_display = ("profile", "caption", "display_order", "created_at")


@admin.register(Listing)
class ListingAdmin(admin.ModelAdmin):
	list_display = ("title", "profile", "listing_type", "pricing_type", "is_active")
	list_filter = ("listing_type", "pricing_type", "is_active")
	search_fields = ("title", "category__name", "profile__business_name")


@admin.register(Review)
class ReviewAdmin(admin.ModelAdmin):
    list_display = ("vendor", "event", "rating", "is_verified", "created_at")
    list_filter = ("is_verified",)
    readonly_fields = ("event", "vendor", "rating", "comment", "created_at")

    def has_add_permission(self, request):
        return False


@admin.register(VendorTag)
class VendorTagAdmin(admin.ModelAdmin):
    list_display = ("name", "kind", "is_active")
    list_filter = ("kind", "is_active")
    search_fields = ("name",)


@admin.register(ServiceLocation)
class ServiceLocationAdmin(admin.ModelAdmin):
    list_display = ("name", "is_active")
    search_fields = ("name",)


class ListingImageInline(admin.TabularInline):
    model = ListingImage
    extra = 0


ListingAdmin.inlines = (ListingImageInline,)
