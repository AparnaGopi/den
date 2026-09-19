from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied
from django.shortcuts import get_object_or_404, redirect, render
from django.utils.http import url_has_allowed_host_and_scheme
from django.views.decorators.http import require_http_methods, require_POST

from accounts.models import User

from .forms import EventDiscoveryForm, ListingForm, MatchWebFilterForm, PortfolioEntryForm, VendorProfileForm
from .matching import matching_vendors, public_vendors
from .models import EventRequest, Listing, PortfolioEntry, VendorProfile


def home(request):
	return render(request, "home.html")


@login_required
def customer_dashboard(request):
	if request.user.role != User.Role.CUSTOMER:
		return redirect("core:vendor-dashboard")
	events = EventRequest.objects.filter(customer=request.user).exclude(status=EventRequest.Status.ARCHIVED).prefetch_related("required_categories")
	return render(request, "core/dashboard.html", {"dashboard_type": "Customer", "event_requests": events})


@login_required
def vendor_dashboard(request):
	if request.user.role != User.Role.VENDOR:
		return redirect("core:customer-dashboard")
	profile = get_vendor_profile(request.user)
	return render(request, "core/dashboard.html", {"dashboard_type": "Vendor", "vendor_profile": profile})


def approved_vendor_profile(request, slug):
	profile = get_object_or_404(
		VendorProfile.objects.prefetch_related("portfolio_entries", "listings"),
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
		},
	)[0]


@login_required
@require_http_methods(["GET", "POST"])
def vendor_profile_manage(request):
	vendor_only(request)
	profile = get_vendor_profile(request.user)
	form = VendorProfileForm(request.POST or None, request.FILES, instance=profile)
	if request.method == "POST" and form.is_valid():
		form.save()
		messages.success(request, "Your vendor profile has been saved." if profile.is_approved else "Your vendor profile has been saved and sent for approval.")
		return redirect("core:vendor-profile-manage")
	return render(request, "core/vendor_profile_manage.html", {"form": form, "profile": profile})


@login_required
@require_http_methods(["GET", "POST"])
def vendor_portfolio_manage(request, entry_id=None):
	vendor_only(request)
	profile = get_vendor_profile(request.user)
	entry = get_object_or_404(PortfolioEntry, pk=entry_id, profile=profile) if entry_id else None
	form = PortfolioEntryForm(request.POST or None, request.FILES, instance=entry)
	if request.method == "POST" and form.is_valid():
		entry = form.save(commit=False)
		entry.profile = profile
		entry.save()
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
		listing.save()
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
    return render(request, "core/event_discovery.html", {"form": form})


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
