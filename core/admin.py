from django.contrib import admin

from .models import Category, Listing, PortfolioEntry, Review, VendorProfile


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
	actions = ("approve_profiles",)

	@admin.action(description="Approve selected vendor profiles")
	def approve_profiles(self, request, queryset):
		updated = queryset.update(approval_status=VendorProfile.ApprovalStatus.APPROVED)
		self.message_user(request, f"Approved {updated} vendor profile(s).")


@admin.register(PortfolioEntry)
class PortfolioEntryAdmin(admin.ModelAdmin):
	list_display = ("profile", "caption", "display_order", "created_at")


@admin.register(Listing)
class ListingAdmin(admin.ModelAdmin):
	list_display = ("title", "profile", "listing_type", "pricing_type", "is_active")
	list_filter = ("listing_type", "pricing_type", "is_active")
	search_fields = ("title", "category", "profile__business_name")


@admin.register(Review)
class ReviewAdmin(admin.ModelAdmin):
    list_display = ("vendor", "event", "rating", "is_verified", "created_at")
    list_filter = ("is_verified",)
    readonly_fields = ("event", "vendor", "rating", "comment", "created_at")

    def has_add_permission(self, request):
        return False
