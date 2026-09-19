from django.db import transaction
from django.shortcuts import get_object_or_404
from rest_framework import generics, parsers, permissions, status
from rest_framework.exceptions import ValidationError
from rest_framework.pagination import PageNumberPagination
from rest_framework.response import Response
from rest_framework.views import APIView

from accounts.models import User
from core.matching import matching_vendors, public_vendors
from core.models import Category, EventRequest, Review, VendorProfile
from .serializers import EventRequestSerializer, MatchFilterSerializer, STEP_FIELDS, VendorBasicProfileSerializer, ReviewSubmissionSerializer


class IsCustomer(permissions.BasePermission):
    message = "Event discovery is available to customer accounts only."

    def has_permission(self, request, view):
        return request.user.is_authenticated and request.user.is_active and request.user.role == User.Role.CUSTOMER


class DiscoveryPagination(PageNumberPagination):
    page_size = 20
    page_size_query_param = "page_size"
    max_page_size = 100


class CustomerEventsMixin:
    permission_classes = (permissions.IsAuthenticated, IsCustomer)
    serializer_class = EventRequestSerializer

    def get_queryset(self):
        return EventRequest.objects.filter(customer=self.request.user).prefetch_related("required_categories")

    def event(self, pk, lock=False):
        queryset = self.get_queryset()
        return get_object_or_404(queryset.select_for_update() if lock else queryset, pk=pk)

    def editable(self, event):
        if event.status == EventRequest.Status.ARCHIVED:
            raise ValidationError({"status": "Archived events cannot be edited."})


class EventListCreateView(CustomerEventsMixin, generics.ListCreateAPIView):
    pagination_class = DiscoveryPagination

    def perform_create(self, serializer):
        serializer.save(customer=self.request.user, status=EventRequest.Status.DRAFT)


class EventDetailView(CustomerEventsMixin, generics.RetrieveUpdateAPIView):
    http_method_names = ("get", "patch", "head", "options")

    @transaction.atomic
    def patch(self, request, pk):
        event = self.event(pk, lock=True)
        self.editable(event)
        serializer = self.serializer_class(event, data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        serializer.save()
        return Response(serializer.data)


class EventStepView(CustomerEventsMixin, APIView):
    @transaction.atomic
    def patch(self, request, pk, step):
        event = self.event(pk, lock=True)
        self.editable(event)
        if step not in STEP_FIELDS:
            raise ValidationError({"step": "Choose a step from 1 to 6."})
        if step > event.completed_step + 1:
            raise ValidationError({"step": "Finish the preceding steps first."})
        unknown = set(request.data) - set(STEP_FIELDS[step])
        if unknown:
            raise ValidationError({field: "This field belongs to a different discovery step." for field in unknown})
        serializer = self.serializer_class(event, data=request.data, partial=True, context={"step": step})
        serializer.is_valid(raise_exception=True)
        serializer.save(completed_step=max(step, event.completed_step), status=EventRequest.Status.DRAFT)
        return Response(serializer.data)


class EventCompleteView(CustomerEventsMixin, APIView):
    @transaction.atomic
    def post(self, request, pk):
        event = self.event(pk, lock=True)
        self.editable(event)
        serializer = self.serializer_class(event, data={}, partial=True, context={"complete": True})
        serializer.is_valid(raise_exception=True)
        serializer.save(status=EventRequest.Status.READY, completed_step=6)
        return Response(serializer.data)


class EventArchiveView(CustomerEventsMixin, APIView):
    @transaction.atomic
    def post(self, request, pk):
        event = self.event(pk, lock=True)
        event.status = EventRequest.Status.ARCHIVED
        event.save(update_fields=("status", "updated_at"))
        return Response(self.serializer_class(event).data)


class EventMatchesView(CustomerEventsMixin, APIView):
    def get(self, request, pk):
        event = self.event(pk)
        if event.status != EventRequest.Status.READY:
            raise ValidationError({"status": "Complete discovery before viewing matches."})
        answers = self.serializer_class(event, data={}, partial=True, context={"complete": True})
        answers.is_valid(raise_exception=True)
        filters = MatchFilterSerializer(data=request.query_params)
        filters.is_valid(raise_exception=True)
        results = matching_vendors(event, filters.validated_data, request)
        paginator = DiscoveryPagination()
        page = paginator.paginate_queryset(results, request, view=self)
        response = paginator.get_paginated_response(page)
        response.data.update({
            "rating_available": any(item["rating"] is not None for item in results),
            "requested_sort": filters.validated_data["sort"],
            "applied_sort": filters.validated_data["sort"],
            "matching_version": 2,
            "price_note": "Published prices are indicative. Hourly and quote-only listings need more details; an event budget is not a booking quote.",
        })
        return response


class EventSavedVendorView(CustomerEventsMixin, APIView):
    @transaction.atomic
    def put(self, request, pk, vendor_id):
        event = self.event(pk, lock=True)
        self.editable(event)
        profile = get_object_or_404(public_vendors(), pk=vendor_id)
        event.saved_vendors.add(profile)
        return Response(self.serializer_class(event).data)

    @transaction.atomic
    def delete(self, request, pk, vendor_id):
        event = self.event(pk, lock=True)
        self.editable(event)
        event.saved_vendors.remove(vendor_id)
        return Response(self.serializer_class(event).data)


class CategoryListView(APIView):
    permission_classes = (permissions.IsAuthenticated,)

    def get(self, request):
        return Response(list(Category.objects.filter(is_active=True).values("id", "name", "slug")))


class VendorBasicProfileView(APIView):
    permission_classes = (permissions.IsAuthenticated,)
    parser_classes = (parsers.JSONParser, parsers.MultiPartParser, parsers.FormParser)

    def profile(self, request):
        if request.user.role != User.Role.VENDOR:
            from rest_framework.exceptions import PermissionDenied
            raise PermissionDenied("Only vendors can manage a vendor profile.")
        profile, _ = VendorProfile.objects.get_or_create(
            user=request.user,
            defaults={"business_name": request.user.email.split("@")[0], "slug": f"vendor-{request.user.pk}", "city": "", "service_area": "", "description": ""},
        )
        return profile

    def get(self, request):
        return Response(VendorBasicProfileSerializer(self.profile(request), context={"request": request}).data)

    def patch(self, request):
        profile = self.profile(request)
        serializer = VendorBasicProfileSerializer(profile, data=request.data, partial=True, context={"request": request})
        serializer.is_valid(raise_exception=True)
        serializer.save()
        return Response(serializer.data)


class EventReviewView(CustomerEventsMixin, APIView):
    @transaction.atomic
    def post(self, request, pk, vendor_id):
        from django.utils import timezone
        event = self.event(pk, lock=True)
        if not event.event_date or event.event_date >= timezone.localdate():
            raise ValidationError({"event": "Reviews are available after the event date."})
        vendor = get_object_or_404(public_vendors(), pk=vendor_id)
        if not event.saved_vendors.filter(pk=vendor.pk).exists():
            raise ValidationError({"vendor": "Review a vendor saved to this event."})
        if Review.objects.filter(event=event, vendor=vendor).exists():
            raise ValidationError({"review": "You already reviewed this vendor for this event."})
        data = ReviewSubmissionSerializer(data=request.data)
        data.is_valid(raise_exception=True)
        review = Review.objects.create(event=event, vendor=vendor, **data.validated_data)
        return Response({"id": review.pk, "is_verified": False}, status=status.HTTP_201_CREATED)
