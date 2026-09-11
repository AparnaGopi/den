from django.contrib import messages
from django.contrib.auth import login, logout
from django.contrib.auth.decorators import login_required
from django.shortcuts import redirect, render
from django.views.decorators.http import require_POST

from .forms import LoginForm, RegistrationForm
from .models import User


def dashboard_for(user):
	if user.role == User.Role.VENDOR:
		return "core:vendor-dashboard"
	return "core:customer-dashboard"


def register(request):
	if request.user.is_authenticated:
		return redirect(dashboard_for(request.user))
	initial_role = request.GET.get("role") if request.GET.get("role") in User.Role.values else User.Role.CUSTOMER
	form = RegistrationForm(request.POST or None, initial={"role": initial_role})
	if request.method == "POST" and form.is_valid():
		user = form.save()
		login(request, user)
		messages.success(request, "Welcome to Den. Your account is ready.")
		return redirect(dashboard_for(user))
	return render(request, "accounts/register.html", {"form": form})


def login_view(request):
	if request.user.is_authenticated:
		return redirect(dashboard_for(request.user))
	form = LoginForm(request=request, data=request.POST or None)
	if request.method == "POST" and form.is_valid():
		user = form.get_user()
		login(request, user)
		messages.success(request, "You are now signed in.")
		return redirect(dashboard_for(user))
	return render(request, "accounts/login.html", {"form": form})


@require_POST
@login_required
def logout_view(request):
	logout(request)
	messages.success(request, "You have been signed out.")
	return redirect("core:home")
