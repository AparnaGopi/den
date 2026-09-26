from django.urls import path
from .views import (
    VendorOptionsView, VendorPortfolioView, EventReviewView, CategoryListView, EventArchiveView, EventCompleteView, EventDetailView,
    EventListCreateView, EventLocationListView, EventMatchesView, EventSavedVendorView, EventStepView, VendorBasicProfileView,
)

urlpatterns = [
    path("vendor/options/", VendorOptionsView.as_view(), name="vendor-options"),
    path("vendor/portfolio/", VendorPortfolioView.as_view(), name="vendor-portfolio"),
    path("vendor/portfolio/<int:pk>/", VendorPortfolioView.as_view(), name="vendor-portfolio-detail"),
    path("events/<int:pk>/vendors/<int:vendor_id>/reviews/", EventReviewView.as_view(), name="event-review"),
    path("vendor/profile/", VendorBasicProfileView.as_view(), name="vendor-basic-profile"),
    path("categories/", CategoryListView.as_view(), name="categories"),
    path("event-locations/", EventLocationListView.as_view(), name="event-locations"),
    path("events/", EventListCreateView.as_view(), name="event-list"),
    path("events/<int:pk>/", EventDetailView.as_view(), name="event-detail"),
    path("events/<int:pk>/steps/<int:step>/", EventStepView.as_view(), name="event-step"),
    path("events/<int:pk>/complete/", EventCompleteView.as_view(), name="event-complete"),
    path("events/<int:pk>/archive/", EventArchiveView.as_view(), name="event-archive"),
    path("events/<int:pk>/matches/", EventMatchesView.as_view(), name="event-matches"),
    path("events/<int:pk>/saved-vendors/<int:vendor_id>/", EventSavedVendorView.as_view(), name="event-save-vendor"),
]
