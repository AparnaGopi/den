from django.core.exceptions import ValidationError as DjangoValidationError
from django.db import transaction
from django.shortcuts import get_object_or_404
from django.utils import timezone
from rest_framework import parsers, permissions
from rest_framework.exceptions import ValidationError
from rest_framework.response import Response
from rest_framework.views import APIView

from core.forms import WEB_HELP_CHOICES
from core.messaging import SubscriptionRequired, can_reply, chat_plan, inbox, open_customer_chat, participant_chats, record_visit, send_message, visit_stats
from core.models import ChatMessage, EventRequest, ServiceLocation, VendorChatSubscription, VendorProfile
from core.vendor_quick import QuickVendorForm
from .views import DiscoveryPagination, VendorBasicProfileView


def message_data(message, request):
    return {"id": message.pk, "body": message.body, "mine": message.sender_id == request.user.pk,
            "created_at": message.created_at, "read_at": message.read_at}


def conversation_data(chat, request):
    event = chat.event
    shared = None
    if event and event.status != EventRequest.Status.ARCHIVED:
        shared = {"event_type": event.get_event_type_display(), "date": event.event_date, "city": event.city,
                  "guests": event.guest_count, "budget_min": event.budget_min, "budget_max": event.budget_max, "notes": event.notes}
    return {"id": chat.pk, "vendor_id": chat.vendor_id, "title": chat.vendor.business_name if request.user.role == "customer" else (chat.customer.first_name or f"Customer #{chat.customer_id}"),
            "updated_at": chat.updated_at, "unread_count": getattr(chat, "unread_count", 0), "event": shared,
            "can_reply": request.user.role == "customer" or can_reply(chat)}


class ConversationListView(APIView):
    permission_classes = (permissions.IsAuthenticated,)

    def get(self, request):
        pager = DiscoveryPagination()
        chats = pager.paginate_queryset(inbox(request.user), request)
        return pager.get_paginated_response([conversation_data(chat, request) for chat in chats])


class ContactVendorView(APIView):
    permission_classes = (permissions.IsAuthenticated,)

    def post(self, request, vendor_id):
        try:
            chat = open_customer_chat(request.user, vendor_id, request.data.get("event_id"))
        except DjangoValidationError as exc:
            raise ValidationError({"event_id": exc.messages})
        return Response(conversation_data(chat, request), status=200)


class ConversationMessagesView(APIView):
    permission_classes = (permissions.IsAuthenticated,)

    def get(self, request, pk):
        chat = get_object_or_404(participant_chats(request.user).select_related("vendor", "customer", "event"), pk=pk)
        queryset = chat.messages.all()
        before = request.query_params.get("before")
        if before:
            try:
                queryset = queryset.filter(pk__lt=int(before))
            except (TypeError, ValueError):
                raise ValidationError({"before": "Choose a message ID."})
        items = list(queryset.order_by("-pk")[:101])
        has_more = len(items) > 100
        items = list(reversed(items[:100]))
        ChatMessage.objects.filter(pk__in=[item.pk for item in items if item.sender_id != request.user.pk and not item.read_at]).update(read_at=timezone.now())
        return Response({"conversation": conversation_data(chat, request), "messages": [message_data(item, request) for item in items],
                         "next_before": items[0].pk if has_more else None})

    def post(self, request, pk):
        try:
            body = request.data.get("body")
            if not isinstance(body, str):
                raise DjangoValidationError("Write a message.")
            message = send_message(request.user, pk, body)
        except SubscriptionRequired as exc:
            return Response({"detail": " ".join(exc.messages), "subscription_required": True}, status=402)
        except DjangoValidationError as exc:
            raise ValidationError({"body": exc.messages})
        return Response(message_data(message, request), status=201)


class VendorChatPlanView(VendorBasicProfileView):
    http_method_names = ("get", "post", "head", "options")
    def get(self, request):
        return Response(chat_plan(self.profile(request)))

    def post(self, request):
        subscription, _ = VendorChatSubscription.objects.get_or_create(vendor=self.profile(request))
        if not subscription.requested_at:
            subscription.requested_at = timezone.now()
            subscription.save(update_fields=("requested_at", "updated_at"))
        return Response({**chat_plan(subscription.vendor), "detail": "Interest saved. Payments are not open yet; you have not been charged."})


class VendorVisitStatsView(VendorBasicProfileView):
    http_method_names = ("get", "head", "options")
    def get(self, request):
        return Response(visit_stats(self.profile(request)))


class VendorVisitView(APIView):
    permission_classes = (permissions.IsAuthenticated,)

    def post(self, request, vendor_id):
        profile = get_object_or_404(VendorProfile, pk=vendor_id, approval_status="APPROVED", is_active=True, user__is_active=True, user__role="vendor")
        record_visit(profile, request.user)
        return Response(status=204)


class QuickVendorProfileView(VendorBasicProfileView):
    http_method_names = ("get", "post", "head", "options")
    parser_classes = (parsers.JSONParser, parsers.MultiPartParser, parsers.FormParser)

    def data(self, profile, request):
        def url(image):
            return request.build_absolute_uri(image.url) if image else None
        form = QuickVendorForm(instance=profile)
        return {"id": profile.pk, "business_name": profile.business_name, "short_description": profile.short_description, "city": profile.city,
                "help_types": form.initial.get("help_types", profile.help_types), "other_services": profile.other_services,
                "service_locations": list(profile.service_locations.values_list("pk", flat=True)), "logo_url": url(profile.profile_image),
                "photos": [{"id": photo.pk, "url": url(photo.image)} for photo in profile.portfolio_entries.all()],
                "approval_status": profile.approval_status, "review_feedback": profile.review_feedback,
                "help_choices": [{"value": value, "label": label} for value, label in WEB_HELP_CHOICES],
                "location_choices": list(ServiceLocation.objects.filter(is_active=True).values("id", "name"))}

    def get(self, request):
        return Response(self.data(self.profile(request), request))

    @transaction.atomic
    def post(self, request):
        profile = VendorProfile.objects.select_for_update().get(pk=self.profile(request).pk)
        form = QuickVendorForm(request.data, request.FILES, instance=profile)
        if not form.is_valid():
            raise ValidationError(form.errors)
        profile = form.save()
        if request.data.get("submit") in ("1", True):
            errors = profile.submission_errors()
            if errors:
                raise ValidationError(errors)
            if not profile.is_approved:
                profile.approval_status = VendorProfile.ApprovalStatus.PENDING
                profile.save(update_fields=("approval_status", "updated_at"))
        return Response(self.data(profile, request))
