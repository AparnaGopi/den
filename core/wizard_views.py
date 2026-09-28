from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.db import transaction
from django.http import JsonResponse
from django.shortcuts import redirect, render
from django.views.decorators.http import require_http_methods

from . import vendor_wizard as wizard
from .models import VendorOnboardingDraft, VendorProfile


def integer(value, default=None):
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


@login_required
@require_http_methods(['GET', 'POST'])
@transaction.atomic
def vendor_wizard(request):
    from .views import get_vendor_profile, vendor_only
    vendor_only(request)
    profile = get_vendor_profile(request.user)
    profile = VendorProfile.objects.select_for_update().get(pk=profile.pk)
    draft = wizard.get_draft(profile)
    draft = VendorOnboardingDraft.objects.select_for_update().select_related('profile', 'pricing_listing').get(pk=draft.pk)
    errors, status = {}, 200
    if request.method == 'POST':
        step = integer(request.POST.get('step'))
        answers = {}
        for name in wizard.STEP_FIELDS.get(step, ()):
            answers[name] = (request.POST.getlist(name) if name in wizard.LIST_FIELDS else
                             request.POST.get(name) == 'on' if name in wizard.BOOL_FIELDS else request.POST.get(name, ''))
        errors, status = wizard.update_draft(draft, step=step, action=request.POST.get('action', 'save'),
            answers=answers, files=request.FILES, target=integer(request.POST.get('target')),
            revision=integer(request.POST.get('revision')), photo_id=request.POST.get('photo_id'))
        if 'application/json' in request.headers.get('Accept', ''):
            return JsonResponse({**wizard.payload(draft, request), 'errors': errors}, status=status)
        if not errors:
            messages.success(request, 'Submitted for admin approval.' if request.POST.get('action') == 'submit' else 'Progress saved.')
            return redirect('core:vendor-profile-manage')
    data = wizard.payload(draft, request)
    step = draft.current_step
    form = wizard.step_form(draft, step)
    # Initial drafts may be incomplete; display errors only after validation is requested.
    form._errors.clear()
    if errors:
        for name, values in errors.items():
            for value in values:
                form.add_error(name if name in form.fields else None, value)
    return render(request, 'core/vendor_wizard.html', {
        'profile': profile, 'form': form, 'wizard': data, 'step': step,
        'step_title': wizard.STEPS[step - 1], 'steps': enumerate(wizard.STEPS, 1),
    }, status=status)
