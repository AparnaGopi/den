from django.urls import path
from .chat import ConversationListView, ContactVendorView, ConversationMessagesView, VendorChatPlanView, VendorVisitStatsView, VendorVisitView, QuickVendorProfileView
from .views import (
    VendorWizardView, VendorOptionsView, VendorPortfolioView, EventReviewView, CategoryListView, EventArchiveView, EventCompleteView, EventDetailView,
    EventListCreateView, EventLocationListView, EventMatchesView, EventSavedVendorView, EventStepView, VendorBasicProfileView,
    DiscoveryServiceTagListView, VendorDiscoveryView,
)

urlpatterns = [
    path("messages/", ConversationListView.as_view(), name="message-list"),
    path("messages/<int:pk>/", ConversationMessagesView.as_view(), name="message-thread"),
    path("vendors/<int:vendor_id>/contact/", ContactVendorView.as_view(), name="contact-vendor"),
    path("vendors/<int:vendor_id>/visit/", VendorVisitView.as_view(), name="vendor-visit"),
    path("vendor/chat-plan/", VendorChatPlanView.as_view(), name="vendor-chat-plan"),
    path("vendor/visit-stats/", VendorVisitStatsView.as_view(), name="vendor-visit-stats"),
    path("vendor/quick-profile/", QuickVendorProfileView.as_view(), name="vendor-quick-profile"),
    path("vendor/onboarding/", VendorWizardView.as_view(), name="vendor-onboarding"),
    path("vendor/options/", VendorOptionsView.as_view(), name="vendor-options"),
    path("vendor/portfolio/", VendorPortfolioView.as_view(), name="vendor-portfolio"),
    path("vendor/portfolio/<int:pk>/", VendorPortfolioView.as_view(), name="vendor-portfolio-detail"),
    path("events/<int:pk>/vendors/<int:vendor_id>/reviews/", EventReviewView.as_view(), name="event-review"),
    path("vendor/profile/", VendorBasicProfileView.as_view(), name="vendor-basic-profile"),
    path("categories/", CategoryListView.as_view(), name="categories"),
    path("event-locations/", EventLocationListView.as_view(), name="event-locations"),
    path("vendors/discovery/", VendorDiscoveryView.as_view(), name="vendor-discovery"),
    path("discovery-services/", DiscoveryServiceTagListView.as_view(), name="discovery-services"),
    path("events/", EventListCreateView.as_view(), name="event-list"),
    path("events/<int:pk>/", EventDetailView.as_view(), name="event-detail"),
    path("events/<int:pk>/steps/<int:step>/", EventStepView.as_view(), name="event-step"),
    path("events/<int:pk>/complete/", EventCompleteView.as_view(), name="event-complete"),
    path("events/<int:pk>/archive/", EventArchiveView.as_view(), name="event-archive"),
    path("events/<int:pk>/matches/", EventMatchesView.as_view(), name="event-matches"),
    path("events/<int:pk>/saved-vendors/<int:vendor_id>/", EventSavedVendorView.as_view(), name="event-save-vendor"),
]
