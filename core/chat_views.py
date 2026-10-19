from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.exceptions import ValidationError
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.views.decorators.http import require_http_methods, require_POST

from .messaging import SubscriptionRequired, can_reply, chat_plan, inbox, open_customer_chat, participant_chats, send_message
from .models import ChatMessage, VendorChatSubscription


@login_required
def message_inbox(request):
    return render(request, "core/message_inbox.html", {"conversations": inbox(request.user)})


@login_required
@require_POST
def contact_vendor(request, vendor_id):
    try:
        conversation = open_customer_chat(request.user, vendor_id, request.POST.get("event_id"))
    except ValidationError as exc:
        messages.error(request, " ".join(exc.messages))
        return redirect("core:customer-dashboard")
    return redirect("core:message-thread", conversation_id=conversation.pk)


@login_required
@require_http_methods(["GET", "POST"])
def message_thread(request, conversation_id):
    conversation = get_object_or_404(participant_chats(request.user).select_related("vendor__user", "customer", "event"), pk=conversation_id)
    error = ""
    if request.method == "POST":
        try:
            send_message(request.user, conversation.pk, request.POST.get("body"))
            return redirect("core:message-thread", conversation_id=conversation.pk)
        except SubscriptionRequired:
            return redirect("core:vendor-chat-plan")
        except ValidationError as exc:
            error = " ".join(exc.messages)
    chat_messages = list(conversation.messages.select_related("sender").all())
    ChatMessage.objects.filter(pk__in=[item.pk for item in chat_messages if item.sender_id != request.user.pk and not item.read_at]).update(read_at=timezone.now())
    return render(request, "core/message_thread.html", {"conversation": conversation, "chat_messages": chat_messages, "error": error,
        "body": request.POST.get("body", "") if error else "", "can_reply": request.user.role == "customer" or can_reply(conversation)})


@login_required
@require_http_methods(["GET", "POST"])
def vendor_chat_plan(request):
    from .views import get_vendor_profile, vendor_only
    vendor_only(request)
    profile = get_vendor_profile(request.user)
    if request.method == "POST":
        subscription, _ = VendorChatSubscription.objects.get_or_create(vendor=profile)
        if not subscription.requested_at:
            subscription.requested_at = timezone.now()
            subscription.save(update_fields=("requested_at", "updated_at"))
        messages.success(request, "Your subscription interest is saved. Payments are not open yet; you have not been charged.")
        return redirect("core:vendor-chat-plan")
    return render(request, "core/vendor_chat_plan.html", {"plan": chat_plan(profile)})
