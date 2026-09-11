from django.contrib.auth.decorators import login_required
from django.shortcuts import redirect, render

from accounts.models import User


def home(request):
	return render(request, "home.html")


@login_required
def customer_dashboard(request):
	if request.user.role != User.Role.CUSTOMER:
		return redirect("core:vendor-dashboard")
	return render(request, "core/dashboard.html", {"dashboard_type": "Customer"})


@login_required
def vendor_dashboard(request):
	if request.user.role != User.Role.VENDOR:
		return redirect("core:customer-dashboard")
	return render(request, "core/dashboard.html", {"dashboard_type": "Vendor"})
