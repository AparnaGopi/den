from django.urls import path

from . import views

app_name = "core"

urlpatterns = [
    path("", views.home, name="home"),
    path("dashboard/customer/", views.customer_dashboard, name="customer-dashboard"),
    path("dashboard/vendor/", views.vendor_dashboard, name="vendor-dashboard"),
    path("events/plan/", views.event_discovery, name="event-discovery"),
    path("events/<int:event_id>/matches/", views.event_matches, name="event-matches"),
    path("events/<int:event_id>/vendors/<int:vendor_id>/save/", views.event_vendor_save, name="event-vendor-save"),
    path("vendors/<slug:slug>/", views.approved_vendor_profile, name="vendor-profile"),
    path("vendor/profile/", views.vendor_profile_manage, name="vendor-profile-manage"),
    path("vendor/portfolio/", views.vendor_portfolio_manage, name="vendor-portfolio-manage"),
    path("vendor/portfolio/<int:entry_id>/edit/", views.vendor_portfolio_manage, name="vendor-portfolio-edit"),
    path("vendor/portfolio/<int:entry_id>/delete/", views.vendor_portfolio_delete, name="vendor-portfolio-delete"),
    path("vendor/listings/", views.vendor_listing_manage, name="vendor-listings-manage"),
    path("vendor/listings/<int:listing_id>/edit/", views.vendor_listing_manage, name="vendor-listing-edit"),
    path("vendor/listings/<int:listing_id>/delete/", views.vendor_listing_delete, name="vendor-listing-delete"),
]