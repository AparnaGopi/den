"""Shared messaging rules for the web and mobile API."""
from datetime import timedelta
from django.core.exceptions import PermissionDenied, ValidationError
from django.db import transaction
from django.db.models import Count, F, Q, Sum
from django.shortcuts import get_object_or_404
from django.utils import timezone

from accounts.models import User
from .models import ChatMessage, Conversation, EventRequest, VendorChatSubscription, VendorProfile, VendorProfileVisit


FREE_CLIENTS = 3


class SubscriptionRequired(ValidationError):
    pass


def participant_chats(user):
    if user.role == User.Role.VENDOR:
        return Conversation.objects.filter(vendor__user=user)
    return Conversation.objects.filter(customer=user)


def chat_plan(profile):
    subscription = VendorChatSubscription.objects.filter(vendor=profile).first()
    used = profile.conversations.filter(trial_access=True).count()
    return {"active": bool(subscription and subscription.is_active), "active_until": subscription.active_until if subscription else None,
            "free_clients_used": used, "free_clients_remaining": max(0, FREE_CLIENTS - used), "free_clients_limit": FREE_CLIENTS,
            "requested": bool(subscription and subscription.requested_at)}


def can_reply(conversation):
    plan = chat_plan(conversation.vendor)
    return conversation.trial_access or plan["active"] or plan["free_clients_remaining"] > 0


@transaction.atomic
def open_customer_chat(user, vendor_id, event_id=None):
    if user.role != User.Role.CUSTOMER:
        raise PermissionDenied
    profile = get_object_or_404(VendorProfile, pk=vendor_id, approval_status="APPROVED", is_active=True, user__is_active=True, user__role=User.Role.VENDOR)
    if event_id:
        try:
            event_id = int(event_id)
        except (TypeError, ValueError):
            raise ValidationError("Choose one of your event plans.")
    event = get_object_or_404(EventRequest, pk=event_id, customer=user, status=EventRequest.Status.READY) if event_id else None
    conversation, _ = Conversation.objects.get_or_create(vendor=profile, customer=user, defaults={"event": event})
    # Sharing an event is an explicit customer action, never a vendor lookup.
    if event and conversation.event_id != event.pk:
        conversation.event = event
        conversation.save(update_fields=("event", "updated_at"))
    return conversation


@transaction.atomic
def send_message(user, conversation_id, body):
    body = str(body or "").strip()
    if not body or len(body) > 4000:
        raise ValidationError("Write a message of 1 to 4,000 characters.")
    conversation = get_object_or_404(participant_chats(user).select_related("vendor__user", "customer"), pk=conversation_id)
    # Serialize the trial check for ALL of this vendor's conversations.
    profile = VendorProfile.objects.select_for_update().get(pk=conversation.vendor_id)
    conversation = Conversation.objects.select_for_update().get(pk=conversation.pk)
    if not profile.is_active or not profile.user.is_active or not conversation.customer.is_active or not profile.is_approved:
        raise PermissionDenied("Messaging is unavailable for this profile.")
    if user.role == User.Role.VENDOR:
        if not conversation.messages.filter(sender=conversation.customer).exists():
            raise PermissionDenied("Reply after the customer starts the conversation.")
        plan = chat_plan(profile)
        if not plan["active"] and not conversation.trial_access:
            if plan["free_clients_remaining"] == 0:
                raise SubscriptionRequired("Your three free client chats are in use. Subscribe to chat with more clients.")
            conversation.trial_access = True
        conversation.vendor_first_reply_at = conversation.vendor_first_reply_at or timezone.now()
    message = ChatMessage.objects.create(conversation=conversation, sender=user, body=body)
    conversation.save(update_fields=("trial_access", "vendor_first_reply_at", "updated_at"))
    return message


def inbox(user):
    return participant_chats(user).filter(messages__isnull=False).select_related("vendor__user", "customer", "event").annotate(
        unread_count=Count("messages", filter=Q(messages__read_at__isnull=True) & ~Q(messages__sender=user), distinct=True),
    ).distinct().order_by("-updated_at", "-pk")


def record_visit(profile, user):
    if not user.is_authenticated or user.role != User.Role.CUSTOMER or user.pk == profile.user_id:
        return
    visit, created = VendorProfileVisit.objects.get_or_create(vendor=profile, customer=user, date=timezone.localdate())
    if not created:
        VendorProfileVisit.objects.filter(pk=visit.pk).update(views=F("views") + 1, last_visited_at=timezone.now())


def visit_stats(profile):
    totals = profile.profile_visits.aggregate(total=Sum("views"), customers=Count("customer", distinct=True))
    return {"total_views": totals["total"] or 0, "unique_customers": totals["customers"],
            "last_7_days": profile.profile_visits.filter(date__gte=timezone.localdate() - timedelta(days=6)).aggregate(total=Sum("views"))["total"] or 0}
