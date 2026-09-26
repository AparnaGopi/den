from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied
from django.db import transaction
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.utils.http import url_has_allowed_host_and_scheme
from django.views.decorators.http import require_http_methods, require_POST

from accounts.models import User

from .forms import EventDiscoveryForm, ListingForm, MatchWebFilterForm, PortfolioEntryForm, VendorProfileForm, PortfolioBatchForm
from .event_rules import EVENT_LOCATIONS, event_location_display
from .matching import matching_vendors, public_vendors
from .models import Category, EventRequest, Listing, PortfolioEntry, VendorProfile, ServiceLocation, ListingImage


def home(request):
	return render(request, "home.html")


@login_required
def customer_dashboard(request):
	if request.user.role != User.Role.CUSTOMER:
		return redirect("core:vendor-dashboard")
	events = EventRequest.objects.filter(customer=request.user).exclude(status=EventRequest.Status.ARCHIVED).prefetch_related("required_categories")
	for event in events:
		event.display_city = event_location_display(event.city)
	return render(request, "core/dashboard.html", {"dashboard_type": "Customer", "event_requests": events})


@login_required
def vendor_dashboard(request):
	if request.user.role != User.Role.VENDOR:
		return redirect("core:customer-dashboard")
	profile = get_vendor_profile(request.user)
	return render(request, "core/dashboard.html", {"dashboard_type": "Vendor", "vendor_profile": profile})


def approved_vendor_profile(request, slug):
	profile = get_object_or_404(
		VendorProfile.objects.select_related("primary_category").prefetch_related("portfolio_entries", "listings__images", "listings__service_tags", "additional_categories", "service_tags", "event_tags", "service_locations"),
		slug=slug,
		approval_status=VendorProfile.ApprovalStatus.APPROVED,
		is_active=True,
		user__is_active=True,
		user__role=User.Role.VENDOR,
	)
	return render(request, "core/vendor_profile.html", {"profile": profile, "reviews": profile.reviews.filter(is_verified=True)})


def vendor_only(request):
	if request.user.role != User.Role.VENDOR:
		raise PermissionDenied


def get_vendor_profile(user):
	return VendorProfile.objects.get_or_create(
		user=user,
		defaults={
			"business_name": user.email.split("@")[0],
			"slug": f"vendor-{user.pk}",
			"city": "",
			"service_area": "",
			"description": "",
			"contact_first_name": user.first_name, "contact_last_name": user.last_name, "business_email": user.email,
		},
	)[0]


@login_required
@require_http_methods(["GET", "POST"])
@transaction.atomic
def vendor_profile_manage(request):
    vendor_only(request)
    profile = get_vendor_profile(request.user)
    if request.method == "POST":
        profile = VendorProfile.objects.select_for_update().get(pk=profile.pk)
    form = VendorProfileForm(request.POST or None, request.FILES, instance=profile)
    if request.method == "POST" and form.is_valid():
        with transaction.atomic():
            form.save()
        messages.success(request, "Profile saved. Preview it before submitting for approval.")
        return redirect("core:vendor-profile-preview")
    return render(request, "core/vendor_profile_manage.html", {"form": form, "profile": profile, "cities": ServiceLocation.objects.filter(is_active=True)})


@login_required
def vendor_profile_preview(request):
    vendor_only(request)
    profile = get_vendor_profile(request.user)
    return render(request, "core/vendor_profile.html", {"profile": profile, "preview": True, "reviews": profile.reviews.filter(is_verified=True)})


@login_required
@require_POST
@transaction.atomic
def vendor_profile_submit(request):
    vendor_only(request)
    profile = get_vendor_profile(request.user)
    profile = VendorProfile.objects.select_for_update().get(pk=profile.pk)
    errors = profile.submission_errors()
    if errors:
        messages.error(request, "Complete these profile fields before submitting: " + ", ".join(errors))
        return redirect("core:vendor-profile-manage")
    if not profile.is_approved:
        profile.approval_status = VendorProfile.ApprovalStatus.PENDING
        profile.save(update_fields=["approval_status", "updated_at"])
    messages.success(request, "Your profile has been submitted for review.")
    return redirect("core:vendor-profile-preview")


@login_required
@require_POST
def vendor_description_create(request):
    vendor_only(request)
    from .vendor_descriptions import description_draft
    form = VendorProfileForm(request.POST, instance=get_vendor_profile(request.user))
    if not form.is_valid():
        return JsonResponse({"errors": form.errors}, status=400)
    return JsonResponse({"description": description_draft(form.cleaned_data)})


@login_required
@require_http_methods(["GET", "POST"])
def vendor_portfolio_manage(request, entry_id=None):
	vendor_only(request)
	profile = get_vendor_profile(request.user)
	entry = get_object_or_404(PortfolioEntry, pk=entry_id, profile=profile) if entry_id else None
	files = request.FILES.copy()
	if "image" in files and "images" not in files and not entry:
		files.setlist("images", files.getlist("image"))
	form = PortfolioEntryForm(request.POST or None, files, instance=entry) if entry else PortfolioBatchForm(request.POST or None, files)
	if request.method == "POST" and form.is_valid():
		with transaction.atomic():
			if entry:
				form.save()
			else:
				for upload in form.cleaned_data["images"]:
					PortfolioEntry.objects.create(profile=profile, image=upload, caption=form.cleaned_data["caption"])
		messages.success(request, "Portfolio image saved.")
		return redirect("core:vendor-portfolio-manage")
	return render(request, "core/vendor_portfolio_manage.html", {"form": form, "profile": profile, "entries": profile.portfolio_entries.all(), "editing": entry})


@login_required
@require_http_methods(["GET", "POST"])
def vendor_listing_manage(request, listing_id=None):
	vendor_only(request)
	profile = get_vendor_profile(request.user)
	listing = get_object_or_404(Listing, pk=listing_id, profile=profile) if listing_id else None
	form = ListingForm(request.POST or None, request.FILES, instance=listing)
	if request.method == "POST" and form.is_valid():
		listing = form.save(commit=False)
		listing.profile = profile
		with transaction.atomic():
			listing.save()
			form.save_m2m()
			for upload in form.cleaned_data["gallery"]:
				ListingImage.objects.create(listing=listing, image=upload)
			listing.images.filter(pk__in=[value for value in request.POST.getlist("remove_images") if value.isdecimal()]).delete()
		messages.success(request, "Listing saved.")
		return redirect("core:vendor-listings-manage")
	return render(request, "core/vendor_listings_manage.html", {"form": form, "profile": profile, "listings": profile.listings.all(), "editing": listing})


@require_POST
@login_required
def vendor_portfolio_delete(request, entry_id):
	vendor_only(request)
	entry = get_object_or_404(PortfolioEntry, pk=entry_id, profile__user=request.user)
	entry.delete()
	messages.success(request, "Portfolio image removed.")
	return redirect("core:vendor-portfolio-manage")


@require_POST
@login_required
def vendor_listing_delete(request, listing_id):
	vendor_only(request)
	listing = get_object_or_404(Listing, pk=listing_id, profile__user=request.user)
	listing.delete()
	messages.success(request, "Listing removed.")
	return redirect("core:vendor-listings-manage")


@login_required
@require_http_methods(["GET", "POST"])
def event_discovery(request):
    if request.user.role != User.Role.CUSTOMER:
        raise PermissionDenied
    event_id = request.GET.get("event_id")
    existing = None
    if event_id:
        existing = get_object_or_404(EventRequest, pk=event_id, customer=request.user, status=EventRequest.Status.DRAFT)
    form = EventDiscoveryForm(request.POST or None, instance=existing)
    if request.method == "POST" and form.is_valid():
        event = form.save(commit=False)
        event.customer = request.user
        event.status = EventRequest.Status.READY
        event.completed_step = 6
        event.save()
        form.save_m2m()
        messages.success(request, "Your event plan is ready. Here are your matches.")
        return redirect("core:event-matches", event_id=event.pk)
    categories = Category.objects.filter(is_active=True)
    selected_values = form["required_categories"].value() or []
    selected_category_ids = {
        int(value.pk if isinstance(value, Category) else value)
        for value in selected_values
    }
    selected_help_types = form["help_types"].value() or []
    other_categories = categories.filter(is_featured=False)
    return render(request, "core/event_discovery.html", {
        "form": form,
        "event_locations": EVENT_LOCATIONS,
        "featured_categories": categories.filter(is_featured=True),
        "other_categories": other_categories,
        "selected_category_ids": selected_category_ids,
        "show_all_services": other_categories.filter(pk__in=selected_category_ids).exists(),
        "show_other_help_field": EventRequest.HelpType.OTHER in selected_help_types,
    })


@login_required
def event_matches(request, event_id):
    if request.user.role != User.Role.CUSTOMER:
        raise PermissionDenied
    event = get_object_or_404(EventRequest.objects.prefetch_related("required_categories"), pk=event_id, customer=request.user, status=EventRequest.Status.READY)
    form = MatchWebFilterForm(request.GET)
    matches = []
    if form.is_valid():
        filters = {key: value for key, value in form.cleaned_data.items() if value not in (None, "")}
        filters.setdefault("approval_status", VendorProfile.ApprovalStatus.APPROVED)
        filters.setdefault("sort", "relevance")
        matches = matching_vendors(event, filters, request)
    return render(request, "core/event_matches.html", {"event": event, "filter_form": form, "matches": matches, "rating_available": any(item["rating"] is not None for item in matches), "saved_vendor_ids": set(event.saved_vendors.values_list("pk", flat=True))})


@require_POST
@login_required
def event_vendor_save(request, event_id, vendor_id):
    if request.user.role != User.Role.CUSTOMER:
        raise PermissionDenied
    event = get_object_or_404(EventRequest, pk=event_id, customer=request.user, status=EventRequest.Status.READY)
    vendor = get_object_or_404(public_vendors(), pk=vendor_id)
    if event.saved_vendors.filter(pk=vendor.pk).exists():
        event.saved_vendors.remove(vendor)
        messages.success(request, f"Removed {vendor.business_name} from saved vendors.")
    else:
        event.saved_vendors.add(vendor)
        messages.success(request, f"Saved {vendor.business_name}.")
    next_url = request.POST.get("next")
    if next_url and url_has_allowed_host_and_scheme(next_url, allowed_hosts={request.get_host()}):
        return redirect(next_url)
    return redirect("core:event-matches", event_id=event.pk)
