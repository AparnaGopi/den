"""Deterministic discovery rules. Prices are indicative, never booking quotes."""
import re
from decimal import Decimal

from django.db.models import Prefetch
from django.urls import reverse

from accounts.models import User
from core.models import Category, EventRequest, Listing, VendorProfile


HELP_LISTING_TYPES = {
    EventRequest.HelpType.FULL_PLANNING: {Listing.ListingType.SERVICE, Listing.ListingType.PACKAGE},
    EventRequest.HelpType.PARTIAL_PLANNING: {Listing.ListingType.SERVICE, Listing.ListingType.PACKAGE},
    EventRequest.HelpType.VENDORS_ONLY: set(Listing.ListingType.values),
    EventRequest.HelpType.RENTALS: {Listing.ListingType.RENTAL},
    EventRequest.HelpType.PRODUCTS: {Listing.ListingType.PRODUCT},
    EventRequest.HelpType.PLANNER: {Listing.ListingType.SERVICE, Listing.ListingType.PACKAGE},
    EventRequest.HelpType.DECORATOR: {Listing.ListingType.SERVICE, Listing.ListingType.PACKAGE},
    EventRequest.HelpType.COMPLETE_SERVICE: set(Listing.ListingType.values),
    EventRequest.HelpType.RENTAL_ITEMS: {Listing.ListingType.RENTAL},
    EventRequest.HelpType.CATERING: {Listing.ListingType.SERVICE, Listing.ListingType.PACKAGE, Listing.ListingType.PRODUCT},
    EventRequest.HelpType.OTHER_SERVICES: set(Listing.ListingType.values),
}


def normalized(value):
    return " ".join(value.casefold().split())


def serves_location(profile, location):
    target = normalized(location)
    areas = re.split(r"[,;/\n]", f"{profile.service_area},{profile.areas_served}")
    return bool(target) and (normalized(profile.city) == target or any(normalized(area) == target for area in areas))


def public_vendors():
    return VendorProfile.objects.filter(
        approval_status=VendorProfile.ApprovalStatus.APPROVED, is_active=True,
        user__is_active=True, user__role=User.Role.VENDOR, listings__is_active=True,
    ).distinct()


def budget_compatible(listing, event):
    # Hourly prices require duration; quote-only prices require a quote.
    if listing.price is None or listing.pricing_type in (Listing.PricingType.HOURLY, Listing.PricingType.CONTACT_FOR_QUOTE):
        return True
    return event.budget_max is None or listing.price <= event.budget_max


def matching_vendors(event, filters, request):
    if filters["approval_status"] != VendorProfile.ApprovalStatus.APPROVED:
        return []
    required = {category.pk for category in event.required_categories.all() if category.is_active}
    help_types = set().union(*(HELP_LISTING_TYPES.get(help_type, set()) for help_type in event.help_types)) if event.help_types else set(Listing.ListingType.values)
    if filters.get("service"):
        help_types.intersection_update(HELP_LISTING_TYPES[filters["service"]])
    active_listings = Listing.objects.filter(is_active=True).select_related("category")
    profiles = public_vendors().select_related("primary_category").prefetch_related(
        Prefetch("additional_categories", queryset=Category.objects.filter(is_active=True)),
        Prefetch("listings", queryset=active_listings, to_attr="discovery_listings"),
    )
    results = []
    for profile in profiles:
        if not serves_location(profile, event.city):
            continue
        if filters.get("location") and not serves_location(profile, filters["location"]):
            continue
        profile_categories = {category.pk for category in profile.additional_categories.all()}
        if profile.primary_category and profile.primary_category.is_active:
            profile_categories.add(profile.primary_category_id)
        eligible = []
        coverage = set()
        for listing in profile.discovery_listings:
            if listing.category and not listing.category.is_active:
                continue
            categories = {listing.category_id} if listing.category_id else profile_categories
            if required and not categories.intersection(required):
                continue
            if listing.listing_type not in help_types:
                continue
            if filters.get("category") and filters["category"].pk not in categories:
                continue
            if filters.get("listing_type") and filters["listing_type"] != listing.listing_type:
                continue
            if not budget_compatible(listing, event):
                continue
            if any(key in filters for key in ("price_min", "price_max")):
                if listing.price is None or listing.pricing_type == Listing.PricingType.CONTACT_FOR_QUOTE:
                    continue
                if "price_min" in filters and listing.price < filters["price_min"]:
                    continue
                if "price_max" in filters and listing.price > filters["price_max"]:
                    continue
            eligible.append(listing)
            coverage.update(categories.intersection(required))
        if not eligible:
            continue
        reasons = [
            {"code": "CATEGORY_COVERAGE", "points": round(40 * len(coverage) / len(required)) if required else 0, "label": f"Covers {len(coverage)} of {len(required)} requested categories"},
            {"code": "SERVICE_LOCATION", "points": 25, "label": "Lists your city in its service locations"},
            {"code": "HELP_TYPE", "points": 15, "label": "Has an active listing for the help requested"},
        ]
        priced = [listing.price for listing in eligible if listing.price is not None and listing.pricing_type in (Listing.PricingType.FIXED, Listing.PricingType.STARTING_FROM)]
        budget_points = 0
        if priced and event.budget_max is not None:
            budget_points = 20 if any(event.budget_min is None or price >= event.budget_min for price in priced) else 10
        reasons.append({"code": "INDICATIVE_BUDGET", "points": budget_points, "label": "Published price fits your indicative budget" if budget_points else "Total cost needs a quote or duration details"})
        image = request.build_absolute_uri(profile.profile_image.url) if profile.profile_image else None
        results.append({
            "id": profile.pk, "business_name": profile.business_name, "slug": profile.slug,
            "city": profile.city, "service_area": profile.service_area,
            "description": profile.short_description or profile.description, "profile_image": image,
            "approval_status": profile.approval_status,
            "profile_url": request.build_absolute_uri(reverse("core:vendor-profile", args=[profile.slug])),
            "match_score": sum(reason["points"] for reason in reasons), "matching_reasons": reasons,
            "rating": None, "starting_price": str(min(priced)) if priced else None,
            "created_at": profile.created_at.isoformat(),
            "listings": [{"id": listing.pk, "title": listing.title, "listing_type": listing.listing_type,
                          "category": listing.category_id, "pricing_type": listing.pricing_type,
                          "price": str(listing.price) if listing.price is not None else None} for listing in eligible],
        })
    sort = filters["sort"]
    if sort == "price":
        results.sort(key=lambda item: (item["starting_price"] is None, Decimal(item["starting_price"] or "0"), -item["match_score"], item["id"]))
    elif sort == "newest":
        results.sort(key=lambda item: (item["created_at"], item["id"]), reverse=True)
    else:
        results.sort(key=lambda item: (-item["match_score"], item["business_name"].casefold(), item["id"]))
    return results
